export const meta = {
  name: 'crypto-advisor',
  description: 'Sequential per-token crypto analysis: TradingView MCP data pull (orchestrator only) → 5-seat quorum → narrative with real web-fetched sources → citation validation post-hook (code-enforced ERR_RX, same pattern as hedge-fund-committee). Outputs BUY/SELL/HOLD signal table + plain-English verdicts + validated news sources.',
  phases: [
    { title: 'Analyze',  detail: 'Sequential per-token: TV data pull (orchestrator) → indicators.py → 5-seat quorum → narrative with real web fetches. Returns structured JSON per token.' },
    { title: 'Validate', detail: 'Code-enforced citation scan: ERR_RX on every cited URL, spawn cold re-fetch validator agent, log failures to logs/citation-errors.log' },
    { title: 'Report',   detail: 'Merge signals + validation verdicts → print 3-block report with CITATION_FAILED flags where applicable' },
  ],
}

// Use 'sonnet' — resolves in both Claude Code and OpenCode. 'claude-sonnet-4' fails in Claude Code.
const MODEL = 'sonnet'
const SKILL = '/Users/engineer/workspace/backtest/.agents/skills'

// ── Args normalization (OpenCode delivers object; Claude Code Workflow tool delivers JSON string) ──
const ARGS = (typeof args === 'string')
  ? (() => { try { return JSON.parse(args) || {} } catch (e) { return {} } })()
  : (args && typeof args === 'object' ? args : {})

const RUN_DATE   = ARGS.date    || '(today)'
const RAW_TOKENS = ARGS.tokens  || 'BTC,ETH,SOL,UNI,HYPE,AAVE,LINK'
const TOKENS     = RAW_TOKENS.split(',').map(t => t.trim().toUpperCase()).filter(Boolean)

// ── Structured output schema (what every per-token agent must return) ─────────
// citations is the hook: every source the narrative seat used must appear here as {url, quote, tier}.
// The workflow JS (not a prompt) scans these with ERR_RX — no agent can self-validate this away.
const TOKEN_SCHEMA = {
  type: 'object',
  properties: {
    symbol:          { type: 'string' },
    price:           { type: 'number' },
    signal:          { type: 'string', enum: ['BUY', 'BUY (small)', 'HOLD', 'SELL'] },
    quorum_verdict:  { type: 'string', enum: ['BULLISH', 'SPLIT', 'BEARISH', 'UNCERTAIN'] },
    dominant_zone:   { type: 'string', enum: ['DEEP_VALUE', 'FAIR_VALUE', 'ELEVATED', 'EXTREME', 'UNKNOWN'] },
    seats_bull:      { type: 'integer', minimum: 0, maximum: 5 },
    seats_bear:      { type: 'integer', minimum: 0, maximum: 5 },
    key_support:     { type: 'number' },
    key_resistance:  { type: 'number' },
    confidence:      { type: 'string', enum: ['HIGH', 'MED', 'LOW'] },
    narrative_posture: { type: 'string', enum: ['BULLISH', 'NEUTRAL', 'BEARISH', 'INSUFFICIENT_DATA'] },
    plain_verdict:   { type: 'string', description: '3-5 sentence plain-English verdict for a non-expert' },
    // THE HOOK: structured citation list the workflow JS scans deterministically
    citations: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          url:    { type: 'string', description: 'The exact https:// URL passed to web_fetch. If no real URL, write [FETCH FAILED: reason]' },
          quote:  { type: 'string', description: 'Verbatim text copied from the fetched page' },
          tier:   { type: 'string', enum: ['T1', 'T2', 'T3', 'FAILED'] },
          status: { type: 'string', enum: ['fetched', 'failed', 'not_fetched'] },
        },
        required: ['url', 'tier', 'status'],
      },
    },
  },
  required: ['symbol', 'signal', 'quorum_verdict', 'dominant_zone', 'seats_bull', 'seats_bear', 'confidence', 'citations'],
}

// ── PHASE 1 — ANALYZE (strictly sequential — single TV chart slot) ────────────
// CRITICAL: tradingview-* MCP tools exist ONLY in the orchestrator. Subagents have zero TV tools.
// Therefore each token must be its own sequential agent call in this loop, not parallelized.
// The agent receives the TV data pull instructions AND must return structured JSON via schema.
phase('Analyze')

