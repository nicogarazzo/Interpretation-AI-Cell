#!/usr/bin/env node
// cost-report.mjs — Token & cost estimator for a completed pipeline run
//
// Usage:  node scripts/cost-report.mjs <run_id>
//         make cost-report RUN=2026-06-02_001
//
// Reads actual output files from corpus/runs/<run_id>/
// Estimates token counts from file sizes (chars ÷ 4 ratio, standard approximation)
// Applies live pricing from shared/token-budget.yml
// Writes final/cost-report.json and prints a formatted table

import { readFile, writeFile, stat, access } from 'node:fs/promises';
import { join, dirname }                      from 'node:path';
import { fileURLToPath }                      from 'node:url';

const __dirname    = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..');
const CORPUS_DIR   = join(PROJECT_ROOT, 'corpus', 'runs');
const PROFILES_DIR = join(PROJECT_ROOT, 'profiles');
const SHARED_DIR   = join(PROJECT_ROOT, 'shared');

// Chars-per-token approximation (OpenAI/Anthropic standard: ~4 chars/token)
const CHARS_PER_TOKEN = 4;

// Fixed overhead per agent invocation: Kanban system prompt + task metadata
const KANBAN_OVERHEAD_TOKENS = 250;

// ─── helpers ────────────────────────────────────────────────────────────────

async function fileSize(path) {
  try { return (await stat(path)).size; }
  catch { return null; }
}

async function readJSON(path) {
  try { return JSON.parse(await readFile(path, 'utf8')); }
  catch { return null; }
}

async function readText(path) {
  try { return await readFile(path, 'utf8'); }
  catch { return null; }
}

function charsToTokens(chars) {
  return Math.round(chars / CHARS_PER_TOKEN);
}

// ─── read config files ───────────────────────────────────────────────────────

async function readAgentModel(agentName) {
  const configPath = join(PROFILES_DIR, agentName, 'config.yaml');
  const txt = await readText(configPath);
  if (!txt) return null;
  const m = txt.match(/^\s*default:\s*(\S+)/m);
  return m ? m[1] : null;
}

async function readPricing() {
  const txt = await readText(join(SHARED_DIR, 'token-budget.yml'));
  if (!txt) return { opus: { input: 15, output: 75 }, sonnet: { input: 3, output: 15 } };

  // Extract pricing block with simple regex
  const opusIn  = txt.match(/opus:\s*\n\s*input_per_1m:\s*([\d.]+)/)?.[1];
  const opusOut = txt.match(/opus:\s*\n\s*input_per_1m:.*\n\s*output_per_1m:\s*([\d.]+)/s)?.[1];
  const sonIn   = txt.match(/sonnet:\s*\n\s*input_per_1m:\s*([\d.]+)/)?.[1];
  const sonOut  = txt.match(/sonnet:\s*\n\s*input_per_1m:.*\n\s*output_per_1m:\s*([\d.]+)/s)?.[1];

  return {
    opus:   { input: parseFloat(opusIn  ?? 15),  output: parseFloat(opusOut ?? 75) },
    sonnet: { input: parseFloat(sonIn   ?? 3),   output: parseFloat(sonOut  ?? 15) },
  };
}

function modelTier(modelId) {
  if (!modelId) return 'unknown';
  if (modelId.includes('opus'))   return 'opus';
  if (modelId.includes('sonnet')) return 'sonnet';
  if (modelId.includes('haiku'))  return 'haiku';
  return 'unknown';
}

function costUSD(inputTokens, outputTokens, tier, pricing) {
  const p = pricing[tier];
  if (!p) return null;
  return (inputTokens / 1_000_000) * p.input + (outputTokens / 1_000_000) * p.output;
}

// ─── per-agent estimation ────────────────────────────────────────────────────

