// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 1 — Imports
// ─────────────────────────────────────────────────────────────────────────────
import { createServer }                        from 'node:http';
import { createReadStream }                    from 'node:fs';
import { readFile, writeFile, readdir,
         mkdir, rmdir, cp, stat, access }      from 'node:fs/promises';
import { watch as fsWatch }                    from 'node:fs';
import { execFile }                            from 'node:child_process';
import { promisify }                           from 'node:util';
import { join, dirname, relative, normalize }  from 'node:path';
import { fileURLToPath }                       from 'node:url';
import wsPkg                                   from 'ws';

const { WebSocketServer } = wsPkg;
const execFileAsync = promisify(execFile);

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 2 — Constantes
// ─────────────────────────────────────────────────────────────────────────────
const __dirname    = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..');
const CORPUS_DIR   = join(PROJECT_ROOT, 'corpus', 'runs');
const TEMPLATE_DIR = join(CORPUS_DIR, '.template');
const PORT         = parseInt(process.env.PORT ?? '3000', 10);
const TIMEOUT_MS   = parseInt(process.env.RUN_TIMEOUT_MS ?? String(10 * 60 * 1000), 10);

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 3 — Estado en memoria
// ─────────────────────────────────────────────────────────────────────────────
//
// RunState = {
//   runId:          string
//   dir:            string           — absolute path to corpus/runs/<run_id>
//   stage:          string           — current pipeline stage
//   startedAt:      number           — Date.now() at dispatch time
//   watcher:        FSWatcher|null
//   wsClients:      Set<WebSocket>
//   processedFiles: Set<string>      — relative paths already emitted
//   timeoutHandle:  Timeout|null
// }
//
const activeRuns = new Map();

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 4 — generateRunId
// ─────────────────────────────────────────────────────────────────────────────
async function generateRunId() {
  const today    = new Date().toISOString().slice(0, 10);
  const entries  = await readdir(CORPUS_DIR);
  const existing = entries.filter(d => d.startsWith(today + '_') && d !== '.template');
  const seq      = String(existing.length + 1).padStart(3, '0');
  const candidate = `${today}_${seq}`;

  // Garantizar unicidad atómica
  try {
    await mkdir(join(CORPUS_DIR, candidate));
    await rmdir(join(CORPUS_DIR, candidate));
  } catch (e) {
    if (e.code === 'EEXIST') return generateRunId();
    throw e;
  }
  return candidate;
}

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 5 — scaffoldRun
// ─────────────────────────────────────────────────────────────────────────────
async function scaffoldRun(runId, segments, meta) {
  const runDir = join(CORPUS_DIR, runId);

  // Copia recursiva del template (Node 16.7+ API, estable en 22)
  await cp(TEMPLATE_DIR, runDir, { recursive: true });

  // Parchar manifest.yml con string replacement (sin yaml parser)
  const now = new Date().toISOString();
  let manifest = await readFile(join(runDir, 'manifest.yml'), 'utf8');
  manifest = manifest
    .replace('run_id: ""', `run_id: "${runId}"`)
    .replace('created_at: ""', `created_at: "${now}"`)
    .replace('file: ""', `file: "${(meta.file ?? '').replace(/"/g, '\\"')}"`)
    .replace('campaign: ""', `campaign: "${(meta.campaign ?? '').replace(/"/g, '\\"')}"`)
    .replace('content_type: ""', `content_type: "${meta.content_type ?? ''}"`)
    .replace('funnel_stage: ""', `funnel_stage: "${meta.funnel_stage ?? ''}"`)
    .replace(/^  language: "en"$/m, `  language: "${meta.language ?? 'en-GB'}"`);
  await writeFile(join(runDir, 'manifest.yml'), manifest);

  // Sobreescribir segments.json con schema correcto + datos reales
  const segmentsPayload = {
    _schema: 'interpretation-ai-cell/segments/v1',
    run_id: runId,
    source_language: meta.language ?? 'en-GB',
    target_language: 'de',
    register: meta.register ?? 'business-formal',
    glossary: meta.glossary ?? 'default-v1',
    segments: segments,
  };
  await writeFile(
    join(runDir, 'source', 'segments.json'),
    JSON.stringify(segmentsPayload, null, 2),
  );

  return runDir;
}

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 6 — checkGateway
// ─────────────────────────────────────────────────────────────────────────────
async function checkGateway() {
  try {
    const { stdout } = await execFileAsync('hermes', ['gateway', 'status'], { timeout: 5000 });
    if (stdout.includes('running')) return 'running';
    if (stdout.includes('stopped')) return 'stopped';
    return 'unknown';
  } catch {
    return 'unknown';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 7 — dispatchRun
// ─────────────────────────────────────────────────────────────────────────────
async function dispatchRun(runId, runDir) {
  const title = `Translate: ${runId}`;
  await execFileAsync('hermes', [
    'kanban', 'create',
    '--assignee', 'translator',
    '--workspace', `dir:${runDir}`,
    '--board', 'translation',
    '--title', title,
  ], { timeout: 10000 });
}

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 8 — FILE_EVENT_MAP
// ─────────────────────────────────────────────────────────────────────────────
const FILE_EVENT_MAP = {
  'agents/translator/output.json':   { agent: 'translator',   event: 'agent_done',        nextStage: 'reviewing' },
  'agents/wittgenstein/review.json': { agent: 'wittgenstein', event: 'agent_done',        nextStage: null },
  'agents/quine/review.json':        { agent: 'quine',        event: 'agent_done',        nextStage: null },
  'agents/frege/review.json':        { agent: 'frege',        event: 'agent_done',        nextStage: null },
  'consensus/verdict.json':          { agent: 'consensus',    event: 'consensus_reached', nextStage: 'consensus' },
  'final/approved.json':             { agent: 'consensus',    event: 'agent_done',        nextStage: 'finalizing' },
  'final/review.html':               { agent: null,           event: 'artifact_ready',    format: 'html' },
  'final/review.pdf':                { agent: null,           event: 'artifact_ready',    format: 'pdf' },
  'agents/koehn/audit.json':         { agent: 'koehn',        event: 'agent_done',        nextStage: 'auditing' },
  'agents/cho/audit.json':           { agent: 'cho',          event: 'agent_done',        nextStage: null },
  'agents/vaswani/audit.json':       { agent: 'vaswani',      event: 'agent_done',        nextStage: null },
};

const PHILOSOPHERS = new Set(['wittgenstein', 'quine', 'frege']);
const SCIENTISTS   = new Set(['koehn', 'cho', 'vaswani']);

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 9 — isAgentFileComplete
// ─────────────────────────────────────────────────────────────────────────────
async function isAgentFileComplete(filepath) {
  try {
    const raw  = await readFile(filepath, 'utf8');
    const data = JSON.parse(raw);
    // Archivo de template tiene run_id: "" — un agente completado lo rellena
    return typeof data.run_id === 'string' && data.run_id.length > 0;
  } catch {
    return false;
  }
}

// Para artefactos HTML/PDF (no tienen run_id): verificar que el archivo existe y no está vacío
async function isArtifactReady(filepath) {
  try {
    const s = await stat(filepath);
    return s.size > 0;
  } catch {
    return false;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 10 — extractAgentMeta
// ─────────────────────────────────────────────────────────────────────────────
async function extractAgentMeta(filepath, agent) {
  try {
    const data = JSON.parse(await readFile(filepath, 'utf8'));
    if (agent === 'translator') {
      return {
        segments_count: data.segments?.length ?? 0,
        model_used: data.model_used ?? null,
        tokens_used: data.tokens_used ?? null,
      };
    }
    if (PHILOSOPHERS.has(agent)) {
      return {
        verdict:      data.verdict ?? null,
        confidence:   data.confidence ?? null,
        issues_count: data.critique?.issues?.length ?? 0,
      };
    }
    if (agent === 'consensus') {
      // consensus/verdict.json
      return {
        result:    data.result ?? null,
        rounds:    data.rounds ?? null,
        escalated: data.escalated ?? false,
      };
    }
    if (SCIENTISTS.has(agent)) {
      return {
        result:         data.result ?? null,
        findings_count: data.findings?.length ?? 0,
      };
    }
  } catch { /* best-effort */ }
  return {};
}

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 11 — startWatcher
// ─────────────────────────────────────────────────────────────────────────────
function startWatcher(runId) {
  const state = activeRuns.get(runId);
  if (!state) return;

  const watcher = fsWatch(state.dir, { recursive: true }, async (_eventType, filename) => {
    if (!filename) return;

    // Normalizar separadores (Windows compat) y limpiar prefijos de path
    const normalizedFilename = filename.replace(/\\/g, '/');
    // fs.watch en macOS puede devolver el path relativo desde runDir o el basename
    // Buscar match en FILE_EVENT_MAP para ambos casos
    let relPath = normalizedFilename;
    const descriptor = FILE_EVENT_MAP[relPath];
    if (!descriptor) return;

    if (state.processedFiles.has(relPath)) return;

    const fullPath = join(state.dir, relPath);

    // Verificar completitud según el tipo de artefacto
    const isJson = relPath.endsWith('.json');
    const complete = isJson
      ? await isAgentFileComplete(fullPath)
      : await isArtifactReady(fullPath);
    if (!complete) return;

    // Marcar como procesado antes del await para evitar doble-emit
    state.processedFiles.add(relPath);

    const elapsedMs = Date.now() - state.startedAt;

    if (descriptor.event === 'agent_done') {
      const meta = await extractAgentMeta(fullPath, descriptor.agent);

      // Actualizar stage
      if (descriptor.nextStage) state.stage = descriptor.nextStage;

      // Lógica especial: filósofos en paralelo
      if (PHILOSOPHERS.has(descriptor.agent)) {
        const done = [...PHILOSOPHERS].filter(p =>
          state.processedFiles.has(`agents/${p}/review.json`)
        );
        if (done.length === 3) state.stage = 'awaiting_consensus';
      }

      broadcast(runId, { type: 'agent_done', agent: descriptor.agent, stage: state.stage, elapsed_ms: elapsedMs, meta });

    } else if (descriptor.event === 'consensus_reached') {
      const meta = await extractAgentMeta(fullPath, 'consensus');
      if (descriptor.nextStage) state.stage = descriptor.nextStage;
      broadcast(runId, { type: 'consensus_reached', stage: state.stage, elapsed_ms: elapsedMs, meta });

      // Si fue escalado a humano: notificar error (pero no cerrar watcher)
      if (meta.escalated) {
        broadcast(runId, { type: 'run_error', run_id: runId, error: 'consensus_escalated', stage: state.stage, elapsed_ms: elapsedMs });
      }

    } else if (descriptor.event === 'artifact_ready') {
      const url = `/runs/${runId}/artifact?format=${descriptor.format}`;
      broadcast(runId, { type: 'artifact_ready', format: descriptor.format, url, elapsed_ms: elapsedMs });

      // run_complete se dispara cuando el PDF (artefacto principal) está listo
      if (descriptor.format === 'pdf') {
        state.stage = 'complete';
        broadcast(runId, { type: 'run_complete', run_id: runId, elapsed_ms: elapsedMs });
        cleanupRun(runId, false /* no cerrar wsClients aún */);
      }
    }
  });

  state.watcher = watcher;

  // Watchdog: timeout si el run no termina en TIMEOUT_MS
  state.timeoutHandle = setTimeout(() => {
    const s = activeRuns.get(runId);
    if (!s) return;
    broadcast(runId, {
      type: 'run_error',
      run_id: runId,
      error: 'timeout',
      stage: s.stage,
      elapsed_ms: Date.now() - s.startedAt,
    });
    cleanupRun(runId, false);
  }, TIMEOUT_MS);
}

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 12 — broadcast + cleanupRun
// ─────────────────────────────────────────────────────────────────────────────
function broadcast(runId, message) {
  const state = activeRuns.get(runId);
  if (!state) return;
  const payload = JSON.stringify(message);
  for (const ws of state.wsClients) {
    if (ws.readyState === 1 /* OPEN */) ws.send(payload);
  }
}

function cleanupRun(runId, closeClients = true) {
  const state = activeRuns.get(runId);
  if (!state) return;

  if (state.watcher) {
    state.watcher.close();
    state.watcher = null;
  }
  if (state.timeoutHandle) {
    clearTimeout(state.timeoutHandle);
    state.timeoutHandle = null;
  }
  if (closeClients) {
    for (const ws of state.wsClients) ws.close();
    activeRuns.delete(runId);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 13 — HTTP router
// ─────────────────────────────────────────────────────────────────────────────
function send(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(payload);
}

async function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => {
      try { resolve(JSON.parse(Buffer.concat(chunks).toString())); }
      catch { reject(new Error('Invalid JSON body')); }
    });
    req.on('error', reject);
  });
}

async function router(req, res) {
  const url      = new URL(req.url, `http://localhost:${PORT}`);
  const method   = req.method.toUpperCase();
  const segments = url.pathname.split('/').filter(Boolean); // ['runs', '<id>', 'artifact']

  // POST /runs
  if (method === 'POST' && segments[0] === 'runs' && segments.length === 1) {
    return handleCreateRun(req, res);
  }
  // GET /runs
  if (method === 'GET' && segments[0] === 'runs' && segments.length === 1) {
    return handleListRuns(req, res);
  }
  // GET /runs/:id/status
  if (method === 'GET' && segments[0] === 'runs' && segments.length === 2) {
    return handleGetStatus(req, res, segments[1]);
  }
  // GET /runs/:id/artifact?format=...
  if (method === 'GET' && segments[0] === 'runs' && segments[2] === 'artifact') {
    return handleServeArtifact(req, res, segments[1], url.searchParams.get('format'));
  }
  // DELETE /runs/:id
  if (method === 'DELETE' && segments[0] === 'runs' && segments.length === 2) {
    return handleCancelRun(req, res, segments[1]);
  }

  send(res, 404, { error: 'not_found' });
}

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 14 — Handlers
// ─────────────────────────────────────────────────────────────────────────────
async function handleCreateRun(req, res) {
  let body;
  try {
    body = await readBody(req);
  } catch {
    return send(res, 400, { error: 'invalid_body', hint: 'Expected JSON: { segments, meta }' });
  }

  const { segments, meta = {} } = body;
  if (!Array.isArray(segments) || segments.length === 0) {
    return send(res, 400, { error: 'missing_segments', hint: 'segments must be a non-empty array' });
  }

  // Verificar gateway antes de crear la run
  const gwStatus = await checkGateway();
  if (gwStatus !== 'running') {
    return send(res, 503, { error: 'gateway_not_running', hint: 'Run: make start', status: gwStatus });
  }

  let runId, runDir;
  try {
    runId  = await generateRunId();
    runDir = await scaffoldRun(runId, segments, meta);
  } catch (e) {
    return send(res, 500, { error: 'scaffold_failed', detail: e.message });
  }

  // Registrar estado en memoria antes de despachar
  activeRuns.set(runId, {
    runId,
    dir: runDir,
    stage: 'dispatched',
    startedAt: Date.now(),
    watcher: null,
    wsClients: new Set(),
    processedFiles: new Set(),
    timeoutHandle: null,
  });

  try {
    await dispatchRun(runId, runDir);
  } catch (e) {
    activeRuns.delete(runId);
    return send(res, 500, { error: 'dispatch_failed', detail: e.message });
  }

  startWatcher(runId);

  send(res, 202, {
    run_id: runId,
    ws_url: `ws://localhost:${PORT}/runs/${runId}`,
    status_url: `/runs/${runId}/status`,
  });
}

async function handleListRuns(req, res) {
  try {
    const entries = await readdir(CORPUS_DIR);
    const runs = await Promise.all(
      entries
        .filter(d => /^\d{4}-\d{2}-\d{2}_\d{3}$/.test(d))
        .map(async runId => {
          const state = activeRuns.get(runId);
          let status = state?.stage ?? 'unknown';
          // Leer manifest solo si no está en memoria
          if (!state) {
            try {
              const manifest = await readFile(join(CORPUS_DIR, runId, 'manifest.yml'), 'utf8');
              const match = manifest.match(/^status:\s*"([^"]+)"/m);
              if (match) status = match[1];
            } catch { /* ignore */ }
          }
          return { run_id: runId, status };
        })
    );
    send(res, 200, { runs });
  } catch (e) {
    send(res, 500, { error: 'list_failed', detail: e.message });
  }
}

async function handleGetStatus(req, res, runId) {
  const runDir = join(CORPUS_DIR, runId);
  try {
    await access(runDir);
  } catch {
    return send(res, 404, { error: 'run_not_found', run_id: runId });
  }

  const state = activeRuns.get(runId);
  const agentsDone = state ? [...state.processedFiles] : [];
  const elapsedMs  = state ? Date.now() - state.startedAt : null;
  let status = state?.stage ?? 'unknown';

  if (!state) {
    try {
      const manifest = await readFile(join(runDir, 'manifest.yml'), 'utf8');
      const match = manifest.match(/^status:\s*"([^"]+)"/m);
      if (match) status = match[1];
    } catch { /* ignore */ }
  }

  send(res, 200, { run_id: runId, status, stage: status, agents_done: agentsDone, elapsed_ms: elapsedMs });
}