const TOKEN_PROMPT = (symbol) =>
  `You are analyzing ${symbol} for crypto advisor. Follow the skill at ` +
  `${SKILL}/crypto-advisor/SKILL.md Steps 1a–1e exactly.\n\n` +

  `HARD CONSTRAINTS (non-negotiable):\n` +
  `1. tradingview-* MCP tools are available to you — use them for all price/indicator data.\n` +
  `2. For the narrative seat: call web_fetch on REAL URLs before citing any source. ` +
     `If a fetch fails, set status="failed" and url="[FETCH FAILED: <reason>]" in the citations array. ` +
     `Do NOT invent headlines. Do NOT put a title where a URL belongs.\n` +
  `3. The citations array in your JSON output is code-scanned by the workflow after you return. ` +
     `Any citation with status!="fetched" or url not starting with https:// will be logged as a ` +
     `citation failure and flagged in the final report. There is no way to hide a bad citation.\n` +
  `4. If you have fewer than 2 successfully fetched sources, set narrative_posture="INSUFFICIENT_DATA".\n\n` +

  `Starting URLs to try for the narrative seat (web_fetch these first):\n` +
  `- Fear & Greed: https://api.alternative.me/fng/?limit=1\n` +
  `- CoinDesk: https://www.coindesk.com/search?q=${symbol}+2026\n` +
  `- CryptoPanic: https://cryptopanic.com/news/${symbol.toLowerCase()}/\n` +
  `- DeFiLlama (if DeFi): https://defillama.com/protocol/${symbol.toLowerCase()}\n\n` +

  `Return your full analysis as a JSON object matching the schema. The plain_verdict field must be ` +
  `3-5 sentences a non-expert can understand (why this signal, main risk, what to watch).`

// Sequential loop — one agent per token, in order
const results = []
for (const symbol of TOKENS) {
  log(`Analyzing ${symbol}...`)
  const result = await agent(TOKEN_PROMPT(symbol), {
    label: `analyze:${symbol}`,
    phase: 'Analyze',
    schema: TOKEN_SCHEMA,
    model: MODEL,
  }).catch(err => ({
    symbol,
    signal: 'HOLD',
    quorum_verdict: 'UNCERTAIN',
    dominant_zone: 'UNKNOWN',
    seats_bull: 0, seats_bear: 0,
    confidence: 'LOW',
    narrative_posture: 'INSUFFICIENT_DATA',
    plain_verdict: `[agent errored: ${String(err).slice(0, 120)}]`,
    citations: [{ url: `[AGENT ERROR: ${String(err).slice(0, 80)}]`, quote: '', tier: 'FAILED', status: 'failed' }],
  }))
  results.push(result || {
    symbol,
    signal: 'HOLD',
    quorum_verdict: 'UNCERTAIN',
    dominant_zone: 'UNKNOWN',
    seats_bull: 0, seats_bear: 0,
    confidence: 'LOW',
    narrative_posture: 'INSUFFICIENT_DATA',
    plain_verdict: '[agent returned null]',
    citations: [{ url: '[NULL RESULT]', quote: '', tier: 'FAILED', status: 'failed' }],
  })
}

// ── PHASE 2 — CITATION VALIDATION (code-enforced post-hook) ──────────────────
// This is the same ERR_RX pattern from hedge-fund-committee Phase 4.5.
// The JS regex runs on the structured citation JSON — no LLM decides whether citations are valid.
// A hallucinated URL (no https://, status != fetched) is caught here regardless of what the
// analysis agent claimed in its prose.
phase('Validate')

