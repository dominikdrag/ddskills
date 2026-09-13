#!/usr/bin/env node

import { assemblePostingPack, validateCampaign, writeValidationReport } from "./lib/campaign-contract.mjs";

function usage() {
    console.log(`Usage:
  node campaign-assets.mjs validate --manifest <file> [--report <file>]
  node campaign-assets.mjs assemble --manifest <file> --decisions <file> --output <directory>`);
}

function fail(message) {
    console.error(`campaign-assets: ${message}`);
    process.exit(1);
}

function parseArguments(argv) {
    const command = argv[0];
    if (command === "--help" || command === "-h" || !command) {
        usage();
        process.exit(command ? 0 : 1);
    }
    if (!["validate", "assemble"].includes(command)) fail(`unknown command ${command}`);
    const options = {};
    for (let index = 1; index < argv.length; index += 1) {
        const flag = argv[index];
        if (flag === "--help" || flag === "-h") {
            usage();
            process.exit(0);
        }
        if (!["--manifest", "--report", "--decisions", "--output"].includes(flag)) fail(`unknown argument ${flag}`);
        const value = argv[index + 1];
        if (!value || value.startsWith("--")) fail(`${flag} requires a value`);
        options[flag.slice(2)] = value;
        index += 1;
    }
    if (!options.manifest) fail("--manifest is required");
    if (command === "validate" && (options.decisions || options.output)) fail("validate accepts only --manifest and --report");
    if (command === "assemble" && (!options.decisions || !options.output || options.report)) {
        fail("assemble requires --manifest, --decisions, and --output");
    }
    return { command, options };
}

try {
    const { command, options } = parseArguments(process.argv.slice(2));
    if (command === "validate") {
        const { report } = validateCampaign(options.manifest);
        if (options.report) writeValidationReport(options.report, report);
        console.log(`campaign-assets: PASS ${report.concepts} concepts, ${report.frames} frames, ${report.exactAppPixelPlacements} exact app-pixel placements`);
        if (options.report) console.log(`campaign-assets: wrote ${options.report}`);
    } else {
        const result = assemblePostingPack(options.manifest, options.decisions, options.output);
        console.log(`campaign-assets: PASS assembled ${result.posts} posts and ${result.frames} frames`);
        console.log(`campaign-assets: wrote ${result.outputPath}`);
    }
} catch (error) {
    fail(error.message);
}
