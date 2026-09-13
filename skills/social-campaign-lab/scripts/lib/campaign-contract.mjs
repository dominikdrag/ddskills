import { createHash } from "node:crypto";
import {
    copyFileSync,
    existsSync,
    mkdirSync,
    readFileSync,
    renameSync,
    rmSync,
    statSync,
    writeFileSync,
} from "node:fs";
import { basename, dirname, isAbsolute, relative, resolve, sep } from "node:path";
import { readPng } from "./png.mjs";

const SHA256_PATTERN = /^[a-f0-9]{64}$/;

function loadJson(path, label) {
    try {
        return JSON.parse(readFileSync(path, "utf8"));
    } catch (error) {
        throw new Error(`cannot read ${label} at ${path}: ${error.message}`);
    }
}

function requiredString(value, label) {
    if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be a non-empty string`);
    return value.trim();
}

function requiredSha256(value, label) {
    const digest = requiredString(value, label);
    if (!SHA256_PATTERN.test(digest)) throw new Error(`${label} must be a lowercase SHA-256 digest`);
    return digest;
}

function sha256Bytes(bytes) {
    return createHash("sha256").update(bytes).digest("hex");
}

export function sha256File(path) {
    return sha256Bytes(readFileSync(path));
}

function assertFile(path, label) {
    try {
        if (!statSync(path).isFile()) throw new Error("not a file");
    } catch (error) {
        throw new Error(`${label} is not a readable file at ${path}: ${error.message}`);
    }
}

function assertDirectory(path, label) {
    try {
        if (!statSync(path).isDirectory()) throw new Error("not a directory");
    } catch (error) {
        throw new Error(`${label} is not a readable directory at ${path}: ${error.message}`);
    }
}

function resolveInside(root, child, label) {
    const value = requiredString(child, label);
    if (isAbsolute(value)) throw new Error(`${label} must be relative`);
    const path = resolve(root, value);
    const relation = relative(root, path);
    if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
        throw new Error(`${label} escapes its owning directory: ${value}`);
    }
    return path;
}

function checkedRect(value, label, bounds) {
    if (!value || typeof value !== "object") throw new Error(`${label} must be a rectangle`);
    const rect = {};
    for (const key of ["x", "y", "width", "height"]) {
        if (!Number.isInteger(value[key]) || value[key] < 0 || (["width", "height"].includes(key) && value[key] === 0)) {
            throw new Error(`${label}.${key} must be ${["width", "height"].includes(key) ? "a positive" : "a non-negative"} integer`);
        }
        rect[key] = value[key];
    }
    if (rect.x + rect.width > bounds.width || rect.y + rect.height > bounds.height) {
        throw new Error(`${label} exceeds ${bounds.width}x${bounds.height} bounds`);
    }
    return rect;
}

function contains(outer, inner) {
    return inner.x >= outer.x
        && inner.y >= outer.y
        && inner.x + inner.width <= outer.x + outer.width
        && inner.y + inner.height <= outer.y + outer.height;
}

function verifyDigest(path, expected, label) {
    const actual = sha256File(path);
    if (actual !== expected) throw new Error(`${label} SHA-256 drift: expected ${expected}, found ${actual}`);
}

function normalizedTokenMap(raw, label, validateValue) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw) || Object.keys(raw).length === 0) {
        throw new Error(`${label} must define at least one token`);
    }
    return Object.fromEntries(Object.entries(raw).sort(([left], [right]) => left.localeCompare(right)).map(([rawName, rawValue]) => {
        const name = requiredString(rawName, `${label} token name`);
        const value = requiredString(rawValue, `${label}.${name}`);
        if (!validateValue(value)) throw new Error(`${label}.${name} has an invalid value: ${value}`);
        return [name, value];
    }));
}

function validateVisualAuthority(path) {
    const raw = loadJson(path, "visual authority");
    if (raw?.schemaVersion !== 1) throw new Error("visual authority must use schemaVersion 1");
    const root = dirname(path);
    const id = requiredString(raw.id, "visualAuthority.id");
    const canvas = raw.canvas;
    if (canvas?.width !== 1080 || canvas?.height !== 1350 || canvas?.colorSpace !== "srgb") {
        throw new Error("visualAuthority.canvas must be 1080x1350 in srgb");
    }
    const safeArea = checkedRect(raw.safeArea, "visualAuthority.safeArea", canvas);
    const colors = normalizedTokenMap(raw.brand?.colors, "visualAuthority.brand.colors", (value) => /^#[A-Fa-f0-9]{6}$/.test(value));
    const fonts = normalizedTokenMap(raw.brand?.fonts, "visualAuthority.brand.fonts", () => true);

    if (!Array.isArray(raw.incumbentPosts) || raw.incumbentPosts.length === 0) {
        throw new Error("visualAuthority.incumbentPosts must contain at least one approved post");
    }
    const incumbents = raw.incumbentPosts.map((item, index) => {
        const label = `visualAuthority.incumbentPosts[${index}]`;
        const itemPath = resolve(root, requiredString(item?.path, `${label}.path`));
        const digest = requiredSha256(item?.sha256, `${label}.sha256`);
        assertFile(itemPath, label);
        verifyDigest(itemPath, digest, label);
        const image = readPng(itemPath, label);
        if (image.width !== canvas.width || image.height !== canvas.height || image.colorType !== 2) {
            throw new Error(`${label} must be a 1080x1350 8-bit RGB feed PNG`);
        }
        return { path: requiredString(item.path, `${label}.path`), sha256: digest };
    });

    if (!Array.isArray(raw.appCaptures)) throw new Error("visualAuthority.appCaptures must be an array");
    const captureIds = new Set();
    const captures = raw.appCaptures.map((item, index) => {
        const label = `visualAuthority.appCaptures[${index}]`;
        const captureId = requiredString(item?.id, `${label}.id`);
        if (captureIds.has(captureId)) throw new Error(`duplicate app capture id: ${captureId}`);
        captureIds.add(captureId);
        const itemPath = resolve(root, requiredString(item?.path, `${label}.path`));
        const digest = requiredSha256(item?.sha256, `${label}.sha256`);
        assertFile(itemPath, label);
        verifyDigest(itemPath, digest, label);
        const image = readPng(itemPath, label);
        const protectedRect = checkedRect(item?.protectedRect, `${label}.protectedRect`, image);
        return { id: captureId, path: itemPath, sourcePath: item.path, sha256: digest, protectedRect, image };
    });

    return {
        id,
        path,
        sha256: sha256File(path),
        canvas,
        safeArea,
        brand: { colors, fonts },
        incumbents,
        captures,
        captureById: new Map(captures.map((capture) => [capture.id, capture])),
    };
}

function checkedTokenNames(raw, allowed, label) {
    if (!Array.isArray(raw) || raw.length === 0) throw new Error(`${label} must contain at least one authority token name`);
    const names = raw.map((value, index) => requiredString(value, `${label}[${index}]`));
    if (new Set(names).size !== names.length) throw new Error(`${label} contains duplicate token names`);
    for (const name of names) {
        if (!Object.hasOwn(allowed, name)) throw new Error(`${label} uses unapproved token ${name}`);
    }
    return [...names].sort();
}

function validatePlacement(raw, label, authority, output) {
    const captureId = requiredString(raw?.captureId, `${label}.captureId`);
    const capture = authority.captureById.get(captureId);
    if (!capture) throw new Error(`${label} refers to unknown app capture ${captureId}`);
    const sourceRect = checkedRect(raw.sourceRect, `${label}.sourceRect`, capture.image);
    const destination = raw.destination;
    if (!destination || !Number.isInteger(destination.x) || !Number.isInteger(destination.y)
        || destination.x < 0 || destination.y < 0) {
        throw new Error(`${label}.destination must contain non-negative integer x and y`);
    }
    const destinationRect = { x: destination.x, y: destination.y, width: sourceRect.width, height: sourceRect.height };
    if (!contains({ x: 0, y: 0, width: output.width, height: output.height }, destinationRect)) {
        throw new Error(`${label} is cropped by the output canvas`);
    }
    if (!contains(sourceRect, capture.protectedRect)) {
        throw new Error(`${label}.sourceRect cuts protected app content`);
    }
    const placedProtectedRect = {
        x: destination.x + capture.protectedRect.x - sourceRect.x,
        y: destination.y + capture.protectedRect.y - sourceRect.y,
        width: capture.protectedRect.width,
        height: capture.protectedRect.height,
    };
    if (!contains(authority.safeArea, placedProtectedRect)) {
        throw new Error(`${label} places protected app content outside the campaign safe area`);
    }

    for (let y = 0; y < sourceRect.height; y += 1) {
        for (let x = 0; x < sourceRect.width; x += 1) {
            const sourceOffset = ((sourceRect.y + y) * capture.image.width + sourceRect.x + x) * capture.image.channels;
            const outputOffset = ((destination.y + y) * output.width + destination.x + x) * output.channels;
            if (capture.image.pixels[sourceOffset] !== output.pixels[outputOffset]
                || capture.image.pixels[sourceOffset + 1] !== output.pixels[outputOffset + 1]
                || capture.image.pixels[sourceOffset + 2] !== output.pixels[outputOffset + 2]) {
                throw new Error(`${label} alters app pixels at source (${sourceRect.x + x},${sourceRect.y + y})`);
            }
        }
    }
    return { captureId, sourceRect, destination: { x: destination.x, y: destination.y } };
}

function validateRenderManifest(path, concept, authority, campaignId) {
    const raw = loadJson(path, `${concept.label}.renderManifest`);
    if (raw?.schemaVersion !== 1) throw new Error(`${concept.label}.renderManifest must use schemaVersion 1`);
    if (raw.campaignId !== campaignId) throw new Error(`${concept.label}.renderManifest campaignId does not match campaign.id`);
    const authorityDigest = requiredSha256(raw.visualAuthoritySha256, `${concept.label}.renderManifest.visualAuthoritySha256`);
    if (authorityDigest !== authority.sha256) throw new Error(`${concept.label}.renderManifest uses a different visual authority revision`);
    const rendererDigest = requiredSha256(raw.rendererSha256, `${concept.label}.renderManifest.rendererSha256`);
    verifyDigest(concept.rendererPath, rendererDigest, `${concept.label}.render.mjs`);
    if (!Array.isArray(raw.frames) || raw.frames.length !== concept.framePaths.length) {
        throw new Error(`${concept.label}.renderManifest.frames must exactly match concept frames`);
    }

    return raw.frames.map((rawFrame, index) => {
        const label = `${concept.label}.renderManifest.frames[${index}]`;
        if (rawFrame?.path !== concept.frameNames[index]) throw new Error(`${label}.path does not match campaign frame order`);
        const digest = requiredSha256(rawFrame.sha256, `${label}.sha256`);
        verifyDigest(concept.framePaths[index], digest, label);
        const output = readPng(concept.framePaths[index], label);
        if (output.width !== authority.canvas.width || output.height !== authority.canvas.height || output.colorType !== 2) {
            throw new Error(`${label} must be a 1080x1350 8-bit RGB feed PNG`);
        }
        const brandTokens = {
            colors: checkedTokenNames(rawFrame.brandTokens?.colors, authority.brand.colors, `${label}.brandTokens.colors`),
            fonts: checkedTokenNames(rawFrame.brandTokens?.fonts, authority.brand.fonts, `${label}.brandTokens.fonts`),
        };
        if (typeof rawFrame.containsAppUI !== "boolean") throw new Error(`${label}.containsAppUI must be true or false`);
        if (!Array.isArray(rawFrame.appCapturePlacements)) throw new Error(`${label}.appCapturePlacements must be an array`);
        if (rawFrame.containsAppUI && rawFrame.appCapturePlacements.length === 0) {
            throw new Error(`${label} declares visible app UI without an authority capture placement`);
        }
        if (!rawFrame.containsAppUI && rawFrame.appCapturePlacements.length > 0) {
            throw new Error(`${label} records app capture placements but containsAppUI is false`);
        }
        const placements = rawFrame.appCapturePlacements.map((placement, placementIndex) => validatePlacement(
            placement,
            `${label}.appCapturePlacements[${placementIndex}]`,
            authority,
            output,
        ));
        return { path: concept.frameNames[index], sha256: digest, brandTokens, containsAppUI: rawFrame.containsAppUI, placements };
    });
}

function normalizedFormat(value, frameCount, label) {
    const format = requiredString(value, `${label}.format`);
    if (!["single", "carousel"].includes(format)) throw new Error(`${label}.format must be single or carousel`);
    if ((format === "single" && frameCount !== 1) || (format === "carousel" && frameCount < 2)) {
        throw new Error(`${label}.frames does not match format ${format}`);
    }
    return format;
}

export function validateCampaign(manifestInput) {
    const manifestPath = resolve(manifestInput);
    const raw = loadJson(manifestPath, "campaign manifest");
    if (raw?.schemaVersion !== 2 || !raw.campaign || !Array.isArray(raw.concepts) || raw.concepts.length === 0) {
        throw new Error("campaign manifest must use schemaVersion 2 and contain campaign plus concepts");
    }
    const manifestRoot = dirname(manifestPath);
    const campaign = {
        id: requiredString(raw.campaign.id, "campaign.id"),
        title: requiredString(raw.campaign.title, "campaign.title"),
        brief: requiredString(raw.campaign.brief, "campaign.brief"),
        reference: requiredString(raw.campaign.reference, "campaign.reference"),
    };
    if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(campaign.id)) {
        throw new Error("campaign.id may contain only letters, digits, dots, underscores, and hyphens");
    }
    const authorityPath = resolve(manifestRoot, requiredString(raw.campaign.visualAuthority, "campaign.visualAuthority"));
    assertFile(authorityPath, "campaign.visualAuthority");
    const authority = validateVisualAuthority(authorityPath);
    const identities = new Set();
    const taskSeeds = new Set();
    const postingOrders = new Set();

    const concepts = raw.concepts.map((rawConcept, index) => {
        const label = `concepts[${index}]`;
        const taskId = requiredString(rawConcept.taskId, `${label}.taskId`);
        const seed = requiredString(rawConcept.seed, `${label}.seed`);
        if (!/^[a-z0-9]{10}$/.test(seed)) throw new Error(`${label}.seed must be 10 lowercase alphanumeric characters`);
        const pair = `${taskId}::${seed}`;
        if (taskSeeds.has(pair)) throw new Error(`duplicate taskId and seed pair: ${pair}`);
        taskSeeds.add(pair);
        const identity = `${campaign.id}::${pair}`;
        if (identities.has(identity)) throw new Error(`duplicate concept identity: ${identity}`);
        identities.add(identity);

        if (!Array.isArray(rawConcept.frames) || rawConcept.frames.length === 0) throw new Error(`${label}.frames must be a non-empty array`);
        const sourceDirValue = requiredString(rawConcept.sourceDir, `${label}.sourceDir`);
        const sourceDir = resolve(manifestRoot, sourceDirValue);
        assertDirectory(sourceDir, `${label}.sourceDir`);
        const artifactPaths = Object.fromEntries(["concept.md", "caption.md", "render.mjs"].map((name) => {
            const path = resolveInside(sourceDir, name, `${label}.${name}`);
            assertFile(path, `${label}.${name}`);
            return [name, path];
        }));
        const frameNames = rawConcept.frames.map((frame, frameIndex) => requiredString(frame, `${label}.frames[${frameIndex}]`));
        const framePaths = frameNames.map((frame, frameIndex) => {
            const path = resolveInside(sourceDir, frame, `${label}.frames[${frameIndex}]`);
            assertFile(path, `${label}.frames[${frameIndex}]`);
            return path;
        });
        const renderManifestName = requiredString(rawConcept.renderManifest, `${label}.renderManifest`);
        const renderManifestPath = resolveInside(sourceDir, renderManifestName, `${label}.renderManifest`);
        assertFile(renderManifestPath, `${label}.renderManifest`);
        let postingOrder = null;
        if (rawConcept.postingOrder !== undefined) {
            if (!Number.isInteger(rawConcept.postingOrder) || rawConcept.postingOrder <= 0) {
                throw new Error(`${label}.postingOrder must be a positive integer`);
            }
            postingOrder = rawConcept.postingOrder;
            if (postingOrders.has(postingOrder)) throw new Error(`duplicate postingOrder: ${postingOrder}`);
            postingOrders.add(postingOrder);
        }
        const concept = {
            label,
            identity,
            taskId,
            seed,
            title: requiredString(rawConcept.title, `${label}.title`),
            feature: requiredString(rawConcept.feature, `${label}.feature`),
            benefit: requiredString(rawConcept.benefit, `${label}.benefit`),
            approach: requiredString(rawConcept.approach, `${label}.approach`),
            assetStatus: requiredString(rawConcept.assetStatus ?? "ready", `${label}.assetStatus`),
            format: normalizedFormat(rawConcept.format, framePaths.length, label),
            postingOrder,
            sourceDir,
            sourceDirValue,
            rendererPath: artifactPaths["render.mjs"],
            captionPath: artifactPaths["caption.md"],
            frameNames,
            framePaths,
            renderManifestName,
        };
        concept.frames = validateRenderManifest(renderManifestPath, concept, authority, campaign.id);
        return concept;
    });

    const frameCount = concepts.reduce((total, concept) => total + concept.frames.length, 0);
    const capturePlacementCount = concepts.reduce((total, concept) => total
        + concept.frames.reduce((frameTotal, frame) => frameTotal + frame.placements.length, 0), 0);
    const report = {
        schemaVersion: 1,
        campaignId: campaign.id,
        visualAuthority: { id: authority.id, sha256: authority.sha256 },
        concepts: concepts.length,
        frames: frameCount,
        incumbentPosts: authority.incumbents.length,
        appCaptures: authority.captures.length,
        exactAppPixelPlacements: capturePlacementCount,
        result: "pass",
    };
    return { manifestPath, raw, campaign, authority, concepts, report };
}

function validateDecisions(path, campaignId) {
    const raw = loadJson(path, "decisions");
    if (raw?.schemaVersion !== 1 || raw.campaignId !== campaignId || !raw.decisions || typeof raw.decisions !== "object") {
        throw new Error("decisions must use schemaVersion 1 and match campaign.id");
    }
    // The review board intentionally retains decisions for concepts removed in later rounds.
    for (const [identity, state] of Object.entries(raw.decisions)) {
        if (!state || !["unreviewed", "keep", "iterate", "drop"].includes(state.verdict) || typeof state.note !== "string") {
            throw new Error(`invalid decision state for ${identity}`);
        }
    }
    return raw.decisions;
}

function slug(value, fallback) {
    const result = value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
        .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 64).replace(/-$/g, "");
    return result || fallback;
}

function writeJson(path, value) {
    writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function postingPackReadme(campaign, posts) {
    const lines = [
        `# ${campaign.title} posting pack`,
        "",
        "Approved assets for manual posting. This directory is not evidence that anything was scheduled or published.",
        "",
        "## Upload order",
        "",
    ];
    for (const post of posts) {
        lines.push(`${post.order}. **${post.title}** — \`${post.directory}/\` (${post.frames.length} frame${post.frames.length === 1 ? "" : "s"})`);
    }
    lines.push("", "Byte hashes and source identities are recorded in `posting-pack.json`.", "");
    return lines.join("\n");
}

