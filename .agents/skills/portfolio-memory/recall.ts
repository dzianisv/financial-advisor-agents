#!/usr/bin/env bun
// Portfolio-memory recall — reuses OpenClaw's two-tier memory model.
//
// Tier 1 (canonical / evergreen): .agents/memory/positions.md — one line per
//   <desk>:<TICKER>, overwritten on every new verdict. Never decays. This is the
//   "current stance" surface; latest write always wins by construction (the COIN fix).
// Tier 2 (episodic / dated): .agents/memory/YYYY-MM-DD.md — decays by the date in
//   the filename, so newer notes outrank older ones (recency = newest file first).
//
// Ranking: if the `openclaw` CLI is present AND configured to index .agents/memory
//   (memorySearch.extraPaths), we use its hybrid BM25+vector+temporal-decay+MMR
//   ranker. Otherwise we degrade to grep: canonical lines always shown, dated lines
//   newest-first. The grep path is a deliberate subset — exact-match + recency only.
//
// Usage:
//   bun recall.ts --desk stocks --tickers "AVGO MRVL COIN PYPL" [--q "AI supply chain"] [--k 8]

import { readdirSync, readFileSync, existsSync } from "node:fs";
import path from "node:path";

function opt(name: string, def = ""): string {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def;
}

const desk = opt("desk", "stocks");
const memDir = opt("dir", ".agents/memory");
const tickers = opt("tickers")
  .split(/[\s,]+/)
  .filter(Boolean)
  .map((t) => t.toUpperCase());
const query = opt("q", tickers.join(" ")).trim();
const k = Number(opt("k", "8")) || 8;
const positionsFile = path.join(memDir, "positions.md");

// --- Tier 1: canonical stances (evergreen, never decays) -------------------
function canonicalLines(): string[] {
  if (!existsSync(positionsFile)) return [];
  const lines = readFileSync(positionsFile, "utf8")
    .split("\n")
    .filter((l) => l.trim() && !l.trim().startsWith("#"));
  if (tickers.length === 0) return lines.filter((l) => l.startsWith(`${desk}:`));
  return lines.filter((l) =>
    tickers.some((t) => l.toUpperCase().startsWith(`${desk.toUpperCase()}:${t} `)),
  );
}

// --- Tier 2: dated episodic notes (recency = newest filename first) ---------
function datedHits(): string[] {
  if (!existsSync(memDir)) return [];
  const dated = readdirSync(memDir)
    .filter((f) => /^\d{4}-\d{2}-\d{2}\.md$/.test(f))
    .sort()
    .reverse(); // newest date first == recency rank
  const terms = tickers.length ? tickers : query.split(/\s+/).filter(Boolean);
  if (terms.length === 0) return [];
  const out: string[] = [];
  for (const f of dated) {
    const date = f.replace(".md", "");
    const text = readFileSync(path.join(memDir, f), "utf8").split("\n");
    for (const line of text) {
      const u = line.toUpperCase();
      if (terms.some((t) => new RegExp(`\\b${t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`).test(u))) {
        out.push(`[${date}] ${line.trim()}`);
        if (out.length >= k) return out;
      }
    }
  }
  return out;
}

// --- Tier 0 (best effort): OpenClaw hybrid ranker if available --------------
async function openclawHits(): Promise<string[] | null> {
  try {
    const probe = Bun.spawnSync(["openclaw", "memory", "status"], { stdout: "pipe", stderr: "pipe" });
    if (probe.exitCode !== 0) return null;
    const res = Bun.spawnSync(
      ["openclaw", "memory", "search", query || tickers.join(" "), "--json", "--max-results", String(k)],
      { stdout: "pipe", stderr: "pipe" },
    );
    if (res.exitCode !== 0) return null;
    const parsed = JSON.parse(new TextDecoder().decode(res.stdout));
    const rows = Array.isArray(parsed) ? parsed : parsed.results ?? [];
    if (!rows.length) return null;
    return rows.map((r: any) => {
      const where = r.path ? `${r.path}${r.startLine ? `:${r.startLine}` : ""}` : "memory";
      return `[${(r.score ?? 0).toFixed?.(3) ?? r.score}] ${where} — ${(r.snippet ?? r.text ?? "").trim()}`;
    });
  } catch {
    return null;
  }
}

const canon = canonicalLines();
const oc = await openclawHits();
const dated = oc ?? datedHits();
const source = oc ? "openclaw-hybrid" : "grep-fallback";

if (canon.length === 0 && dated.length === 0) {
  console.log("[no prior memory for this run]");
  process.exit(0);
}

console.log(`<prior_context source="${source}" desk="${desk}">`);
if (canon.length) {
  console.log("canonical (current stance — evergreen, never decays):");
  for (const l of canon) console.log(`  ${l}`);
}
if (dated.length) {
  console.log(oc ? "ranked memory (hybrid BM25+vector+decay):" : "episodic (dated notes, newest first):");
  for (const l of dated) console.log(`  ${l}`);
}
console.log("</prior_context>");
