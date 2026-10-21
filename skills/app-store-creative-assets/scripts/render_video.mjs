#!/usr/bin/env node
// Render a looping App Store creative-asset video from an HTML page, one frame at a time.
//
//   NODE_PACKAGES=/path/to/node_modules CHROME_BIN=/path/to/chrome node render_video.mjs STORY.json \
//     --page PAGE.html --out 'out/{locale}/3840x1646/header.mp4' --evidence /path/outside/project \
//     [--stills 0,4,8] [--report render-report.json] [--no-audio]
//
// The page contract and story fields are described in references/video.md. Needs playwright-core (found through
// NODE_PACKAGES or normal resolution), a Chrome or Chromium binary (CHROME_BIN) and ffmpeg with libx264 on PATH.
// Exits nonzero with a JSON diagnostic when an input, the copy gate, a frame layout or the loop seam fails.
import {createRequire} from 'node:module';
import {mkdir, mkdtemp, readdir, readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {spawn, spawnSync} from 'node:child_process';
import {dirname, join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

// Apple's video limits as read on 21 October 2026; a story can override them with "limits" after checking the live page.
const DEFAULT_LIMITS = {fps: [30, 60], seconds: [5, 30]};
// Guideline 2.3.14: no specific or discounted pricing and no unverifiable claims. Stories add other locales' words.
const OFFER_WORDS = /\b(free|trial|discount|offer|sale|price)\b/i;
const MONEY = /[$€£¥₹%]/u;
const DIGIT = /\p{Nd}/u;

class Failure extends Error {}

function parseArgs(argv) {
  const args = {story: undefined, stills: undefined, audio: true};
  for (let i = 0; i < argv.length; i++) {
    const name = argv[i];
    const value = () => {
      if (i + 1 >= argv.length) throw new Failure(`${name} needs a value`);
      return argv[++i];
    };
    if (name === '--page') args.page = value();
    else if (name === '--out') args.out = value();
    else if (name === '--evidence') args.evidence = value();
    else if (name === '--stills') args.stills = value().split(',').map(Number);
    else if (name === '--report') args.report = value();
    else if (name === '--no-audio') args.audio = false;
    else if (name.startsWith('--')) throw new Failure(`Unknown option ${name}`);
    else if (args.story === undefined) args.story = name;
    else throw new Failure(`Unexpected argument ${name}`);
  }
  if (!args.story || !args.page || !args.evidence) throw new Failure('Pass STORY, --page and --evidence');
  if (!args.stills && !args.out) throw new Failure('Pass --out with a {locale} placeholder, or --stills');
  if (args.stills?.some(t => !Number.isFinite(t))) throw new Failure('--stills takes comma-separated seconds');
  return args;
}

function timecodeSeconds(code, fps) {
  const match = /^(\d{2}):(\d{2}):(\d{2}):(\d{2})$/.exec(code);
  if (!match) throw new Failure(`posterTimeCode must be HH:MM:SS:FF, got ${code}`);
  const [h, m, s, f] = match.slice(1).map(Number);
  if (m > 59 || s > 59 || f >= fps) throw new Failure(`posterTimeCode out of range: ${code}`);
  return h * 3600 + m * 60 + s + f / fps;
}

function checkStory(story) {
  const {canvas, fps, loopSeconds} = story;
  const limits = {...DEFAULT_LIMITS, ...story.limits};
  if (!Number.isInteger(canvas?.width) || !Number.isInteger(canvas?.height) || canvas.width <= 0 || canvas.height <= 0)
    throw new Failure('canvas needs positive integer width and height');
  if (!limits.fps.includes(fps)) throw new Failure(`fps must be one of ${limits.fps.join(', ')}`);
  if (!(loopSeconds >= limits.seconds[0] && loopSeconds <= limits.seconds[1]))
    throw new Failure(`loopSeconds must be ${limits.seconds[0]}-${limits.seconds[1]}`);
  if (!Number.isInteger(Math.round(loopSeconds * fps * 1000) / 1000))
    throw new Failure('loopSeconds × fps must be a whole number of frames');
  if (!story.copy || !Object.keys(story.copy).length) throw new Failure('copy needs at least one locale');
  const poster = timecodeSeconds(story.posterTimeCode ?? '00:00:00:00', fps);
  if (poster >= loopSeconds) throw new Failure('posterTimeCode must fall inside the loop');
}

// Headline lines carry no price, offer or number; labels may hold numbers from sourced, labelled example data.
function copyProblems(story) {
  const problems = [];
  const stems = (story.offerWords ?? []).map(w => w.toLocaleLowerCase());
  const offerish = text => OFFER_WORDS.test(text) || MONEY.test(text) || stems.some(s => text.toLocaleLowerCase().includes(s));
  for (const [locale, copy] of Object.entries(story.copy)) {
    for (const line of copy.lines ?? []) if (offerish(line) || DIGIT.test(line)) problems.push(`${locale}: headline "${line}" has a price, offer or number`);
    for (const label of copy.labels ?? []) if (offerish(label)) problems.push(`${locale}: label "${label}" has a price or offer`);
  }
  return problems;
}

const intersects = (a, b) => a.x < b.right && a.right > b.x && a.y < b.bottom && a.bottom > b.y;
const inflate = (box, d) => ({x: box.x - d, y: box.y - d, right: box.right + d, bottom: box.bottom + d});

// One frame: copy inside its column and below the status band; visible items below the band, inside the canvas unless they
// bleed on purpose, and clear of the copy unless marked nearCopyOk; an exiting item never crosses the band or the copy.
function layoutProblems(lay, story, t, locale) {
  const problems = [];
  const band = story.guides?.statusBand?.height ?? 0;
  const column = story.headline;
  const copy = lay.headline && inflate(lay.headline, story.guides?.copyClearance ?? 40);
  const {width: W, height: H} = story.canvas;
  for (const line of lay.lines ?? []) {
    if (column && (line.x < column.left - 1 || line.right > column.left + column.width + 1)) problems.push('headline line outside its column');
    if (line.y < band) problems.push('headline in the status band');
  }
  for (const item of lay.items ?? []) {
    if (item.opacity <= 0.01) continue;
    if (item.exiting) {
      if (item.y < band || (copy && intersects(copy, item))) problems.push(`exiting ${item.id} crosses the status band or the copy`);
      continue;
    }
    if (item.y < band) problems.push(`${item.id} in the status band`);
    if (!item.bleeds && (item.x < 0 || item.y < 0 || item.right > W || item.bottom > H)) problems.push(`${item.id} leaves the canvas`);
    if (copy && !item.nearCopyOk && item.opacity > 0.5 && intersects(copy, item)) problems.push(`${item.id} too close to the copy`);
  }
  return problems.map(p => `${locale} t=${t.toFixed(3)}: ${p}`);
}

function ffmpeg(args, label) {
  const result = spawnSync('ffmpeg', ['-v', 'error', '-y', ...args], {encoding: 'utf8'});
  if (result.error || result.status) throw new Failure(`${label} failed: ${result.error?.message ?? result.stderr}`);
}

// Real footage becomes a PNG sequence at the video's frame rate; the page shows frame n as an image.
async function prepareRecording(story, root, evidence, runtime) {
  const rec = story.recording;
  if (!rec) return;
  const dir = await mkdtemp(join(evidence, 'recording-'));
  ffmpeg(['-ss', String(rec.start ?? 0), '-i', join(root, rec.file), ...(rec.duration ? ['-t', String(rec.duration)] : []),
    '-vf', [`fps=${story.fps}`, rec.filter].filter(Boolean).join(','), join(dir, '%05d.png')], 'recording decode');
  runtime.framesUrl = pathToFileURL(dir).href + '/';
  runtime.frameCount = (await readdir(dir)).filter(f => f.endsWith('.png')).length;
}

// Chrome first draws a downscaled image with a fast filter and swaps in a sharper one a few frames later, which shows as a
// pop. Each prescale entry is cut and resized here (Lanczos) to its exact display size, so the page draws it 1:1.
async function prepareImages(story, root, evidence, runtime) {
  const entries = Object.entries(story.prescale ?? {});
  if (!entries.length) return;
  const dir = await mkdtemp(join(evidence, 'prescaled-'));
  runtime.prescaled = {};
  for (const [key, spec] of entries) {
    const crop = spec.crop && `crop=${spec.crop.width}:${spec.crop.height}:${spec.crop.x}:${spec.crop.y}`;
    const out = join(dir, `${key}-${spec.width}x${spec.height}.png`);
    ffmpeg(['-i', join(root, spec.file), '-vf',
      [crop, `scale=${spec.width}:${spec.height}:flags=lanczos+accurate_rnd+full_chroma_int`, 'format=rgb24'].filter(Boolean).join(','), out],
      `prescale ${key}`);
    runtime.prescaled[key] = {url: pathToFileURL(out).href, width: spec.width, height: spec.height};
  }
}

function encoder(file, story, loop, audio) {
  const {fps} = story;
  const sound = audio ? ['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000', '-map', '0:v', '-map', '1:a', '-shortest'] : [];
  const soundCodec = audio ? ['-c:a', 'aac', '-b:a', '256k'] : ['-an'];
  const ff = spawn('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-c:v', 'png', '-framerate', String(fps), '-i', '-',
    ...sound,
    '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv',
    '-c:v', 'libx264', '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709:range=tv', '-profile:v', 'high', '-level:v', '5.1',
    '-preset', 'slow', '-crf', '14', '-g', String(fps * 2), '-r', String(fps),
    '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv',
    ...soundCodec, '-movflags', '+faststart', '-t', String(loop), file], {stdio: ['pipe', 'inherit', 'inherit']});
  ff.stdin.on('error', () => {}); // a failed encoder is reported through `done`
  const done = new Promise((ok, fail) => {
    ff.on('error', fail);
    ff.on('close', code => (code ? fail(new Failure(`ffmpeg exited ${code}`)) : ok()));
  });
  return {ff, done};
}

// Compares two PNG screenshots in the page; small rasterisation differences after hundreds of frames are not a seam.
const pixelDiff = (page, a, b) => page.evaluate(async ([a, b]) => {
  const load = async src => {
    const image = new Image();
    image.src = 'data:image/png;base64,' + src;
    await image.decode();
    const canvas = new OffscreenCanvas(image.width, image.height);
    const context = canvas.getContext('2d');
    context.drawImage(image, 0, 0);
    return context.getImageData(0, 0, image.width, image.height).data;
  };
  const [p, q] = await Promise.all([load(a), load(b)]);
  let differing = 0, maxDiff = 0, over8 = 0, over24 = 0;
  for (let i = 0; i < p.length; i += 4) {
    const d = Math.max(Math.abs(p[i] - q[i]), Math.abs(p[i + 1] - q[i + 1]), Math.abs(p[i + 2] - q[i + 2]));
    if (!d) continue;
    differing++;
    maxDiff = Math.max(maxDiff, d);
    if (d > 8) over8++;
    if (d > 24) over24++;
  }
  return {identical: false, differing, maxDiff, over8, over24};
}, [a.toString('base64'), b.toString('base64')]);

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const storyPath = resolve(args.story);
  const root = dirname(storyPath);
  const story = JSON.parse(await readFile(storyPath, 'utf8'));
  checkStory(story);
  const {width: W, height: H} = story.canvas;
  const fps = story.fps;
  const loop = story.loopSeconds;
  const frames = Math.round(loop * fps);
  const locales = Object.keys(story.copy);
  if (args.out && locales.length > 1 && !args.out.includes('{locale}')) throw new Failure('--out needs {locale} for more than one locale');

  for (const input of story.inputs ?? []) {
    const digest = createHash('sha256').update(await readFile(join(root, input.file))).digest('hex');
    if (digest !== input.sha256) throw new Failure(`Input hash mismatch: ${input.file}`);
  }
  const refused = copyProblems(story);
  if (refused.length) throw new Failure(refused.join('; '));

  const evidence = resolve(args.evidence);
  await mkdir(evidence, {recursive: true});
  const runtime = {};
  await prepareRecording(story, root, evidence, runtime);
  await prepareImages(story, root, evidence, runtime);

  const require = createRequire(import.meta.url);
  const {chromium} = require(process.env.NODE_PACKAGES ? join(process.env.NODE_PACKAGES, 'playwright-core') : 'playwright-core');
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_BIN,
    args: ['--force-color-profile=srgb', '--font-render-hinting=none', '--allow-file-access-from-files'],
  });
  const problems = [];
  const report = {rendered: new Date().toISOString(), chrome: browser.version(), canvas: story.canvas, fps, frames, loopSeconds: loop,
    posterTimeCode: story.posterTimeCode ?? '00:00:00:00', audio: args.audio ? 'silent stereo AAC' : 'none', locales: {}};
  try {
    const open = async locale => {
      const page = await browser.newPage({viewport: {width: W, height: H}, deviceScaleFactor: 1});
      await page.goto(pathToFileURL(resolve(args.page)).href);
      const info = await page.evaluate(([s, l, r]) => window.setup(s, l, r), [story, locale, runtime]);
      return {page, info};
    };
    const shot = page => page.locator('#art').screenshot({type: 'png', animations: 'disabled'});
    const at = (page, t) => page.evaluate(t => window.renderAt(t), t);
    const check = async (page, t, locale) => problems.push(...layoutProblems(await page.evaluate(() => window.layout()), story, t, locale));

    if (args.stills) {
      for (const locale of locales) {
        const {page, info} = await open(locale);
        for (const t of args.stills) {
          await at(page, t);
          await check(page, t, locale);
          await writeFile(join(evidence, `${locale}-t${t.toFixed(2)}.png`), await shot(page));
        }
        report.locales[locale] = {info, stills: args.stills};
        await page.close();
      }
    } else {
      await Promise.all(locales.map(async locale => {
        const {page, info} = await open(locale);
        const file = resolve(args.out.replaceAll('{locale}', locale));
        await mkdir(dirname(file), {recursive: true});
        const {ff, done} = encoder(file, story, loop, args.audio);
        // Warm-up: Chrome rasterises a freshly painted layer slightly differently from one that has been moving. Render the
        // loop's last half second first, so frame 0 is drawn in the same state as every other frame.
        await at(page, 0);
        await shot(page);
        await page.waitForTimeout(400);
        for (let i = Math.round(fps / 2); i >= 1; i--) {
          await at(page, loop - i / fps);
          await shot(page);
        }
        let first;
        for (let i = 0; i < frames; i++) {
          const t = i / fps;
          await at(page, t);
          await check(page, t, locale);
          const png = await shot(page);
          if (i === 0) first = png;
          if (!ff.stdin.write(png)) await new Promise(ok => ff.stdin.once('drain', ok));
        }
        ff.stdin.end();
        await done;
        // Seam: the frame one loop later must match frame 0, so the wrap is one ordinary step of the motion. It fails when
        // more than 0.05% of pixels differ by more than 8 levels, or more than 200 pixels by more than 24.
        await at(page, loop);
        const wrap = await shot(page);
        const seam = wrap.equals(first) ? {identical: true, differing: 0, maxDiff: 0, over8: 0, over24: 0} : await pixelDiff(page, first, wrap);
        if (seam.over8 > W * H * 0.0005 || seam.over24 > 200) {
          problems.push(`${locale}: frame at t=${loop}s differs from frame 0 (loop seam) ${JSON.stringify(seam)}`);
          await writeFile(join(evidence, `${locale}-frame0.png`), first);
          await writeFile(join(evidence, `${locale}-wrap.png`), wrap);
        }
        report.locales[locale] = {info, file, frame0Sha256: createHash('sha256').update(first).digest('hex'), seam};
        await page.close();
      }));
    }
  } finally {
    await browser.close();
  }
  report.problems = problems.length;
  await writeFile(join(evidence, 'problems.txt'), problems.join('\n') + '\n');
  if (args.report) await writeFile(resolve(args.report), JSON.stringify(report, null, 1) + '\n');
  console.log(JSON.stringify(report, null, 1));
  if (problems.length) throw new Failure(`${problems.length} layout or seam problems, first: ${problems[0]}; all in ${join(evidence, 'problems.txt')}`);
}

try {
  await main();
} catch (error) {
  console.error(JSON.stringify({error: error.message}));
  process.exitCode = 1;
}
