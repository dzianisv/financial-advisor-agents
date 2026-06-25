#!/usr/bin/env bun
// Portfolio-memory write — reuses OpenClaw's evergreen-overwrite model.
//
// Two writes per verdict:
//   1. Canonical UPSERT into .agents/memory/positions.md — one line per <desk>:<TICKER>.
//      If a line for this key exists it is REPLACED, else appended. This is the supersede
//      mechanism: it is enforced by code (the line is overwritten), not by asking the agent
//      to remember to cross out the old note. Evergreen file => never decays => always
//      surfaces as the current stance. Solves the COIN "two contradictory same-day notes" bug.
//   2. Append a compact, greppable verdict line to the dated log .agents/memory/<date>.md —
//      episodic history that decays by filename date (newer outranks older on recall).
//
// Usage:
//   bun remember.ts --desk stocks --ticker COIN --verdict HOLD --date 2026-06-24 \
//     --conviction 3 --body "crypto bullish; rev -30.8%; below 200d -36%; fwd PE 30"

import { readFileSync, writeFileSync, existsSync, appendFileSync } from "node:fs";
import path from "node:path";

function opt(name: string, def = ""): string {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def;
}

const desk = opt("desk", "stocks");
const ticker = opt("ticker").toUpperCase();
const verdict = opt("verdict").toUpperCase();
const date = opt("date") || new Date().toISOString().slice(0, 10);
const conviction = opt("conviction");
const body = opt("body").replace(/\n/g, " ").trim();
const memDir = opt("dir", ".agents/memory");

if (!ticker || !verdict) {
  console.error("remember.ts: --ticker and --verdict are required");
  process.exit(1);
}

const key = `${desk}:${ticker}`;
const conv = conviction ? `conv ${conviction}/5` : "";
const line = `${key} | ${verdict} | ${date} | ${conv} | ${body}`.replace(/\| {2,}/g, "| ").trim();

// --- 1. Canonical UPSERT (overwrite the one line for this desk:ticker) ------
const positionsFile = path.join(memDir, "positions.md");
const header =
  "# Portfolio canonical stances — evergreen, never decays; latest write wins per <desk>:<TICKER>.\n" +
  "# format: <desk>:<TICKER> | <VERDICT> | <date> | <conviction> | <one-line thesis>\n";
let lines = existsSync(positionsFile)
  ? readFileSync(positionsFile, "utf8").split("\n")
  : header.split("\n");
const keyPrefix = `${key} |`;
const idx = lines.findIndex((l) => l.startsWith(keyPrefix));
if (idx >= 0) {
  lines[idx] = line; // SUPERSEDE: replace prior stance
} else {
  if (lines.length && lines[lines.length - 1].trim() === "") lines.pop();
  lines.push(line);
}
writeFileSync(positionsFile, lines.join("\n").replace(/\n+$/, "") + "\n");

// --- 2. Append to dated episodic log ---------------------------------------
const datedFile = path.join(memDir, `${date}.md`);
const datedLine = `- ${ticker} ${verdict}${conv ? ` (${conv})` : ""} — ${body}`;
if (!existsSync(datedFile)) {
  writeFileSync(datedFile, `# ${date}\n\n## verdicts\n${datedLine}\n`);
} else {
  const txt = readFileSync(datedFile, "utf8");
  if (txt.includes("## verdicts")) {
    appendFileSync(datedFile, `${datedLine}\n`);
  } else {
    appendFileSync(datedFile, `\n## verdicts\n${datedLine}\n`);
  }
}

console.log(`remembered ${key} = ${verdict} (${date}) -> ${positionsFile} [${idx >= 0 ? "superseded" : "new"}] + ${datedFile}`);
