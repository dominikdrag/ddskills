import { readFileSync } from "node:fs";
import { inflateSync } from "node:zlib";

const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
const CRC_TABLE = Array.from({ length: 256 }, (_, value) => {
    let checksum = value;
    for (let bit = 0; bit < 8; bit += 1) {
        checksum = (checksum & 1) ? 0xedb88320 ^ (checksum >>> 1) : checksum >>> 1;
    }
    return checksum >>> 0;
});

export function crc32(bytes) {
    let checksum = 0xffffffff;
    for (const byte of bytes) checksum = CRC_TABLE[(checksum ^ byte) & 0xff] ^ (checksum >>> 8);
    return (checksum ^ 0xffffffff) >>> 0;
}

function paeth(left, above, upperLeft) {
    const estimate = left + above - upperLeft;
    const leftDistance = Math.abs(estimate - left);
    const aboveDistance = Math.abs(estimate - above);
    const upperLeftDistance = Math.abs(estimate - upperLeft);
    if (leftDistance <= aboveDistance && leftDistance <= upperLeftDistance) return left;
    return aboveDistance <= upperLeftDistance ? above : upperLeft;
}

function decodeRows(compressed, width, height, channels, label) {
    let filtered;
    try {
        filtered = inflateSync(compressed);
    } catch (error) {
        throw new Error(`${label} has invalid compressed image data: ${error.message}`);
    }
    const stride = width * channels;
    const rowLength = stride + 1;
    if (filtered.length !== rowLength * height) {
        throw new Error(`${label} has an invalid decoded byte count`);
    }
    const pixels = Buffer.alloc(stride * height);
    for (let y = 0; y < height; y += 1) {
        const filter = filtered[y * rowLength];
        if (filter > 4) throw new Error(`${label} has an invalid PNG row filter`);
        const sourceOffset = y * rowLength + 1;
        const outputOffset = y * stride;
        for (let x = 0; x < stride; x += 1) {
            const raw = filtered[sourceOffset + x];
            const left = x >= channels ? pixels[outputOffset + x - channels] : 0;
            const above = y > 0 ? pixels[outputOffset + x - stride] : 0;
            const upperLeft = y > 0 && x >= channels ? pixels[outputOffset + x - stride - channels] : 0;
            let prediction = 0;
            if (filter === 1) prediction = left;
            if (filter === 2) prediction = above;
            if (filter === 3) prediction = Math.floor((left + above) / 2);
            if (filter === 4) prediction = paeth(left, above, upperLeft);
            pixels[outputOffset + x] = (raw + prediction) & 0xff;
        }
    }
    return pixels;
}

export function readPng(path, label = path) {
    let bytes;
    try {
        bytes = readFileSync(path);
    } catch (error) {
        throw new Error(`cannot read ${label} at ${path}: ${error.message}`);
    }
    if (bytes.length < 45 || !bytes.subarray(0, 8).equals(PNG_SIGNATURE)) {
        throw new Error(`${label} is not a PNG`);
    }

    let header;
    const idatChunks = [];
    let offset = 8;
    let chunkIndex = 0;
    let sawIend = false;
    while (offset < bytes.length) {
        if (offset + 12 > bytes.length) throw new Error(`${label} has a truncated PNG chunk`);
        const length = bytes.readUInt32BE(offset);
        const end = offset + 12 + length;
        if (end > bytes.length) throw new Error(`${label} has a truncated PNG chunk payload`);
        const typeBytes = bytes.subarray(offset + 4, offset + 8);
        const type = typeBytes.toString("ascii");
        const data = bytes.subarray(offset + 8, offset + 8 + length);
        const storedCrc = bytes.readUInt32BE(offset + 8 + length);
        if (storedCrc !== crc32(Buffer.concat([typeBytes, data]))) {
            throw new Error(`${label} has a bad ${type} chunk checksum`);
        }
        if (chunkIndex === 0 && (type !== "IHDR" || length !== 13)) {
            throw new Error(`${label} must start with a 13-byte IHDR chunk`);
        }
        if (type === "IHDR") {
            header = {
                width: data.readUInt32BE(0),
                height: data.readUInt32BE(4),
                bitDepth: data[8],
                colorType: data[9],
                compression: data[10],
                filter: data[11],
                interlace: data[12],
            };
        }
        if (type === "IDAT") idatChunks.push(data);
        if (type === "IEND") {
            if (length !== 0 || end !== bytes.length) throw new Error(`${label} has an invalid final IEND chunk`);
            sawIend = true;
        }
        offset = end;
        chunkIndex += 1;
    }
    if (!header || !sawIend || idatChunks.length === 0) {
        throw new Error(`${label} is missing PNG header, image data, or IEND`);
    }
    if (header.bitDepth !== 8 || ![2, 6].includes(header.colorType)) {
        throw new Error(`${label} must be 8-bit RGB or RGBA`);
    }
    if (header.compression !== 0 || header.filter !== 0 || header.interlace !== 0) {
        throw new Error(`${label} must use standard compression/filtering and be non-interlaced`);
    }
    const channels = header.colorType === 2 ? 3 : 4;
    const pixels = decodeRows(Buffer.concat(idatChunks), header.width, header.height, channels, label);
    if (channels === 4) {
        for (let index = 3; index < pixels.length; index += 4) {
            if (pixels[index] !== 255) throw new Error(`${label} must be opaque for exact pixel comparison`);
        }
    }
    return { ...header, channels, bytes, pixels };
}
