#!/usr/bin/env node

import { readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import { inflateSync } from "node:zlib";

const VALID_VERDICTS = new Set(["unreviewed", "keep", "iterate", "drop"]);
const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
const CRC_TABLE = Array.from({ length: 256 }, (_, value) => {
    let checksum = value;
    for (let bit = 0; bit < 8; bit += 1) {
        checksum = (checksum & 1) ? 0xedb88320 ^ (checksum >>> 1) : checksum >>> 1;
    }
    return checksum >>> 0;
});

function fail(message) {
    console.error(`review-board: ${message}`);
    process.exit(1);
}

function usage() {
    console.log("Usage: node build-review-board.mjs --manifest <file> --output <file> [--decisions <file>]");
}

function parseArguments(argv) {
    const options = {};
    for (let index = 0; index < argv.length; index += 1) {
        const flag = argv[index];
        if (flag === "--help" || flag === "-h") {
            usage();
            process.exit(0);
        }
        if (!["--manifest", "--output", "--decisions"].includes(flag)) fail(`unknown argument ${flag}`);
        const value = argv[index + 1];
        if (!value || value.startsWith("--")) fail(`${flag} requires a value`);
        options[flag.slice(2)] = value;
        index += 1;
    }
    if (!options.manifest || !options.output) {
        usage();
        fail("--manifest and --output are required");
    }
    return options;
}

function loadJson(path, label) {
    try {
        return JSON.parse(readFileSync(path, "utf8"));
    } catch (error) {
        fail(`cannot read ${label} at ${path}: ${error.message}`);
    }
}

function requiredString(value, label) {
    if (typeof value !== "string" || !value.trim()) fail(`${label} must be a non-empty string`);
    return value.trim();
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function safeJson(value) {
    return JSON.stringify(value).replaceAll("<", "\\u003c").replaceAll(">", "\\u003e").replaceAll("&", "\\u0026");
}

function resolveInside(root, child, label) {
    const path = resolve(root, child);
    const relation = relative(root, path);
    if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
        fail(`${label} escapes sourceDir: ${child}`);
    }
    return path;
}

function crc32(bytes) {
    let checksum = 0xffffffff;
    for (const byte of bytes) checksum = CRC_TABLE[(checksum ^ byte) & 0xff] ^ (checksum >>> 8);
    return (checksum ^ 0xffffffff) >>> 0;
}

function inspectPng(path, label) {
    let bytes;
    try {
        bytes = readFileSync(path);
    } catch (error) {
        fail(`cannot read ${label} at ${path}: ${error.message}`);
    }
    if (bytes.length < 45 || !bytes.subarray(0, 8).equals(PNG_SIGNATURE)) {
        fail(`${label} is not a valid PNG header: ${path}`);
    }

    const idatChunks = [];
    let offset = 8;
    let chunkIndex = 0;
    let sawIend = false;
    while (offset < bytes.length) {
        if (offset + 12 > bytes.length) fail(`${label} has a truncated PNG chunk: ${path}`);
        const length = bytes.readUInt32BE(offset);
        const end = offset + 12 + length;
        if (end > bytes.length) fail(`${label} has a truncated PNG chunk payload: ${path}`);
        const typeBytes = bytes.subarray(offset + 4, offset + 8);
        const type = typeBytes.toString("ascii");
        const data = bytes.subarray(offset + 8, offset + 8 + length);
        const storedCrc = bytes.readUInt32BE(offset + 8 + length);
        const actualCrc = crc32(Buffer.concat([typeBytes, data]));
        if (storedCrc !== actualCrc) fail(`${label} has a bad ${type} chunk checksum: ${path}`);
        if (chunkIndex === 0 && (type !== "IHDR" || length !== 13)) fail(`${label} must start with a 13-byte IHDR chunk: ${path}`);
        if (type === "IDAT") idatChunks.push(data);
        if (type === "IEND") {
            if (length !== 0 || end !== bytes.length) fail(`${label} has an invalid final IEND chunk: ${path}`);
            sawIend = true;
        }
        offset = end;
        chunkIndex += 1;
    }
    if (!sawIend || idatChunks.length === 0) fail(`${label} is missing PNG image data or IEND: ${path}`);

    const width = bytes.readUInt32BE(16);
    const height = bytes.readUInt32BE(20);
    const bitDepth = bytes[24];
    const colorType = bytes[25];
    if (width !== 1080 || height !== 1350) {
        fail(`${label} must be 1080x1350, found ${width}x${height}: ${path}`);
    }
    if (bitDepth !== 8 || colorType !== 2) {
        fail(`${label} must be 8-bit RGB without alpha, found bit depth ${bitDepth} and PNG color type ${colorType}: ${path}`);
    }
    let pixels;
    try {
        pixels = inflateSync(Buffer.concat(idatChunks));
    } catch (error) {
        fail(`${label} has invalid compressed image data at ${path}: ${error.message}`);
    }
    const interlaceMethod = bytes[28];
    if (interlaceMethod === 0) {
        const rowLength = 1 + width * 3;
        if (pixels.length !== rowLength * height) fail(`${label} has an invalid decoded RGB byte count: ${path}`);
        for (let row = 0; row < height; row += 1) {
            if (pixels[row * rowLength] > 4) fail(`${label} has an invalid PNG row filter: ${path}`);
        }
    } else if (interlaceMethod !== 1) {
        fail(`${label} has an invalid PNG interlace method: ${path}`);
    }
    return `data:image/png;base64,${bytes.toString("base64")}`;
}

function normalizedDecisions(raw, campaignId) {
    if (!raw) return {};
    if (raw.schemaVersion !== 1 || raw.campaignId !== campaignId || typeof raw.decisions !== "object" || raw.decisions === null) {
        fail("decision file must use schemaVersion 1 and match campaign.id");
    }
    const entries = Object.entries(raw.decisions).sort(([left], [right]) => left.localeCompare(right));
    return Object.fromEntries(entries.map(([identity, state]) => {
        const verdict = state?.verdict ?? "unreviewed";
        const note = state?.note ?? "";
        if (!VALID_VERDICTS.has(verdict) || typeof note !== "string") fail(`invalid decision state for ${identity}`);
        return [identity, { verdict, note }];
    }));
}

function verifyManifest(raw, manifestPath) {
    if (raw?.schemaVersion !== 1 || typeof raw.campaign !== "object" || !Array.isArray(raw.concepts)) {
        fail("manifest must contain schemaVersion 1, campaign, and concepts");
    }
    const campaign = {
        id: requiredString(raw.campaign.id, "campaign.id"),
        title: requiredString(raw.campaign.title, "campaign.title"),
        brief: requiredString(raw.campaign.brief, "campaign.brief"),
        reference: requiredString(raw.campaign.reference, "campaign.reference"),
    };
    if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(campaign.id)) {
        fail("campaign.id may contain only letters, digits, dots, underscores, and hyphens");
    }
    if (raw.concepts.length === 0) fail("manifest must contain at least one concept");

    const identities = new Set();
    const taskSeeds = new Set();
    const manifestRoot = dirname(manifestPath);
    const concepts = raw.concepts.map((rawConcept, index) => {
        const label = `concepts[${index}]`;
        const taskId = requiredString(rawConcept.taskId, `${label}.taskId`);
        const seed = requiredString(rawConcept.seed, `${label}.seed`);
        if (!/^[a-z0-9]{10}$/.test(seed)) fail(`${label}.seed must be 10 lowercase alphanumeric characters`);
        const pair = `${taskId}::${seed}`;
        if (taskSeeds.has(pair)) fail(`duplicate taskId and seed pair: ${pair}`);
        taskSeeds.add(pair);
        const identity = `${campaign.id}::${taskId}::${seed}`;
        if (identities.has(identity)) fail(`duplicate concept identity: ${identity}`);
        identities.add(identity);

        const format = requiredString(rawConcept.format, `${label}.format`);
        if (!["single", "carousel"].includes(format)) fail(`${label}.format must be single or carousel`);
        if (!Array.isArray(rawConcept.frames)) fail(`${label}.frames must be an array`);
        if ((format === "single" && rawConcept.frames.length !== 1) || (format === "carousel" && rawConcept.frames.length < 2)) {
            fail(`${label}.frames does not match format ${format}`);
        }

        const sourceDirValue = requiredString(rawConcept.sourceDir, `${label}.sourceDir`);
        const sourceDir = resolve(manifestRoot, sourceDirValue);
        try {
            if (!statSync(sourceDir).isDirectory()) fail(`${label}.sourceDir is not a directory: ${sourceDir}`);
        } catch (error) {
            fail(`cannot inspect ${label}.sourceDir at ${sourceDir}: ${error.message}`);
        }
        for (const requiredArtifact of ["concept.md", "caption.md", "render.mjs"]) {
            const artifactPath = resolveInside(sourceDir, requiredArtifact, `${label}.${requiredArtifact}`);
            try {
                if (!statSync(artifactPath).isFile()) fail(`${label} is missing ${requiredArtifact}`);
            } catch (error) {
                fail(`cannot inspect required artifact ${artifactPath}: ${error.message}`);
            }
        }
        const frames = rawConcept.frames.map((frame, frameIndex) => {
            const frameValue = requiredString(frame, `${label}.frames[${frameIndex}]`);
            const framePath = resolveInside(sourceDir, frameValue, `${label}.frames[${frameIndex}]`);
            return {
                name: frameValue,
                dataUrl: inspectPng(framePath, `${label}.frames[${frameIndex}]`),
            };
        });

        return {
            identity,
            taskId,
            seed,
            title: requiredString(rawConcept.title, `${label}.title`),
            feature: requiredString(rawConcept.feature, `${label}.feature`),
            benefit: requiredString(rawConcept.benefit, `${label}.benefit`),
            approach: requiredString(rawConcept.approach, `${label}.approach`),
            format,
            assetStatus: requiredString(rawConcept.assetStatus ?? "ready", `${label}.assetStatus`),
            sourceDir: sourceDirValue,
            frames,
        };
    });
    return { campaign, concepts };
}

