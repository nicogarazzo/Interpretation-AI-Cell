import puppeteer from 'puppeteer';
import { resolve } from 'path';
import { existsSync } from 'fs';

const input = process.argv[2];
const output = process.argv[3];

if (!input || !output) {
  console.error('Usage: node html-to-pdf.mjs <input.html> <output.pdf>');
  process.exit(1);
}

const inputPath = resolve(input);
if (!existsSync(inputPath)) {
  console.error(`File not found: ${inputPath}`);
  process.exit(1);
}

const browser = await puppeteer.launch({ headless: true });
const page = await browser.newPage();
await page.goto(`file://${inputPath}`, { waitUntil: 'networkidle0' });
await page.pdf({
  path: resolve(output),
  format: 'A4',
  margin: { top: '20mm', bottom: '24mm', left: '18mm', right: '18mm' },
  printBackground: true,
  displayHeaderFooter: true,
  headerTemplate: '<div></div>',
  footerTemplate: '<div style="font-size:8px;color:#aaa;width:100%;text-align:center;padding:0 20mm;">Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>',
});
await browser.close();
console.log(`PDF saved: ${resolve(output)}`);