// Regex matches: missing https://, explicit FAILED markers, or error-shaped content
const CITATION_BAD_RX = /^(?!https?:\/\/)|^\[FETCH FAILED|^\[AGENT ERROR|^\[NULL|\b(not_fetched|failed)\b/i

const citationRows = []
for (const r of results) {
  for (const c of (r.citations || [])) {
    const bad = CITATION_BAD_RX.test(c.url) || c.status !== 'fetched'
    citationRows.push({
      symbol:  r.symbol,
      tier:    c.tier,
      url:     (c.url || '').slice(0, 300),
      quote:   (c.quote || '').slice(0, 200),
      status:  c.status,
      bad,
    })
  }
}

const badCitations = citationRows.filter(c => c.bad)
const goodCitations = citationRows.filter(c => !c.bad)
log(`Citations: ${goodCitations.length} good, ${badCitations.length} bad`)

// Symbols with ≥1 bad citation → flag them in the report
const flaggedSymbols = new Set(badCitations.map(c => c.symbol))

// Spawn cold re-fetch validator on the GOOD citations to check quote presence
// (separate agent = no memory of original fetch, literal string match)
let validationReport = null
if (goodCitations.length > 0) {
  validationReport = await agent(
    `You are a citation auditor. Re-fetch every URL in the list below and check whether the quoted ` +
    `text is actually present on the page (verbatim or near-verbatim 6-word match).\n\n` +
    `For each: call web_fetch(url), search for the quote, return status:\n` +
    `- VERIFIED: quote found verbatim or 5/6 words present\n` +
    `- NOT_FOUND: page fetched but quote absent → this is a hallucinated citation\n` +
    `- FETCH_FAILED: could not fetch the URL\n\n` +
    `Citations to check (JSON):\n${JSON.stringify(goodCitations, null, 2)}\n\n` +
    `Return a JSON array: [{symbol, url, status: "VERIFIED"|"NOT_FOUND"|"FETCH_FAILED", evidence: "verbatim snippet found, or empty"}]`,
    { label: 'citation-validator', phase: 'Validate', model: MODEL,
      schema: { type: 'array', items: { type: 'object', properties: {
        symbol: { type: 'string' }, url: { type: 'string' },
        status: { type: 'string', enum: ['VERIFIED', 'NOT_FOUND', 'FETCH_FAILED'] },
        evidence: { type: 'string' },
      }, required: ['symbol', 'url', 'status'] } },
    }
  ).catch(err => { log(`Validator agent error: ${err}`); return null })

  // NOT_FOUND from the cold validator = hallucinated → add to flagged
  if (Array.isArray(validationReport)) {
    for (const v of validationReport) {
      if (v.status === 'NOT_FOUND') flaggedSymbols.add(v.symbol)
    }
  }
}

// Append to durable error log (same pattern as hedge-fund-committee logs/error.log)
const errRows = [
  ...badCitations.map(c => ({ symbol: c.symbol, type: 'BAD_URL', detail: c.url.slice(0, 300) })),
  ...(Array.isArray(validationReport)
    ? validationReport.filter(v => v.status === 'NOT_FOUND')
        .map(v => ({ symbol: v.symbol, type: 'HALLUCINATED_QUOTE', detail: v.url.slice(0, 300) }))
    : []),
]

if (errRows.length) {
  await agent(
    `Append a citation-error log entry, then return only "ERRLOG OK".\n` +
    `1. \`mkdir -p logs\`. 2. Get UTC timestamp: \`date -u +%FT%TZ\`.\n` +
    `3. APPEND (never overwrite) to \`logs/citation-errors.log\`:\n` +
    `Header: \`=== <timestamp> crypto-advisor run ===\`\n` +
    `Then one tab-separated line per row: \`<timestamp>\\t<symbol>\\t<type>\\t<detail>\`\n` +
    `Rows: ${JSON.stringify(errRows)}`,
    { label: 'citation-errlog', phase: 'Validate', model: MODEL }
  )
  log(`Logged ${errRows.length} citation error(s) to logs/citation-errors.log`)
}

// ── PHASE 3 — REPORT ─────────────────────────────────────────────────────────
phase('Report')

const validatorMap = {}
if (Array.isArray(validationReport)) {
  for (const v of validationReport) {
    const key = `${v.symbol}::${v.url}`
    validatorMap[key] = v.status
  }
}

await agent(
  `Print the final crypto portfolio run report. Use exactly this data — do not re-run any analysis.\n\n` +
  `RUN DATE: ${RUN_DATE}\n` +
  `FLAGGED SYMBOLS (≥1 citation failed validation): ${JSON.stringify([...flaggedSymbols])}\n` +
  `ANALYSIS RESULTS: ${JSON.stringify(results, null, 2)}\n` +
  `CITATION VALIDATION: ${JSON.stringify(validationReport, null, 2)}\n\n` +

  `Print THREE BLOCKS in order:\n\n` +

  `BLOCK 1 — Signal table:\n` +
  `=== CRYPTO PORTFOLIO RUN — ${RUN_DATE} ===  (data: TradingView MCP)\n` +
  `One row per token: Token | Signal (append ⚠️ CITATION_FAILED if in flagged list) | Zone | Quorum | Bulls/Bears\n\n` +

  `BLOCK 2 — Plain-English verdicts:\n` +
  `For each token, print the plain_verdict from the analysis result verbatim (3-5 sentences). ` +
  `If flagged, prepend: "⚠️ Narrative sources could not be verified — treat the narrative seat as INSUFFICIENT_DATA."\n\n` +

  `BLOCK 3 — Citation validation report:\n` +
  `--- CITATION VALIDATION ---\n` +
  `For each token, list its citations with their validation status (VERIFIED/NOT_FOUND/FETCH_FAILED/BAD_URL). ` +
  `Use the validationReport data exactly — do not invent statuses.\n` +
  `End with a summary line: "X/Y citations VERIFIED, Z hallucinated/failed — see logs/citation-errors.log"\n`,
  { label: 'report', phase: 'Report', model: MODEL }
)