async function estimateTranslator(runDir) {
  // Input: SOUL.md (system prompt) + source/segments.json
  // Output: final/translation_draft.json
  const soulSize  = await fileSize(join(PROFILES_DIR, 'translator', 'SOUL.md'));
  const inputSize = await fileSize(join(runDir, 'source', 'segments.json'));
  const draftPath = join(runDir, 'final', 'translation_draft.json');
  const draftSize = await fileSize(draftPath);

  if (!draftSize) return null;   // run didn't complete translation

  // Read for segment count and model
  const draft = await readJSON(draftPath);
  const segsCount    = draft?.segments?.length ?? draft?.translations?.length ?? 0;
  const modelFromFile = draft?.translator?.model ?? null;

  const inputTokens  = charsToTokens((soulSize ?? 1500) + (inputSize ?? 0)) + KANBAN_OVERHEAD_TOKENS;
  const outputTokens = charsToTokens(draftSize);

  // _usage self-report (if present, prefer segments_processed from agent)
  const selfReport = draft?._usage ?? null;

  return {
    agent: 'translator',
    data_source: 'final/translation_draft.json',
    model_from_file: modelFromFile,
    segments: selfReport?.segments_processed ?? segsCount,
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    self_reported: selfReport != null,
  };
}

async function estimatePhilosopher(runDir, agentName) {
  // Input: SOUL.md + final/translation_draft.json (the text they review)
  // Output: final/critique_<agent>.json  OR  final/<agent>_critique.md
  const soulSize  = await fileSize(join(PROFILES_DIR, agentName, 'SOUL.md'));
  const draftSize = await fileSize(join(runDir, 'final', 'translation_draft.json'));

  // Try JSON first, then MD
  const jsonPath = join(runDir, 'final', `critique_${agentName}.json`);
  const mdPath   = join(runDir, 'final', `${agentName}_critique.md`);
  let outputSize = await fileSize(jsonPath);
  let outputFile = `critique_${agentName}.json`;
  if (!outputSize) {
    outputSize = await fileSize(mdPath);
    outputFile = `${agentName}_critique.md`;
  }

  if (!outputSize) return null;  // philosopher didn't run

  // Check for self-reported _usage
  const critique = await readJSON(jsonPath);
  const selfReport = critique?._usage ?? null;
  const segsCount = critique ? (
    // count from critique data: reviews array or infer from draft
    critique.reviews?.length ??
    critique.critique?.issues?.length ??   // fallback: just issues
    null
  ) : null;

  const inputTokens  = charsToTokens((soulSize ?? 1200) + (draftSize ?? 0)) + KANBAN_OVERHEAD_TOKENS;
  const outputTokens = charsToTokens(outputSize);

  return {
    agent: agentName,
    data_source: outputFile,
    model_from_file: null,   // philosophers don't write model to their critique
    segments: selfReport?.segments_processed ?? segsCount,
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    self_reported: selfReport != null,
  };
}

async function estimateScientist(runDir, agentName) {
  // Input: SOUL.md + various diff/memory data (we approximate with the full run context)
  // Output: agents/<agent>/audit.json
  const soulSize  = await fileSize(join(PROFILES_DIR, agentName, 'SOUL.md'));
  const auditPath = join(runDir, 'agents', agentName, 'audit.json');
  const outputSize = await fileSize(auditPath);

  if (!outputSize) return null;  // scientist didn't run (common — they're async/cron)

  // Reject template placeholders (run_id === '' means never populated)
  const audit = await readJSON(auditPath);
  if (!audit?.run_id) return null;

  const selfReport = audit?._usage ?? null;

  // For scientists we don't have a clean input file, estimate heuristically:
  // They read the full draft + all critiques + git diff (unknown size)
  // Use 3× SOUL.md as a rough proxy for total context
  const inputTokens  = charsToTokens((soulSize ?? 2000) * 3) + KANBAN_OVERHEAD_TOKENS;
  const outputTokens = charsToTokens(outputSize);

  return {
    agent: agentName,
    data_source: `agents/${agentName}/audit.json`,
    model_from_file: null,
    segments: selfReport?.segments_processed ?? null,
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    self_reported: selfReport != null,
  };
}

// ─── manifest ────────────────────────────────────────────────────────────────

async function readManifest(runDir) {
  const txt = await readText(join(runDir, 'manifest.yml'));
  if (!txt) return {};
  const get = key => txt.match(new RegExp(`^${key}:\\s*"([^"]*)"`, 'm'))?.[1] ?? '';
  return {
    run_id:       get('run_id'),
    client:       get('client'),
    campaign:     get('campaign'),
    content_type: get('content_type'),
    created_at:   get('created_at'),
  };
}