function conceptMarkup(concept, index) {
    const searchText = [concept.title, concept.feature, concept.benefit, concept.approach, concept.taskId, concept.seed].join(" ").toLowerCase();
    const frames = concept.frames.map((frame, frameIndex) => `
        <figure>
            <button class="frame" type="button" aria-label="Inspect ${escapeHtml(concept.title)}, frame ${frameIndex + 1}">
                <img src="${frame.dataUrl}" alt="${escapeHtml(concept.title)}, frame ${frameIndex + 1} of ${concept.frames.length}">
            </button>
            <figcaption>${String(frameIndex + 1).padStart(2, "0")} / ${String(concept.frames.length).padStart(2, "0")}</figcaption>
        </figure>`).join("");
    return `
    <article class="concept" data-concept data-identity="${escapeHtml(concept.identity)}" data-format="${concept.format}" data-search="${escapeHtml(searchText)}">
        <header class="concept-header">
            <span class="number">${String(index + 1).padStart(2, "0")}</span>
            <div><h2>${escapeHtml(concept.title)}</h2><p class="approach">${escapeHtml(concept.approach)}</p></div>
            <div class="badges"><span>${concept.format}</span><span>${escapeHtml(concept.assetStatus)}</span></div>
        </header>
        <dl>
            <div><dt>Feature</dt><dd>${escapeHtml(concept.feature)}</dd></div>
            <div><dt>Benefit</dt><dd>${escapeHtml(concept.benefit)}</dd></div>
            <div><dt>Origin</dt><dd><code>${escapeHtml(concept.taskId)}</code><br><code>${escapeHtml(concept.seed)}</code></dd></div>
        </dl>
        <div class="frames">${frames}
        </div>
        <section class="review" aria-label="Review ${escapeHtml(concept.title)}">
            <div class="verdicts">
                <span>Verdict</span>
                <button type="button" data-verdict="keep" aria-pressed="false">Keep</button>
                <button type="button" data-verdict="iterate" aria-pressed="false">Iterate</button>
                <button type="button" data-verdict="drop" aria-pressed="false">Drop</button>
            </div>
            <label>Decision note<textarea data-note rows="3" placeholder="Record the requested change or reason."></textarea></label>
        </section>
    </article>`;
}

