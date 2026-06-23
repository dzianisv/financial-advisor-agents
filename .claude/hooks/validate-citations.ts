#!/usr/bin/env bun
/**
 * validate-citations.ts — Claude Code Stop hook
 * Fires when Claude finishes a turn. Parses transcript for [T1]/[T2]/[T3] URLs,
 * diffs against the real fetch log from log-web-fetch.ts, flags hallucinations.
 * Input (stdin): { session_id, transcript_path, ... }
 */

import { join } from "path"

const REPO = "/Users/engineer/workspace/backtest"
const CITATION_RX = /\[T[123]\]\s+(https?:\/\/\S+)/g

const input = await Bun.stdin.text()
const event = JSON.parse(input)

const sessionId: string = event.session_id ?? "unknown"
const transcriptPath: string = event.transcript_path ?? ""
const fetchLog = `/tmp/cc-fetches-${sessionId}.jsonl`
const errorLog = join(REPO, "logs/citation-errors.log")

// ── 1. Extract cited URLs from transcript ──────────────────────────────────
const cited: string[] = []
if (transcriptPath) {
  try {
    const transcript = await Bun.file(transcriptPath).text()
    // Transcript is JSONL — find last assistant message
    const lines = transcript.split("\n").filter(Boolean)
    const assistantLines = lines
      .map(l => { try { return JSON.parse(l) } catch { return null } })
      .filter(m => m?.role === "assistant")

    const text = assistantLines.map(m => m?.content ?? "").join("\n")
    for (const match of text.matchAll(CITATION_RX)) {
      cited.push(match[1].replace(/[.,;)]+$/, ""))
    }
  } catch {}
}

if (cited.length === 0) process.exit(0)

// ── 2. Load actually-fetched URLs ─────────────────────────────────────────
const fetched = new Set<string>()
try {
  const raw = await Bun.file(fetchLog).text()
  for (const line of raw.split("\n").filter(Boolean)) {
    try {
      const { url, success } = JSON.parse(line)
      if (success) fetched.add(url)
    } catch {}
  }
} catch {}

// ── 3. Diff — cited but not fetched = hallucinated ────────────────────────
const ts = new Date().toISOString()
const failures: string[] = []

for (const url of cited) {
  if (!fetched.has(url)) failures.push(url)
}

if (failures.length > 0) {
  await Bun.mkdir(join(REPO, "logs"), { recursive: true })
  const existing = await Bun.file(errorLog).exists() ? await Bun.file(errorLog).text() : ""
  const newLines = failures.map(u => `${ts}\t${sessionId}\tHALLUCINATED_CITATION\t${u}`).join("\n")
  await Bun.write(errorLog, existing + newLines + "\n")
  process.stderr.write(`⚠️  [citation-validator] ${failures.length} cited URL(s) never fetched — see logs/citation-errors.log\n`)
}

// ── 4. Clean up session fetch log ─────────────────────────────────────────
try { await Bun.file(fetchLog).unlink() } catch {}

process.exit(0)