const ARTIFACT_PATHS   = { pdf: 'final/review.pdf', html: 'final/review.html', json: 'final/approved.json' };
const ARTIFACT_CTYPES  = { pdf: 'application/pdf', html: 'text/html; charset=utf-8', json: 'application/json' };

async function handleServeArtifact(req, res, runId, format) {
  if (!format || !ARTIFACT_PATHS[format]) {
    return send(res, 400, { error: 'invalid_format', hint: 'format must be pdf|html|json' });
  }

  const runDir   = join(CORPUS_DIR, runId);
  const filePath = join(runDir, ARTIFACT_PATHS[format]);

  try {
    await access(runDir);
  } catch {
    return send(res, 404, { error: 'run_not_found', run_id: runId });
  }

  let fileStat;
  try {
    fileStat = await stat(filePath);
  } catch {
    return send(res, 404, { error: 'artifact_not_ready', format, run_id: runId });
  }

  res.writeHead(200, {
    'Content-Type': ARTIFACT_CTYPES[format],
    'Content-Length': fileStat.size,
    'Content-Disposition': `attachment; filename="translation-${runId}.${format}"`,
    'Cache-Control': 'no-store',
  });
  createReadStream(filePath).pipe(res);
}

async function handleCancelRun(req, res, runId) {
  const state = activeRuns.get(runId);
  if (!state) {
    // Check if directory exists at all
    try {
      await access(join(CORPUS_DIR, runId));
      return send(res, 204, null);
    } catch {
      return send(res, 404, { error: 'run_not_found', run_id: runId });
    }
  }

  broadcast(runId, { type: 'cancelled', run_id: runId });
  cleanupRun(runId, true);
  res.writeHead(204);
  res.end();
}

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 15 — WebSocket server
// ─────────────────────────────────────────────────────────────────────────────
const wss = new WebSocketServer({ noServer: true });