function renderBoard(campaign, concepts, decisions) {
    const conceptData = Object.fromEntries(concepts.map((concept) => [concept.identity, {
        title: concept.title,
        taskId: concept.taskId,
        seed: concept.seed,
        feature: concept.feature,
    }]));
    return `<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>${escapeHtml(campaign.title)} — review</title>
    <style>
        :root { color-scheme: light; --ink: #201f1b; --paper: #f5f0e7; --card: #fffdf8; --line: #c9c0b2; --orange: #d96535; --green: #afc78a; --peach: #f0b18f; }
        * { box-sizing: border-box; }
        body { margin: 0; color: var(--ink); background: var(--paper); font: 16px/1.5 ui-sans-serif, system-ui, sans-serif; }
        .masthead, main, footer { width: min(1480px, calc(100% - 40px)); margin-inline: auto; }
        .masthead { padding: 56px 0 32px; }
        .eyebrow, dt, .approach, figcaption { text-transform: uppercase; letter-spacing: .08em; font-size: .75rem; font-weight: 750; }
        h1 { margin: 4px 0 8px; font: 700 clamp(2.4rem, 7vw, 6rem)/.96 ui-serif, Georgia, serif; max-width: 1050px; }
        .brief { max-width: 850px; font-size: 1.08rem; }
        .toolbar {
            position: sticky; top: 0; z-index: 5; display: grid; grid-template-columns: minmax(220px, 1fr) auto auto auto;
            gap: 10px; padding: 14px; margin: 24px 0 36px; background: rgba(245, 240, 231, .96); border: 1px solid var(--line);
        }
        input, select, button, textarea { color: inherit; background: var(--card); border: 1px solid var(--line); border-radius: 4px; font: inherit; }
        input, select, button { min-height: 42px; padding: 8px 12px; }
        button { cursor: pointer; font-weight: 700; }
        button:hover { border-color: var(--ink); }
        .summary { margin: 0 0 18px; font-weight: 700; }
        .concept { padding: 30px; margin-bottom: 30px; background: var(--card); border: 1px solid var(--line); box-shadow: 7px 7px 0 #ded5c7; }
        .concept[hidden] { display: none; }
        .concept-header { display: grid; grid-template-columns: auto 1fr auto; gap: 18px; align-items: start; }
        .number { display: grid; place-items: center; width: 44px; height: 44px; color: white; background: var(--orange); border-radius: 50%; font-weight: 800; }
        h2 { margin: 0; font: 700 clamp(1.7rem, 4vw, 3.2rem)/1.05 ui-serif, Georgia, serif; }
        .approach { margin: 8px 0 0; color: #665e53; }
        .badges { display: flex; gap: 7px; flex-wrap: wrap; justify-content: end; }
        .badges span { padding: 5px 9px; border: 1px solid var(--line); border-radius: 99px; font-size: .75rem; }
        dl { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin: 26px 0; }
        dl div { border-top: 1px solid var(--line); padding-top: 10px; }
        dt { color: #665e53; }
        dd { margin: 5px 0 0; }
        code { font-size: .75rem; overflow-wrap: anywhere; }
        .frames { display: flex; gap: 16px; overflow-x: auto; padding: 0 0 12px; scroll-snap-type: x proximity; }
        figure { flex: 0 0 min(390px, 82vw); margin: 0; scroll-snap-align: start; }
        .frame { display: block; width: 100%; padding: 0; background: #171714; overflow: hidden; }
        .frame img { display: block; width: 100%; height: auto; }
        figcaption { margin-top: 6px; color: #665e53; }
        .review {
            display: grid; grid-template-columns: auto minmax(260px, 1fr); gap: 24px; align-items: end;
            margin-top: 28px; padding-top: 22px; border-top: 1px solid var(--line);
        }
        .verdicts { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .verdicts span { margin-right: 4px; font-weight: 800; }
        [data-verdict="keep"][aria-pressed="true"] { background: var(--green); border-color: #6c8646; }
        [data-verdict="iterate"][aria-pressed="true"] { background: var(--peach); border-color: #a86341; }
        [data-verdict="drop"][aria-pressed="true"] { color: white; background: #5b5750; border-color: #5b5750; }
        label { display: grid; gap: 6px; font-weight: 700; }
        textarea { width: 100%; padding: 10px; resize: vertical; font-weight: 400; }
        .empty { display: none; padding: 42px; text-align: center; border: 1px dashed var(--line); }
        .empty[data-visible="true"] { display: block; }
        footer { padding: 24px 0 52px; color: #665e53; }
        dialog { width: min(1160px, calc(100% - 30px)); max-height: 96vh; padding: 12px; border: 0; background: #171714; }
        dialog::backdrop { background: rgba(0, 0, 0, .78); }
        .dialog-bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; color: white; margin-bottom: 10px; }
        .dialog-image { display: block; max-width: 100%; max-height: calc(96vh - 74px); margin: auto; }
        .visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
        @media (max-width: 800px) {
            .toolbar { position: static; grid-template-columns: 1fr 1fr; }
            .toolbar input { grid-column: 1 / -1; }
            .concept { padding: 20px; }
            .concept-header, dl, .review { grid-template-columns: 1fr; }
            .badges { justify-content: start; }
        }
        @media print {
            .toolbar, .review, dialog { display: none; }
            .concept { break-inside: avoid; box-shadow: none; }
        }
    </style>
</head>
<body>
    <header class="masthead">
        <p class="eyebrow">Campaign review · self-contained</p>
        <h1>${escapeHtml(campaign.title)}</h1>
        <p class="brief">${escapeHtml(campaign.brief)}</p>
        <p><strong>Reference:</strong> ${escapeHtml(campaign.reference)}</p>
        <div class="toolbar" aria-label="Review controls">
            <input type="search" data-search placeholder="Search title, feature, benefit, seed, or task…" aria-label="Search concepts">
            <select data-format aria-label="Filter by format">
                <option value="all">All formats</option><option value="single">Single image</option><option value="carousel">Carousel</option>
            </select>
            <select data-status aria-label="Filter by review status">
                <option value="all">All statuses</option><option value="unreviewed">Unreviewed</option><option value="keep">Keep</option>
                <option value="iterate">Iterate</option><option value="drop">Drop</option>
            </select>
            <button type="button" data-copy>Copy decision summary</button>
            <button type="button" data-export>Export decisions</button>
            <button type="button" data-import>Import decisions</button>
            <input class="visually-hidden" type="file" accept="application/json,.json" data-import-file>
        </div>
        <p class="summary" data-summary></p>
    </header>
    <main>${concepts.map(conceptMarkup).join("")}
        <p class="empty" data-empty>No concepts match this view.</p>
    </main>
    <footer>
        All ${concepts.reduce((count, concept) => count + concept.frames.length, 0)} PNG frames are embedded.
        Decisions persist locally and can be exported or imported as JSON.
    </footer>
    <dialog data-dialog>
        <div class="dialog-bar"><span data-dialog-label>Full-size creative</span><button type="button" data-close>Close</button></div>
        <img class="dialog-image" data-dialog-image alt="Full-size creative">
    </dialog>
    <script>
        const campaignId = ${safeJson(campaign.id)};
        const reviewTitle = ${safeJson(campaign.title)};
        const conceptData = ${safeJson(conceptData)};
        const embeddedDecisions = ${safeJson(decisions)};
        const storageKey = "social-campaign-lab:" + campaignId;
        const validVerdicts = new Set(["unreviewed", "keep", "iterate", "drop"]);
        const concepts = [...document.querySelectorAll("[data-concept]")];
        const search = document.querySelector("[data-search]");
        const formatFilter = document.querySelector("[data-format]");
        const statusFilter = document.querySelector("[data-status]");
        const summary = document.querySelector("[data-summary]");
        const empty = document.querySelector("[data-empty]");
        const dialog = document.querySelector("[data-dialog]");
        const dialogImage = document.querySelector("[data-dialog-image]");
        const dialogLabel = document.querySelector("[data-dialog-label]");
        let saved = { ...embeddedDecisions };

        try {
            const local = JSON.parse(localStorage.getItem(storageKey) || "{}");
            if (local && typeof local === "object") saved = { ...saved, ...local };
        } catch {}

        function normalizeState(state) {
            return {
                verdict: validVerdicts.has(state?.verdict) ? state.verdict : "unreviewed",
                note: typeof state?.note === "string" ? state.note : "",
            };
        }

        function persist() {
            try { localStorage.setItem(storageKey, JSON.stringify(saved)); } catch {}
        }

        function hydrate(concept) {
            const identity = concept.dataset.identity;
            const state = normalizeState(saved[identity]);
            saved[identity] = state;
            concept.dataset.status = state.verdict;
            concept.querySelectorAll("[data-verdict]").forEach((button) => {
                button.setAttribute("aria-pressed", String(button.dataset.verdict === state.verdict));
            });
            concept.querySelector("[data-note]").value = state.note;
        }

        function updateView() {
            const query = search.value.trim().toLowerCase();
            let shown = 0;
            concepts.forEach((concept) => {
                const matchesSearch = !query || concept.dataset.search.includes(query);
                const matchesFormat = formatFilter.value === "all" || concept.dataset.format === formatFilter.value;
                const matchesStatus = statusFilter.value === "all" || concept.dataset.status === statusFilter.value;
                concept.hidden = !(matchesSearch && matchesFormat && matchesStatus);
                if (!concept.hidden) shown += 1;
            });
            const counts = Object.fromEntries([...validVerdicts].map((verdict) => [
                verdict,
                concepts.filter((concept) => concept.dataset.status === verdict).length,
            ]));
            summary.textContent = shown + " shown · " + counts.keep + " Keep · " + counts.iterate + " Iterate · "
                + counts.drop + " Drop · " + counts.unreviewed + " unreviewed";
            empty.dataset.visible = String(shown === 0);
        }

        concepts.forEach((concept) => {
            hydrate(concept);
            concept.querySelectorAll("[data-verdict]").forEach((button) => {
                button.addEventListener("click", () => {
                    const identity = concept.dataset.identity;
                    saved[identity] = { ...normalizeState(saved[identity]), verdict: button.dataset.verdict };
                    persist();
                    hydrate(concept);
                    updateView();
                });
            });
            concept.querySelector("[data-note]").addEventListener("input", (event) => {
                const identity = concept.dataset.identity;
                saved[identity] = { ...normalizeState(saved[identity]), note: event.target.value };
                persist();
            });
            concept.querySelectorAll(".frame").forEach((button) => {
                button.addEventListener("click", () => {
                    const image = button.querySelector("img");
                    dialogImage.src = image.src;
                    dialogImage.alt = image.alt;
                    dialogLabel.textContent = image.alt;
                    dialog.showModal();
                });
            });
        });

        [search, formatFilter, statusFilter].forEach((control) => control.addEventListener("input", updateView));
        document.querySelector("[data-close]").addEventListener("click", () => dialog.close());
        dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });

        function portableRecord() {
            const entries = Object.entries(saved)
                .sort(([left], [right]) => left.localeCompare(right))
                .map(([identity, state]) => [identity, normalizeState(state)]);
            const decisions = Object.fromEntries(entries);
            return { schemaVersion: 1, campaignId, decisions };
        }

        document.querySelector("[data-copy]").addEventListener("click", async (event) => {
            const lines = ["# " + reviewTitle + " decisions", ""];
            concepts.forEach((concept, index) => {
                const identity = concept.dataset.identity;
                const state = normalizeState(saved[identity]);
                const origin = conceptData[identity];
                lines.push(String(index + 1).padStart(2, "0") + ". [" + state.verdict.toUpperCase() + "] " + origin.title);
                lines.push("   Task: " + origin.taskId);
                lines.push("   Seed: " + origin.seed);
                lines.push("   Feature: " + origin.feature);
                lines.push("   Note: " + (state.note.trim().replaceAll("\\n", " ") || "—"));
            });
            try {
                await navigator.clipboard.writeText(lines.join("\\n"));
                const original = event.currentTarget.textContent;
                event.currentTarget.textContent = "Copied";
                setTimeout(() => { event.currentTarget.textContent = original; }, 1400);
            } catch {
                event.currentTarget.textContent = "Clipboard unavailable";
            }
        });

        document.querySelector("[data-export]").addEventListener("click", () => {
            const blob = new Blob([JSON.stringify(portableRecord(), null, 2) + "\\n"], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = campaignId + "-decisions.json";
            link.click();
            URL.revokeObjectURL(url);
        });

        const importFile = document.querySelector("[data-import-file]");
        document.querySelector("[data-import]").addEventListener("click", () => importFile.click());
        importFile.addEventListener("change", async () => {
            const file = importFile.files?.[0];
            if (!file) return;
            try {
                const incoming = JSON.parse(await file.text());
                if (incoming.schemaVersion !== 1 || incoming.campaignId !== campaignId || !incoming.decisions || typeof incoming.decisions !== "object") {
                    throw new Error("This decision file belongs to a different campaign or schema.");
                }
                for (const [identity, state] of Object.entries(incoming.decisions)) saved[identity] = normalizeState(state);
                persist();
                concepts.forEach(hydrate);
                updateView();
            } catch (error) {
                alert(error.message);
            } finally {
                importFile.value = "";
            }
        });

        persist();
        updateView();
    </script>
</body>
</html>\n`;
}

const options = parseArguments(process.argv.slice(2));
const manifestPath = resolve(options.manifest);
const outputPath = resolve(options.output);
const { campaign, concepts } = verifyManifest(loadJson(manifestPath, "manifest"), manifestPath);
const decisions = normalizedDecisions(options.decisions ? loadJson(resolve(options.decisions), "decisions") : null, campaign.id);

try {
    writeFileSync(outputPath, renderBoard(campaign, concepts, decisions), "utf8");
} catch (error) {
    fail(`cannot write review board at ${outputPath}: ${error.message}`);
}

console.log(`review-board: wrote ${outputPath}`);
const frameCount = concepts.reduce((count, concept) => count + concept.frames.length, 0);
console.log(`review-board: ${concepts.length} concepts, ${frameCount} embedded frames, ${Object.keys(decisions).length} imported decisions`);