export function assemblePostingPack(manifestInput, decisionsInput, outputInput) {
    const validated = validateCampaign(manifestInput);
    const decisionsPath = resolve(decisionsInput);
    const decisions = validateDecisions(decisionsPath, validated.campaign.id);
    const unresolved = [];
    const kept = [];
    for (const concept of validated.concepts) {
        const verdict = decisions[concept.identity]?.verdict ?? "unreviewed";
        if (!["unreviewed", "keep", "iterate", "drop"].includes(verdict)) throw new Error(`invalid verdict for ${concept.identity}`);
        if (verdict === "unreviewed" || verdict === "iterate") unresolved.push(`${concept.identity} (${verdict})`);
        if (verdict === "keep") kept.push(concept);
    }
    if (unresolved.length > 0) throw new Error(`cannot assemble with unresolved concepts: ${unresolved.join(", ")}`);
    if (kept.length === 0) throw new Error("cannot assemble a posting pack without Keep decisions");
    for (const concept of kept) {
        if (concept.postingOrder === null) throw new Error(`${concept.identity} needs postingOrder before assembly`);
    }
    kept.sort((left, right) => left.postingOrder - right.postingOrder || left.identity.localeCompare(right.identity));

    const outputPath = resolve(outputInput);
    if (existsSync(outputPath)) throw new Error(`output already exists: ${outputPath}`);
    const outputParent = dirname(outputPath);
    mkdirSync(outputParent, { recursive: true });
    const temporaryPath = resolve(outputParent, `.${basename(outputPath)}.tmp-${process.pid}`);
    if (existsSync(temporaryPath)) throw new Error(`temporary output already exists: ${temporaryPath}`);
    mkdirSync(temporaryPath);

    const width = Math.max(2, String(kept.length).length);
    const posts = [];
    try {
        for (let index = 0; index < kept.length; index += 1) {
            const concept = kept[index];
            const order = String(index + 1).padStart(width, "0");
            const directory = `${order}-${slug(concept.title, concept.seed)}`;
            const destination = resolve(temporaryPath, directory);
            mkdirSync(destination);
            const captionDestination = resolve(destination, "caption.md");
            const captionDigest = sha256File(concept.captionPath);
            copyFileSync(concept.captionPath, captionDestination);
            verifyDigest(captionDestination, captionDigest, `${concept.identity} copied caption`);
            const frames = concept.framePaths.map((source, frameIndex) => {
                const name = `${String(frameIndex + 1).padStart(2, "0")}.png`;
                const frameDestination = resolve(destination, name);
                copyFileSync(source, frameDestination);
                verifyDigest(frameDestination, concept.frames[frameIndex].sha256, `${concept.identity} copied frame ${frameIndex + 1}`);
                return {
                    file: `${directory}/${name}`,
                    sha256: concept.frames[frameIndex].sha256,
                    source: `${concept.sourceDirValue}/${concept.frameNames[frameIndex]}`,
                };
            });
            posts.push({
                order: index + 1,
                postingOrder: concept.postingOrder,
                title: concept.title,
                directory,
                identity: concept.identity,
                taskId: concept.taskId,
                seed: concept.seed,
                caption: {
                    file: `${directory}/caption.md`,
                    sha256: captionDigest,
                    source: `${concept.sourceDirValue}/caption.md`,
                },
                frames,
            });
        }
        const provenance = {
            schemaVersion: 1,
            campaign: {
                id: validated.campaign.id,
                title: validated.campaign.title,
                manifestSha256: sha256File(validated.manifestPath),
            },
            visualAuthority: {
                id: validated.authority.id,
                sha256: validated.authority.sha256,
                source: relative(dirname(validated.manifestPath), validated.authority.path) || basename(validated.authority.path),
            },
            decisionsSha256: sha256File(decisionsPath),
            posts,
        };
        writeFileSync(resolve(temporaryPath, "README.md"), postingPackReadme(validated.campaign, posts), "utf8");
        writeJson(resolve(temporaryPath, "posting-pack.json"), provenance);
        writeJson(resolve(temporaryPath, "validation-report.json"), validated.report);
        renameSync(temporaryPath, outputPath);
        return { outputPath, posts: posts.length, frames: posts.reduce((total, post) => total + post.frames.length, 0), report: validated.report };
    } catch (error) {
        rmSync(temporaryPath, { recursive: true, force: true });
        throw error;
    }
}

export function writeValidationReport(path, report) {
    writeJson(resolve(path), report);
}