// ─── formatting ──────────────────────────────────────────────────────────────

function fmtNum(n, width = 7) {
  if (n == null) return '—'.padStart(width);
  return n.toLocaleString('en-US').padStart(width);
}

function fmtCost(usd) {
  if (usd == null || typeof usd !== 'number') return '     —'.padStart(10);
  return `$${usd.toFixed(4)}`.padStart(10);
}

function hr(ch = '─', len = 72) { return ch.repeat(len); }

const COL = { agent: 14, model: 29, tier: 7, inTok: 9, outTok: 9, cost: 11 };

function row(agent, model, tier, inTok, outTok, cost) {
  return [
    agent.padEnd(COL.agent),
    (model ?? '—').padEnd(COL.model),
    (tier ?? '—').padEnd(COL.tier),
    fmtNum(inTok, COL.inTok),
    fmtNum(outTok, COL.outTok),
    fmtCost(cost).padStart(COL.cost),
  ].join('  ');
}

function header() {
  return [
    'AGENT'.padEnd(COL.agent),
    'MODEL'.padEnd(COL.model),
    'TIER'.padEnd(COL.tier),
    'IN TOK'.padStart(COL.inTok),
    'OUT TOK'.padStart(COL.outTok),
    'COST (USD)'.padStart(COL.cost),
  ].join('  ');
}

// ─── main ────────────────────────────────────────────────────────────────────

const runId = process.argv[2];
if (!runId) {
  console.error('Usage: node scripts/cost-report.mjs <run_id>');
  console.error('       make cost-report RUN=2026-06-02_001');
  process.exit(1);
}

const runDir = join(CORPUS_DIR, runId);
try { await access(runDir); }
catch {
  console.error(`Run not found: ${runDir}`);
  process.exit(1);
}

const [pricing, manifest] = await Promise.all([readPricing(), readManifest(runDir)]);

// Read live model config for all agents
const agentModels = {};
await Promise.all([
  'translator', 'wittgenstein', 'quine', 'frege', 'koehn', 'cho', 'vaswani',
].map(async a => { agentModels[a] = await readAgentModel(a); }));

// Estimate tokens for each agent
const [
  translatorData,
  wittData, quineData, fregeData,
  koehnData, choData, vaswaniData,
] = await Promise.all([
  estimateTranslator(runDir),
  estimatePhilosopher(runDir, 'wittgenstein'),
  estimatePhilosopher(runDir, 'quine'),
  estimatePhilosopher(runDir, 'frege'),
  estimateScientist(runDir, 'koehn'),
  estimateScientist(runDir, 'cho'),
  estimateScientist(runDir, 'vaswani'),
]);

// Resolve final model for each agent
// Prefer: self-reported in file → live config.yaml → fallback label
function resolveModel(agentData, agentName) {
  return agentData?.model_from_file ?? agentModels[agentName] ?? null;
}

const agents = [
  { name: 'translator',   data: translatorData, group: 'hot_path' },
  { name: 'wittgenstein', data: wittData,        group: 'hot_path' },
  { name: 'quine',        data: quineData,       group: 'hot_path' },
  { name: 'frege',        data: fregeData,       group: 'hot_path' },
  { name: 'koehn',        data: koehnData,       group: 'scientists' },
  { name: 'cho',          data: choData,         group: 'scientists' },
  { name: 'vaswani',      data: vaswaniData,     group: 'scientists' },
].map(a => {
  const model = resolveModel(a.data, a.name);
  const tier  = modelTier(model);
  const inTok  = a.data?.input_tokens  ?? null;
  const outTok = a.data?.output_tokens ?? null;
  const cost   = inTok != null ? costUSD(inTok, outTok ?? 0, tier, pricing) : null;
  return { ...a, model, tier, inTok, outTok, cost };
});

// Aggregate totals
const hotPath   = agents.filter(a => a.group === 'hot_path');
const scientists = agents.filter(a => a.group === 'scientists');
const ran        = agents.filter(a => a.data != null);

