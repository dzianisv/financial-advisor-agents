#!/usr/bin/env bun
/**
 * PostToolUse(web_fetch) hook — logs every real fetch to /tmp/cc-fetches-{SESSION_ID}.jsonl
 * Runs outside the LLM loop. Called by Claude Code after every web_fetch tool call.
 * Input (stdin): { tool_name, tool_input: {url}, tool_response: {...}, session_id, ... }
 */

const input = await Bun.stdin.text()
const event = JSON.parse(input)

const sessionId: string = event.session_id ?? "unknown"
const url: string = event.tool_input?.url ?? ""
const hasError: boolean = !!(event.tool_response?.error)
const status: string = event.tool_response?.status ?? "unknown"

if (!url) process.exit(0)

const logFile = `/tmp/cc-fetches-${sessionId}.jsonl`
const entry = JSON.stringify({
  url,
  success: !hasError,
  status,
  ts: new Date().toISOString(),
})

await Bun.write(Bun.file(logFile), 
  (await Bun.file(logFile).exists() ? await Bun.file(logFile).text() : "") + entry + "\n"
)

process.exit(0)