wss.on('connection', (ws, req, runId) => {
  const state = activeRuns.get(runId);
  if (!state) {
    ws.close(4004, 'run_not_found');
    return;
  }

  state.wsClients.add(ws);

  // Snapshot inmediato del estado actual
  ws.send(JSON.stringify({
    type: 'snapshot',
    run_id: runId,
    stage: state.stage,
    agents_done: [...state.processedFiles],
    elapsed_ms: Date.now() - state.startedAt,
  }));

  ws.on('message', raw => {
    let msg;
    try { msg = JSON.parse(raw.toString()); } catch { return; }
    if (msg.type === 'cancel') {
      broadcast(runId, { type: 'cancelled', run_id: runId });
      cleanupRun(runId, true);
    }
  });

  ws.on('close', () => {
    const s = activeRuns.get(runId);
    if (s) s.wsClients.delete(ws);
  });

  ws.on('error', () => {
    const s = activeRuns.get(runId);
    if (s) s.wsClients.delete(ws);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN 16 — Bootstrap + server.listen
// ─────────────────────────────────────────────────────────────────────────────
async function restoreInProgressRuns() {
  let entries;
  try {
    entries = await readdir(CORPUS_DIR);
  } catch {
    return;
  }

  for (const runId of entries) {
    if (!/^\d{4}-\d{2}-\d{2}_\d{3}$/.test(runId)) continue;

    const runDir = join(CORPUS_DIR, runId);
    let status;
    try {
      const manifest = await readFile(join(runDir, 'manifest.yml'), 'utf8');
      const match    = manifest.match(/^status:\s*"([^"]+)"/m);
      status = match?.[1];
    } catch { continue; }

    if (status !== 'in_progress') continue;

    // Reconstruir processedFiles verificando qué archivos ya existen y están completos
    const processedFiles = new Set();
    for (const [relPath] of Object.entries(FILE_EVENT_MAP)) {
      const fullPath = join(runDir, relPath);
      const isJson = relPath.endsWith('.json');
      const complete = isJson
        ? await isAgentFileComplete(fullPath)
        : await isArtifactReady(fullPath);
      if (complete) processedFiles.add(relPath);
    }

    activeRuns.set(runId, {
      runId,
      dir: runDir,
      stage: 'in_progress',
      startedAt: Date.now(),
      watcher: null,
      wsClients: new Set(),
      processedFiles,
      timeoutHandle: null,
    });

    startWatcher(runId);
    console.log(`[boot] Restored watcher for in-progress run: ${runId}`);
  }
}

const server = createServer(async (req, res) => {
  try {
    await router(req, res);
  } catch (e) {
    console.error('[server] Unhandled error:', e);
    if (!res.headersSent) send(res, 500, { error: 'internal_error', detail: e.message });
  }
});

server.on('upgrade', (req, socket, head) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const segs = url.pathname.split('/').filter(Boolean);

  // Only handle WS for /runs/:run_id
  if (segs[0] !== 'runs' || segs.length !== 2) {
    socket.destroy();
    return;
  }

  const runId = segs[1];
  wss.handleUpgrade(req, socket, head, ws => {
    wss.emit('connection', ws, req, runId);
  });
});

await restoreInProgressRuns();

server.listen(PORT, () => {
  console.log(`[server] Interpretation AI Cell API listening on http://localhost:${PORT}`);
  console.log(`[server] WebSocket: ws://localhost:${PORT}/runs/<run_id>`);
  console.log(`[server] Run timeout: ${TIMEOUT_MS / 1000}s`);
});