const totalIn   = ran.reduce((s, a) => s + (a.inTok  ?? 0), 0);
const totalOut  = ran.reduce((s, a) => s + (a.outTok ?? 0), 0);
const totalCost = ran.reduce((s, a) => s + (a.cost   ?? 0), 0);

const hpIn   = hotPath.filter(a => a.data).reduce((s, a) => s + (a.inTok  ?? 0), 0);
const hpOut  = hotPath.filter(a => a.data).reduce((s, a) => s + (a.outTok ?? 0), 0);
const hpCost = hotPath.filter(a => a.data).reduce((s, a) => s + (a.cost   ?? 0), 0);

// ─── print report ────────────────────────────────────────────────────────────

const W = 72;
console.log();
console.log('╔' + '═'.repeat(W - 2) + '╗');
console.log(`║  TOKEN & COST REPORT — ${runId}`.padEnd(W - 1) + '║');
console.log('╚' + '═'.repeat(W - 2) + '╝');
console.log();

if (manifest.client)   console.log(`  Client:       ${manifest.client}`);
if (manifest.campaign) console.log(`  Campaign:     ${manifest.campaign}`);
if (manifest.created_at) console.log(`  Run date:     ${manifest.created_at}`);
const segs = translatorData?.segments;
if (segs)              console.log(`  Segments:     ${segs}`);
console.log(`  Estimation:   char-count → tokens at ${CHARS_PER_TOKEN}:1 ratio + SOUL.md overhead`);
console.log();

console.log(hr());
console.log(header());
console.log(hr());

for (const a of agents) {
  const notRan = a.data == null;
  const label  = notRan ? a.name : a.name;
  const suffix = notRan ? '  (not run)' : (a.data.self_reported ? '  ✓' : '');
  console.log(row(label + suffix, a.model, a.tier, a.inTok, a.outTok, a.cost));

  // Separator after hot path
  if (a.name === 'frege') {
    console.log(hr('·'));
    const hpLabel = 'HOT PATH SUB';
    console.log(row(hpLabel, '', '', hpIn, hpOut, hpCost));
    console.log(hr('·'));
  }
}

console.log(hr());
console.log(row('TOTAL RUN', '', '', totalIn, totalOut, totalCost));
console.log(hr());
console.log();
console.log('  Note: Scientists (koehn, cho, vaswani) run async via cron — may not appear in every run.');
console.log('  ✓ = agent self-reported _usage in output file (forward runs only).');
console.log();

// ─── write cost-report.json ──────────────────────────────────────────────────

const report = {
  _schema: 'interpretation-ai-cell/cost-report/v1',
  run_id: runId,
  generated_at: new Date().toISOString(),
  manifest,
  estimation_method: `char-count at ${CHARS_PER_TOKEN} chars/token + ${KANBAN_OVERHEAD_TOKENS} token kanban overhead per agent`,
  pricing_snapshot: pricing,
  agents: agents.map(a => ({
    name: a.name,
    group: a.group,
    model: a.model,
    tier: a.tier,
    ran: a.data != null,
    self_reported_usage: a.data?.self_reported ?? false,
    data_source: a.data?.data_source ?? null,
    segments_processed: a.data?.segments ?? null,
    input_tokens: a.inTok,
    output_tokens: a.outTok,
    cost_usd: a.cost != null ? parseFloat(a.cost.toFixed(6)) : null,
  })),
  summary: {
    hot_path: { input_tokens: hpIn, output_tokens: hpOut, cost_usd: parseFloat(hpCost.toFixed(6)) },
    scientists: {
      input_tokens:  scientists.filter(a => a.data).reduce((s, a) => s + (a.inTok ?? 0), 0),
      output_tokens: scientists.filter(a => a.data).reduce((s, a) => s + (a.outTok ?? 0), 0),
      cost_usd:      parseFloat(scientists.filter(a => a.data).reduce((s, a) => s + (a.cost ?? 0), 0).toFixed(6)),
    },
    total: { input_tokens: totalIn, output_tokens: totalOut, cost_usd: parseFloat(totalCost.toFixed(6)) },
  },
};

const outPath = join(runDir, 'final', 'cost-report.json');
await writeFile(outPath, JSON.stringify(report, null, 2));
console.log(`  Report written → corpus/runs/${runId}/final/cost-report.json`);
console.log();
