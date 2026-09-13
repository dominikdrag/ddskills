import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { deflateSync } from "node:zlib";
import { assemblePostingPack, validateCampaign } from "./lib/campaign-contract.mjs";
import { crc32 } from "./lib/png.mjs";

function sha256(path) {
    return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function pngChunk(type, data) {
    const typeBytes = Buffer.from(type, "ascii");
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    const checksum = Buffer.alloc(4);
    checksum.writeUInt32BE(crc32(Buffer.concat([typeBytes, data])));
    return Buffer.concat([length, typeBytes, data, checksum]);
}

function writeRgbPng(path, width, height, pixels) {
    const header = Buffer.alloc(13);
    header.writeUInt32BE(width, 0);
    header.writeUInt32BE(height, 4);
    header[8] = 8;
    header[9] = 2;
    const rows = Buffer.alloc((width * 3 + 1) * height);
    for (let y = 0; y < height; y += 1) {
        const target = y * (width * 3 + 1);
        rows[target] = 0;
        pixels.copy(rows, target + 1, y * width * 3, (y + 1) * width * 3);
    }
    writeFileSync(path, Buffer.concat([
        Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
        pngChunk("IHDR", header),
        pngChunk("IDAT", deflateSync(rows)),
        pngChunk("IEND", Buffer.alloc(0)),
    ]));
}

function solidPixels(width, height, rgb) {
    const pixels = Buffer.alloc(width * height * 3);
    for (let index = 0; index < pixels.length; index += 3) {
        pixels[index] = rgb[0];
        pixels[index + 1] = rgb[1];
        pixels[index + 2] = rgb[2];
    }
    return pixels;
}

function writeJson(path, value) {
    writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`);
}

function fixture() {
    const root = mkdtempSync(join(tmpdir(), "social-campaign-lab-"));
    const lane = join(root, "seed-lab", "a1b2c3d4e5");
    const frames = join(lane, "out");
    mkdirSync(frames, { recursive: true });
    const incumbentPath = join(root, "incumbent.png");
    const capturePath = join(root, "capture.png");
    const framePath = join(frames, "01.png");
    const rendererPath = join(lane, "render.mjs");
    writeRgbPng(incumbentPath, 1080, 1350, solidPixels(1080, 1350, [30, 31, 32]));
    const capturePixels = Buffer.from([
        200, 10, 20, 201, 11, 21,
        202, 12, 22, 203, 13, 23,
    ]);
    writeRgbPng(capturePath, 2, 2, capturePixels);
    const framePixels = solidPixels(1080, 1350, [244, 240, 232]);
    for (let y = 0; y < 2; y += 1) {
        for (let x = 0; x < 2; x += 1) {
            const source = (y * 2 + x) * 3;
            const target = ((100 + y) * 1080 + 100 + x) * 3;
            capturePixels.copy(framePixels, target, source, source + 3);
        }
    }
    writeRgbPng(framePath, 1080, 1350, framePixels);
    writeFileSync(join(lane, "concept.md"), "# Exact app pixels\n");
    writeFileSync(join(lane, "caption.md"), "A caption.\n");
    writeFileSync(rendererPath, "// deterministic fixture renderer\n");

    const authorityPath = join(root, "visual-authority.json");
    const authority = {
        schemaVersion: 1,
        id: "fixture-authority",
        canvas: { width: 1080, height: 1350, colorSpace: "srgb" },
        safeArea: { x: 50, y: 50, width: 980, height: 1250 },
        brand: {
            colors: { paper: "#F4F0E8", ink: "#201F1B" },
            fonts: { display: "New York", body: "SF Pro" },
        },
        incumbentPosts: [{ path: "incumbent.png", sha256: sha256(incumbentPath) }],
        appCaptures: [{
            id: "morning-board",
            path: "capture.png",
            sha256: sha256(capturePath),
            protectedRect: { x: 0, y: 0, width: 2, height: 2 },
        }],
    };
    writeJson(authorityPath, authority);

    const renderManifestPath = join(lane, "render-manifest.json");
    const renderManifest = {
        schemaVersion: 1,
        campaignId: "fixture-campaign",
        visualAuthoritySha256: sha256(authorityPath),
        rendererSha256: sha256(rendererPath),
        frames: [{
            path: "out/01.png",
            sha256: sha256(framePath),
            brandTokens: { colors: ["paper", "ink"], fonts: ["display", "body"] },
            containsAppUI: true,
            appCapturePlacements: [{
                captureId: "morning-board",
                sourceRect: { x: 0, y: 0, width: 2, height: 2 },
                destination: { x: 100, y: 100 },
            }],
        }],
    };
    writeJson(renderManifestPath, renderManifest);

    const manifestPath = join(root, "campaign.json");
    const manifest = {
        schemaVersion: 2,
        campaign: {
            id: "fixture-campaign",
            title: "Fixture campaign",
            brief: "Verify the campaign contract",
            reference: "incumbent.png",
            visualAuthority: "visual-authority.json",
        },
        concepts: [{
            taskId: "01a00000-0000-7000-8000-000000000001",
            seed: "a1b2c3d4e5",
            title: "Exact app pixels",
            feature: "Morning Board",
            benefit: "Product truth",
            approach: "Captured proof",
            format: "single",
            assetStatus: "ready",
            postingOrder: 10,
            sourceDir: "seed-lab/a1b2c3d4e5",
            renderManifest: "render-manifest.json",
            frames: ["out/01.png"],
        }],
    };
    writeJson(manifestPath, manifest);

    const identity = "fixture-campaign::01a00000-0000-7000-8000-000000000001::a1b2c3d4e5";
    const decisionsPath = join(root, "decisions.json");
    writeJson(decisionsPath, {
        schemaVersion: 1,
        campaignId: "fixture-campaign",
        decisions: { [identity]: { verdict: "keep", note: "" } },
    });
    return {
        root,
        manifestPath,
        decisionsPath,
        authorityPath,
        renderManifestPath,
        framePath,
        framePixels,
        renderManifest,
    };
}

function tree(path) {
    const files = [];
    function visit(directory) {
        for (const entry of readdirSync(directory, { withFileTypes: true }).sort((left, right) => left.name.localeCompare(right.name))) {
            const child = join(directory, entry.name);
            if (entry.isDirectory()) visit(child);
            else files.push([relative(path, child), readFileSync(child)]);
        }
    }
    visit(path);
    return files;
}

test("validates exact app pixels and assembles byte-deterministic posting packs", (t) => {
    const data = fixture();
    t.after(() => rmSync(data.root, { recursive: true, force: true }));
    const validated = validateCampaign(data.manifestPath);
    assert.deepEqual(validated.report, {
        schemaVersion: 1,
        campaignId: "fixture-campaign",
        visualAuthority: { id: "fixture-authority", sha256: sha256(data.authorityPath) },
        concepts: 1,
        frames: 1,
        incumbentPosts: 1,
        appCaptures: 1,
        exactAppPixelPlacements: 1,
        result: "pass",
    });

    const first = join(data.root, "pack-a");
    const second = join(data.root, "pack-b");
    const decisionsWithRetainedHistory = JSON.parse(readFileSync(data.decisionsPath, "utf8"));
    decisionsWithRetainedHistory.decisions["fixture-campaign::removed-task::zzzzzzzzzz"] = { verdict: "drop", note: "Removed in review." };
    writeJson(data.decisionsPath, decisionsWithRetainedHistory);
    assemblePostingPack(data.manifestPath, data.decisionsPath, first);
    assemblePostingPack(data.manifestPath, data.decisionsPath, second);
    const firstTree = tree(first);
    const secondTree = tree(second);
    assert.deepEqual(firstTree.map(([path]) => path), secondTree.map(([path]) => path));
    for (let index = 0; index < firstTree.length; index += 1) assert.ok(firstTree[index][1].equals(secondTree[index][1]));
    assert.ok(readFileSync(join(first, "01-exact-app-pixels", "01.png")).equals(readFileSync(data.framePath)));
    assert.ok(readFileSync(join(first, "01-exact-app-pixels", "caption.md")).equals(readFileSync(join(data.root, "seed-lab", "a1b2c3d4e5", "caption.md"))));

    const reportPath = join(data.root, "cli-report.json");
    const cli = spawnSync(process.execPath, [
        resolve(import.meta.dirname, "campaign-assets.mjs"),
        "validate",
        "--manifest",
        data.manifestPath,
        "--report",
        reportPath,
    ], { encoding: "utf8" });
    assert.equal(cli.status, 0, cli.stderr);
    assert.match(cli.stdout, /PASS 1 concepts, 1 frames, 1 exact app-pixel placements/);
    assert.equal(JSON.parse(readFileSync(reportPath, "utf8")).result, "pass");

    const boardPath = join(data.root, "review-board.html");
    const board = spawnSync(process.execPath, [
        resolve(import.meta.dirname, "build-review-board.mjs"),
        "--manifest",
        data.manifestPath,
        "--output",
        boardPath,
    ], { encoding: "utf8" });
    assert.equal(board.status, 0, board.stderr);
    const boardHtml = readFileSync(boardPath, "utf8");
    assert.match(boardHtml, /Exact app pixels/);
    assert.match(boardHtml, /data:image\/png;base64/);
});

test("rejects altered captured app pixels even when the frame hash is current", (t) => {
    const data = fixture();
    t.after(() => rmSync(data.root, { recursive: true, force: true }));
    data.framePixels[((100 * 1080) + 100) * 3] = 99;
    writeRgbPng(data.framePath, 1080, 1350, data.framePixels);
    data.renderManifest.frames[0].sha256 = sha256(data.framePath);
    writeJson(data.renderManifestPath, data.renderManifest);
    assert.throws(() => validateCampaign(data.manifestPath), /alters app pixels/);
});

test("rejects unsafe app capture crops", (t) => {
    const data = fixture();
    t.after(() => rmSync(data.root, { recursive: true, force: true }));
    data.renderManifest.frames[0].appCapturePlacements[0].sourceRect.width = 1;
    writeJson(data.renderManifestPath, data.renderManifest);
    assert.throws(() => validateCampaign(data.manifestPath), /cuts protected app content/);
});

test("rejects lanes bound to another visual authority revision", (t) => {
    const data = fixture();
    t.after(() => rmSync(data.root, { recursive: true, force: true }));
    data.renderManifest.visualAuthoritySha256 = "0".repeat(64);
    writeJson(data.renderManifestPath, data.renderManifest);
    assert.throws(() => validateCampaign(data.manifestPath), /different visual authority revision/);
});

test("rejects brand tokens outside the shared authority", (t) => {
    const data = fixture();
    t.after(() => rmSync(data.root, { recursive: true, force: true }));
    data.renderManifest.frames[0].brandTokens.colors.push("lane-blue");
    writeJson(data.renderManifestPath, data.renderManifest);
    assert.throws(() => validateCampaign(data.manifestPath), /unapproved token lane-blue/);
});

test("refuses unresolved decisions and existing posting-pack outputs", (t) => {
    const data = fixture();
    t.after(() => rmSync(data.root, { recursive: true, force: true }));
    const decisions = JSON.parse(readFileSync(data.decisionsPath, "utf8"));
    const identity = Object.keys(decisions.decisions)[0];
    decisions.decisions[identity].verdict = "iterate";
    writeJson(data.decisionsPath, decisions);
    assert.throws(() => assemblePostingPack(data.manifestPath, data.decisionsPath, join(data.root, "pack")), /unresolved concepts/);

    decisions.decisions[identity].verdict = "keep";
    writeJson(data.decisionsPath, decisions);
    const output = join(data.root, "pack");
    mkdirSync(output);
    assert.throws(() => assemblePostingPack(data.manifestPath, data.decisionsPath, output), /output already exists/);
});
