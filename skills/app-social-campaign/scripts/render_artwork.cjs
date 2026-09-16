#!/usr/bin/env node
// Render an app-specific HTML artboard file; this helper imposes no brand/layout.
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const { pathToFileURL } = require('url');
const [rootArg, specArg] = process.argv.slice(2);
if (!rootArg || !specArg) throw new Error('Usage: node render_artwork.cjs CAMPAIGN_ROOT RENDER_SPEC.json');
const root = fs.realpathSync(path.resolve(rootArg));
function local(name) {
  const p = path.resolve(root, name);
  if (p === root || path.relative(root, p).startsWith('..') || path.isAbsolute(path.relative(root, p))) throw new Error('Path outside campaign: ' + name);
  let ancestor = p;
  while (!fs.existsSync(ancestor)) ancestor = path.dirname(ancestor);
  const realAncestor = fs.realpathSync(ancestor);
  const relativeAncestor = path.relative(root, realAncestor);
  if (relativeAncestor.startsWith('..') || path.isAbsolute(relativeAncestor)) throw new Error('Symlink points outside campaign: ' + name);
  return p;
}
const spec = JSON.parse(fs.readFileSync(local(specArg), 'utf8'));
const moduleRoot = process.env.NODE_PACKAGES;
const dependency = name => require(moduleRoot ? path.join(moduleRoot, name) : name);
const { chromium } = dependency('playwright'), sharp = dependency('sharp');
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const locks = spec.approvedHashes ? JSON.parse(fs.readFileSync(local(spec.approvedHashes))) : {};
for (const [file, expected] of Object.entries(locks)) if (hash(local(file)) !== expected) throw new Error('Approved file changed: ' + file);
if (!Array.isArray(spec.items) || !spec.items.length) throw new Error('No render items');
if (new Set(spec.items.map(x => x.file)).size !== spec.items.length) throw new Error('Duplicate output files');
for (const item of spec.items) {
  local(item.file);
  if (!item.selector || !Number.isInteger(item.width) || !Number.isInteger(item.height) || item.width < 1 || item.height < 1) throw new Error('Invalid render item');
}
(async () => {
  const options = { headless: true };
  if (process.env.CHROME_BIN) options.executablePath = process.env.CHROME_BIN;
  const browser = await chromium.launch(options);
  const report = [];
  try {
    const page = await browser.newPage({ viewport: { width: Math.max(...spec.items.map(i => i.width)), height: Math.max(...spec.items.map(i => i.height)) }, deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(local(spec.html)).href);
    await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(i => i.decode())); });
    for (const item of spec.items) {
      if (locks[item.file]) { report.push({ file: item.file, preserved: true, sha256: locks[item.file] }); continue; }
      const art = page.locator(item.selector);
      if (await art.count() !== 1) throw new Error('Expected one artboard: ' + item.selector);
      const issues = await art.evaluate((element, selector) => {
        const canvas = element.getBoundingClientRect();
        return [...element.querySelectorAll(selector)].flatMap(node => {
          const r = node.getBoundingClientRect();
          return r.left < canvas.left - 1 || r.right > canvas.right + 1 || r.top < canvas.top - 1 || r.bottom > canvas.bottom + 1 || node.scrollWidth > node.clientWidth + 2
            ? [{ element: node.tagName, text: node.textContent.slice(0, 100) }] : [];
        });
      }, item.textSelector || 'h1,h2,h3,p,[data-check]');
      if (issues.length) throw new Error('Text outside artboard: ' + item.file + ' ' + JSON.stringify(issues));
      const buffer = await sharp(await art.screenshot({ type: 'png' })).flatten({ background: item.background || '#ffffff' }).toColourspace('srgb').png().toBuffer();
      const m = await sharp(buffer).metadata();
      if (m.width !== item.width || m.height !== item.height || m.channels !== 3) throw new Error('Unexpected PNG dimensions/channels: ' + item.file);
      const output = local(item.file);
      fs.mkdirSync(path.dirname(output), { recursive: true });
      fs.writeFileSync(output, buffer);
      report.push({ file: item.file, width: m.width, height: m.height, channels: m.channels, bounds: 'passed', sha256: hash(output) });
    }
  } finally { await browser.close(); }
  const reportPath = local(spec.report || 'source/render-report.json');
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, JSON.stringify({ evidence: 'Technical export checks; visual inspection still required.', items: report }, null, 2));
  console.log(JSON.stringify({ checked: report.length, preserved: report.filter(i => i.preserved).length, report: reportPath }));
})().catch(error => { console.error(error.message); process.exitCode = 1; });
