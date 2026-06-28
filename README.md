# Financial Advisor Agent — Agentic Hedge-Fund + Crypto Workflows

> ⚠️ **Educational analysis only — not financial advice.** Past backtest performance does not guarantee future results. Validate with a fee-only fiduciary before deploying real capital.

A portable skill+workflow layer that turns **Claude Code, openclaw, or hermes** into a proactive financial advisor — watching markets daily and surfacing time-sensitive setups before they're missed.

The agent proposes; the human approves every order. Recommend-only, always.

## Architecture

The `research-market` workflow is an 8-phase dynamic pipeline where a **CIO agent (`research-manager`) discovers all skill components live at runtime** — no roster is hardcoded in the orchestrator. Phases execute as sequential gates; within each gate, work fans out in parallel across assets, keeping per-asset cost O(1) regardless of how many tickers the screener surfaces.

![research-market workflow](docs/research-market-architecture.svg)

Key design properties:
- **Autonomous screener** — no hardcoded tickers; `sector-screen` derives candidates from ETF holdings, analyst screeners, and earnings transcripts using runtime `screen_criteria`
- **Per-asset O(1) pipeline** — Gather, Consolidate, Panel, and Ledger all fan out independently per asset; adding more tickers does not change per-asset agent count
- **MAX_GATHER=3 / MAX_PANEL=3 caps** — hard limits on parallel gather and panel seats per asset, preventing token runaway
- **CIO discovers skills live** — `research-manager` lists `.agents/skills/` at runtime and selects `gather_skills[]`, `panel_skills[]`, `desk_skill`, and `chair_skill` from what is actually installed
- **Ledger logs calibrated Brier-scored probabilities** — every per-asset conviction score is recorded via `python3 ledger.py add` for ongoing calibration tracking

## How it works

Two tiers run on any backend. FAST catches same-day setups; SLOW produces a weekly buy brief.

```
                      DATA SOURCES
  yfinance | FRED | alternative.me | EDGAR | FT/WSJ | Polymarket
                         |
          +--------------+---------------+
          |                              |
   FAST (daily cron)             SLOW (weekly workflow)
   scan -> gate -> DM            hedge-fund-committee
          |                              |
  dip-screener                   1. COLLECT  (x6 parallel)
  crypto-dip-scanner                regime, fomc, 13f,
  regime-detection                  congress, news, dips
  feed-fomc                           |
  trend-stock-research           2. PANEL  (multi-lens-quorum)
          |                         4+ analyst lenses
  signal-convergence-alert               |
  (>=2 sources match)            3. DECIDE
          |                         risk veto -> buy brief
          +-------------+---------------+
                        |
                   DM to owner
              (silent when nothing fires)
                        |
       +-----------------------------------+
       | Claude Code  |  openclaw  | hermes |
       +-----------------------------------+
```

- **FAST** -- daily cron fires each scanner independently. A gate must pass (e.g. stock -30% from 52w high AND regime=RISK_ON) before a DM is sent; otherwise the job is silent. The convergence alert cross-references all pools and DMs when the same ticker appears in 2+ sources.
- **SLOW** -- a weekly multi-agent workflow fans out 6 research desks in parallel, ranks candidates by source count, runs each through a 4-lens analyst panel (Buffett, Druckenmiller, Alden, fundamentals), applies a binding risk-management veto, and produces a ranked buy brief with staged entry plans.
- **Backend** -- same ~60 skills install identically onto Claude Code, openclaw, or hermes. Only the scheduling primitive differs.

---

## stocks-advisor — pluggable decision hierarchy

The `stocks-advisor` skill runs a 5-seat analyst panel (fundamental / technical / narrative-macro / sentiment / smart-money) per stock, then routes through a **pluggable decision hierarchy** that replaces the default committee with a named hedge-fund decision chain.

Invoke with `--hierarchy <name>`. Default is `bsc` (best eval score). All 8 hierarchies are blind-scored /25 against the same IBKR portfolio input (85 positions, $578k equity, COIN 21.5%):

| Rank | Hierarchy | Key mechanism | Score |
|:----:|:----------|:--------------|:-----:|
| 1 | `bsc` ← **default** | Edge Gate + Skeptic [MEM audit] + P0/P1/P2/P3 | **25/25** |
| 2 | `bridgewater` | Skeptic → CIO → Risk Manager | 23/25 |
| 3 | `soros` | Macro thesis → Reflexivity → P0/P1/P2/P3 | 21/25 |
| 4 | `berkshire` | Circle of Competence → Moat → Munger Inversion | 20/25 |
| 4 | `millennium` | PM thesis → Automated Hard Stop (Kelly, no override) | 20/25 |
| 6 | `citadel` | Pod PM → Central Risk (bidirectional) → Griffin | 19/25 |
| 6 | `point72` | Edge Gate → Conviction → Cohen Seat | 19/25 |
| 8 | `tiger` | Variant perception → Adversarial pitch → sole authority | 15/25 |

**Why BSC Hybrid wins:** combines Bridgewater's mandatory Skeptic seat (adversarial challenge before every CIO decision), Soros's P0/P1/P2/P3 execution table (share counts + falsification conditions per row), and Cohen's Edge Gate (information / analytical / timing / structural edge must be named before deep-dive — no edge = fundamentals-only WATCH). Also adds [LIVE]/[FILED]/[MEM] citation tagging on all Skeptic factual claims to close the data-grounding ceiling shared by all lower-scoring architectures.

**Why Tiger scores lowest on a diversified portfolio:** Tiger's decision chain is designed for 15–20 name concentrated long/short books. On an 85-position book it identifies variant-perception ideas but cannot reason across positions holistically.

**Run with a specific hierarchy:**
```
Run stocks-advisor with --hierarchy bridgewater on: AAPL, KO, AXP
Review my portfolio [sheet URL] using --hierarchy bsc
Compare hierarchies on: AAPL, KO — use all        # → routes to hierarchy-compare workflow
```

Hierarchy files: `.agents/skills/stocks-advisor/references/hierarchies/`
Eval workflow: `.claude/workflows/hierarchy-compare.js`

```
BSC Hybrid decision chain (6 steps):

  ┌─────────────────────────────────────────────────────────┐
  │ Step 0.85  COHEN EDGE GATE                              │
  │            Name edge type: INFO / ANALYTICAL /          │
  │            TIMING / STRUCTURAL — or NO_EDGE → skip      │
  └──────────────────────┬──────────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────────┐
  │ Step 1     5-SEAT PANEL (parallel)                      │
  │            Fundamental · Technical · Narrative ·        │
  │            Sentiment · Smart-money                      │
  └──────────────────────┬──────────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────────┐
  │ Step 2     SKEPTIC SEAT  [MEM-audit]                    │
  │            Adversarial challenge · [LIVE]/[FILED]/[MEM] │
  │            tags · -30%/-50% tail stress                 │
  └──────────────────────┬──────────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────────┐
  │ Step 2.5   CIO SYNTHESIS                                │
  │            Weighs panel vs Skeptic · DISSENT LOGGED     │
  │            even when Skeptic overruled                  │
  └──────────────────────┬──────────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────────┐
  │ Step 2.7   RISK MANAGER GATE                            │
  │            APPROVED $X (N% book) or BLOCKED: reason     │
  │            Required for every BUY / ADD verdict         │
  └──────────────────────┬──────────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────────┐
  │ Step 3.6   P0/P1/P2/P3 EXECUTION TABLE (Soros format)  │
  │            Share counts · entry zones · triggers ·      │
  │            falsification condition per row              │
  └─────────────────────────────────────────────────────────┘
```

---

## research-market pipeline

> Source: [`.agents/workflows/research-market.workflow.js`](.agents/workflows/research-market.workflow.js)

Six-phase dynamic workflow. **`research-manager`** (intake/triage desk head) reads available skills live at runtime and selects every component — no roster is hardcoded in the script.

<svg viewBox="0 0 820 960" xmlns="http://www.w3.org/2000/svg" font-family="system-ui,sans-serif" font-size="12">
<defs>
  <marker id="arr" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
    <polygon points="0 0, 8 3, 0 6" fill="#aaa"/>
  </marker>
</defs>

<!-- Lane backgrounds -->
<rect x="90" y="44"  width="716" height="72"  rx="6" fill="#f5f5f5"/>
<rect x="90" y="126" width="716" height="228" rx="6" fill="#eeeeee"/>
<rect x="90" y="364" width="716" height="116" rx="6" fill="#f5f5f5"/>
<rect x="90" y="490" width="716" height="316" rx="6" fill="#eeeeee"/>
<rect x="90" y="816" width="716" height="68"  rx="6" fill="#f5f5f5"/>
<rect x="90" y="894" width="716" height="50"  rx="6" fill="#f5f5f5"/>

<!-- Lane labels -->
<text x="14" y="82"  fill="#bbb" font-size="8" font-weight="700" letter-spacing="1">INTAKE</text>
<text x="14" y="242" fill="#bbb" font-size="8" font-weight="700" letter-spacing="1">GATHER</text>
<text x="14" y="422" fill="#bbb" font-size="8" font-weight="700" letter-spacing="1">CONSOLIDATE</text>
<text x="14" y="648" fill="#bbb" font-size="8" font-weight="700" letter-spacing="1">PANEL</text>
<text x="14" y="850" fill="#bbb" font-size="8" font-weight="700" letter-spacing="1">DECIDE</text>
<text x="14" y="919" fill="#bbb" font-size="8" font-weight="700" letter-spacing="1">LEDGER</text>

<!-- ═══ INTAKE ═══ -->
<rect x="280" y="50" width="260" height="60" rx="8" fill="#6366f1"/>
<text x="410" y="72"  text-anchor="middle" fill="white" font-weight="700" font-size="14">research-manager</text>
<text x="410" y="89"  text-anchor="middle" fill="white" font-size="10" opacity=".85">intake / triage desk head</text>
<text x="410" y="104" text-anchor="middle" fill="white" font-size="8.5" opacity=".65">discovers skills live → builds routing plan</text>
<line x1="410" y1="110" x2="410" y2="124" stroke="#bbb" stroke-width="1.2" marker-end="url(#arr)"/>

<!-- ═══ GATHER row A: regulatory / macro / odds ═══ -->
<text x="410" y="140" text-anchor="middle" fill="#bbb" font-size="8.5" font-style="italic">— regulatory / macro / odds —</text>

<rect x="98"  y="146" width="114" height="44" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="155" y="163" text-anchor="middle" fill="#555" font-size="8" font-family="monospace" font-weight="600">analyst-smartmoney-13f</text>
<text x="155" y="177" text-anchor="middle" fill="#888" font-size="9">fund filings (EDGAR)</text>
<text x="155" y="189" text-anchor="middle" fill="#bbb" font-size="7.5">13F quarterly</text>

<rect x="222" y="146" width="108" height="44" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="276" y="163" text-anchor="middle" fill="#555" font-size="8" font-family="monospace" font-weight="600">analyst-smartmoney-13d</text>
<text x="276" y="177" text-anchor="middle" fill="#888" font-size="9">activist filings</text>

<rect x="340" y="146" width="154" height="44" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="417" y="163" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace" font-weight="600">analyst-smartmoney-ptr</text>
<text x="417" y="178" text-anchor="middle" fill="#888" font-size="9">trades disclosures</text>

<rect x="504" y="146" width="112" height="44" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="560" y="163" text-anchor="middle" fill="#555" font-size="8" font-family="monospace" font-weight="600">feed-fomc</text>
<text x="560" y="178" text-anchor="middle" fill="#888" font-size="9">Fed rates / statements</text>

<rect x="626" y="146" width="144" height="44" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="698" y="163" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace" font-weight="600">analyst-smartmoney-polymarket</text>
<text x="698" y="178" text-anchor="middle" fill="#888" font-size="9">Polymarket / Kalshi</text>

<!-- ═══ GATHER row B: news feeds ═══ -->
<text x="410" y="204" text-anchor="middle" fill="#bbb" font-size="8.5" font-style="italic">— news feeds —</text>

<rect x="98"  y="208" width="102" height="40" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="149" y="224" text-anchor="middle" fill="#555" font-size="8" font-family="monospace" font-weight="600">feed-wsj</text>
<text x="149" y="240" text-anchor="middle" fill="#888" font-size="9">Wall Street Journal</text>

<rect x="210" y="208" width="92"  height="40" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="256" y="224" text-anchor="middle" fill="#555" font-size="8" font-family="monospace" font-weight="600">feed-ft</text>
<text x="256" y="240" text-anchor="middle" fill="#888" font-size="9">Financial Times</text>

<rect x="312" y="208" width="136" height="40" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="380" y="224" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace" font-weight="600">feed-cointelegraph</text>
<text x="380" y="240" text-anchor="middle" fill="#888" font-size="9">CoinTelegraph</text>

<rect x="458" y="208" width="116" height="40" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="516" y="224" text-anchor="middle" fill="#555" font-size="8" font-family="monospace" font-weight="600">feed-coindesk</text>
<text x="516" y="240" text-anchor="middle" fill="#888" font-size="9">CoinDesk</text>

<rect x="584" y="208" width="108" height="40" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="638" y="224" text-anchor="middle" fill="#555" font-size="8" font-family="monospace" font-weight="600">feed-decrypt</text>
<text x="638" y="240" text-anchor="middle" fill="#888" font-size="9">Decrypt.co</text>

<text x="700" y="204" text-anchor="end" fill="#888" font-size="7.5" font-style="italic">+ feed-coinbase · feed-theblock · feed-bitcoinmagazine · feed-bloomberg</text>

<!-- ═══ GATHER row C: onchain / quant ═══ -->
<text x="410" y="264" text-anchor="middle" fill="#bbb" font-size="8.5" font-style="italic">— onchain / quant data —</text>

<rect x="112" y="270" width="150" height="40" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="187" y="286" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace" font-weight="600">crypto-onchain-data</text>
<text x="187" y="302" text-anchor="middle" fill="#888" font-size="9">MVRV-Z, NUPL</text>

<rect x="272" y="270" width="150" height="40" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="347" y="286" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace" font-weight="600">crypto-liquidity-data</text>
<text x="347" y="302" text-anchor="middle" fill="#888" font-size="9">ETF flows / CEX depth</text>

<rect x="432" y="270" width="180" height="40" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="522" y="286" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace" font-weight="600">analyst-smartmoney-positioning</text>
<text x="522" y="302" text-anchor="middle" fill="#888" font-size="9">funding, OI, options</text>

<rect x="622" y="270" width="104" height="40" rx="5" fill="white" stroke="#ddd" stroke-width="1.2"/>
<text x="674" y="286" text-anchor="middle" fill="#555" font-size="8" font-family="monospace" font-weight="600">dip-scanner</text>
<text x="674" y="302" text-anchor="middle" fill="#888" font-size="9">−30% from 52w high</text>

<!-- Gather → Consolidate -->
<line x1="410" y1="317" x2="410" y2="358" stroke="#bbb" stroke-width="1.2" stroke-dasharray="4 3" marker-end="url(#arr)"/>
<text x="452" y="340" fill="#bbb" font-size="8.5">all seats parallel</text>

<!-- ═══ CONSOLIDATE ═══ -->
<rect x="282" y="370" width="256" height="48" rx="8" fill="white" stroke="#6366f1" stroke-width="2"/>
<text x="410" y="391"  text-anchor="middle" fill="#111" font-weight="700" font-size="13">Research Report</text>
<text x="410" y="409" text-anchor="middle" fill="#555" font-size="10">desk skill merges all seat findings</text>

<line x1="410" y1="418" x2="410" y2="434" stroke="#bbb" stroke-width="1.2" marker-end="url(#arr)"/>

<rect x="312" y="436" width="196" height="36" rx="6" fill="#f0f0f0" stroke="#ddd" stroke-width="1.2"/>
<text x="410" y="452" text-anchor="middle" fill="#555" font-size="8" font-family="monospace" font-weight="600">crypto-research-desk</text>
<text x="410" y="466" text-anchor="middle" fill="#888" font-size="8">/ stock-research-desk</text>

<line x1="410" y1="472" x2="410" y2="488" stroke="#bbb" stroke-width="1.2" marker-end="url(#arr)"/>

<!-- ═══ PANEL ═══ -->
<text x="410" y="502" text-anchor="middle" fill="#bbb" font-size="8.5" font-style="italic">multi-lens quorum — parallel — all reason over consolidated brief</text>

<!--
  Person icon: (cx, top)
    head  circle: cx, top+13, r=11
    body  rect:   cx-12, top+24, w=24 h=18 rx=6
    name text:    cx, top+57  (600 weight, 11px)
    skill text:   cx, top+69  (monospace, 7.5px)
    desc  text:   cx, top+80  (9px)
  cols cx: 185, 410, 635   row tops: 510, 614, 718
-->

<!-- ROW 1 (top=510) -->
<!-- investor-lyn-alden -->
<circle cx="185" cy="523" r="11" fill="#6366f1"/>
<rect x="173" y="534" width="24" height="18" rx="6" fill="#6366f1"/>
<text x="185" y="567" text-anchor="middle" fill="#111" font-weight="600" font-size="11">Lyn Alden</text>
<text x="185" y="579" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace">investor-lyn-alden</text>
<text x="185" y="590" text-anchor="middle" fill="#888" font-size="9">macro-monetary</text>

<!-- investor-ray-dalio -->
<circle cx="410" cy="523" r="11" fill="#6366f1"/>
<rect x="398" y="534" width="24" height="18" rx="6" fill="#6366f1"/>
<text x="410" y="567" text-anchor="middle" fill="#111" font-weight="600" font-size="11">Ray Dalio</text>
<text x="410" y="579" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace">investor-ray-dalio</text>
<text x="410" y="590" text-anchor="middle" fill="#888" font-size="9">debt cycle</text>

<!-- investor-stanley-druckenmiller -->
<circle cx="635" cy="523" r="11" fill="#6366f1"/>
<rect x="623" y="534" width="24" height="18" rx="6" fill="#6366f1"/>
<text x="635" y="567" text-anchor="middle" fill="#111" font-weight="600" font-size="11">Druckenmiller</text>
<text x="635" y="579" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace">investor-stanley-druckenmiller</text>
<text x="635" y="590" text-anchor="middle" fill="#888" font-size="9">momentum / risk</text>

<!-- ROW 2 (top=614) -->
<!-- research-lacy-hunt -->
<circle cx="185" cy="627" r="11" fill="#6366f1"/>
<rect x="173" y="638" width="24" height="18" rx="6" fill="#6366f1"/>
<text x="185" y="671" text-anchor="middle" fill="#111" font-weight="600" font-size="11">Lacy Hunt</text>
<text x="185" y="683" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace">research-lacy-hunt</text>
<text x="185" y="694" text-anchor="middle" fill="#888" font-size="9">deflation dissent</text>

<!-- investor-warren-buffett -->
<circle cx="410" cy="627" r="11" fill="#6366f1"/>
<rect x="398" y="638" width="24" height="18" rx="6" fill="#6366f1"/>
<text x="410" y="671" text-anchor="middle" fill="#111" font-weight="600" font-size="11">Buffett / Graham</text>
<text x="410" y="683" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace">investor-warren-buffett</text>
<text x="410" y="694" text-anchor="middle" fill="#888" font-size="9">value + margin of safety</text>

<!-- research-michael-pettis -->
<circle cx="635" cy="627" r="11" fill="#6366f1"/>
<rect x="623" y="638" width="24" height="18" rx="6" fill="#6366f1"/>
<text x="635" y="671" text-anchor="middle" fill="#111" font-weight="600" font-size="11">Pettis</text>
<text x="635" y="683" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace">research-michael-pettis</text>
<text x="635" y="694" text-anchor="middle" fill="#888" font-size="9">global imbalances</text>

<!-- ROW 3 (top=718) -->
<!-- research-russell-napier -->
<circle cx="185" cy="731" r="11" fill="#6366f1"/>
<rect x="173" y="742" width="24" height="18" rx="6" fill="#6366f1"/>
<text x="185" y="775" text-anchor="middle" fill="#111" font-weight="600" font-size="11">Russell Napier</text>
<text x="185" y="787" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace">research-russell-napier</text>
<text x="185" y="798" text-anchor="middle" fill="#888" font-size="9">financial repression</text>

<!-- research-morgan-housel — NON-VOTING, slate gray -->
<circle cx="410" cy="731" r="11" fill="#94a3b8"/>
<rect x="398" y="742" width="24" height="18" rx="6" fill="#94a3b8"/>
<text x="410" y="775" text-anchor="middle" fill="#111" font-weight="600" font-size="11">Morgan Housel</text>
<text x="410" y="787" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace">research-morgan-housel</text>
<text x="410" y="798" text-anchor="middle" fill="#888" font-size="9">behavioral guard · non-voting</text>

<!-- superforecasting -->
<circle cx="635" cy="731" r="11" fill="#6366f1"/>
<rect x="623" y="742" width="24" height="18" rx="6" fill="#6366f1"/>
<text x="635" y="775" text-anchor="middle" fill="#111" font-weight="600" font-size="11">Superforecaster</text>
<text x="635" y="787" text-anchor="middle" fill="#555" font-size="7.5" font-family="monospace">superforecasting</text>
<text x="635" y="798" text-anchor="middle" fill="#888" font-size="9">calibrated probabilities</text>

<!-- Panel → Decide -->
<line x1="410" y1="805" x2="410" y2="814" stroke="#bbb" stroke-width="1.2" marker-end="url(#arr)"/>

<!-- ═══ DECIDE ═══ -->
<rect x="282" y="820" width="256" height="58" rx="8" fill="#6366f1"/>
<text x="410" y="841"  text-anchor="middle" fill="white" font-weight="700" font-size="13">Chair Decision</text>
<text x="410" y="858"  text-anchor="middle" fill="white" font-size="9.5" opacity=".85">crypto-chair · stock-chair</text>
<text x="410" y="872"  text-anchor="middle" fill="white" font-size="8.5" opacity=".65">BUY · HOLD · TRIM · AVOID + tranche plan</text>

<line x1="410" y1="878" x2="410" y2="892" stroke="#bbb" stroke-width="1.2" marker-end="url(#arr)"/>

<!-- ═══ LEDGER ═══ -->
<rect x="296" y="896" width="228" height="40" rx="8" fill="white" stroke="#bbb" stroke-width="1.4" stroke-dasharray="6 3"/>
<text x="410" y="913" text-anchor="middle" fill="#333" font-weight="600">forecast-ledger</text>
<text x="410" y="929" text-anchor="middle" fill="#888" font-size="9">ledger.py · dated row · Brier-score tracked</text>

<!-- Legend -->
<rect x="666" y="820" width="140" height="116" rx="6" fill="white" stroke="#e0e0e0" stroke-width="1"/>
<text x="736" y="838" text-anchor="middle" fill="#888" font-size="9" font-weight="600">LEGEND</text>
<rect x="676" y="846" width="14" height="12" rx="3" fill="#6366f1"/>
<text x="696" y="857" fill="#333" font-size="9">Manager / Chair</text>
<rect x="676" y="864" width="14" height="12" rx="3" fill="white" stroke="#ccc" stroke-width="1"/>
<text x="696" y="875" fill="#333" font-size="9">Data seat (skill name)</text>
<circle cx="683" cy="891" r="6" fill="#6366f1"/>
<text x="696" y="895" fill="#333" font-size="9">Voting analyst</text>
<circle cx="683" cy="909" r="6" fill="#94a3b8"/>
<text x="696" y="913" fill="#333" font-size="9">Non-voting guardrail</text>
<rect x="676" y="921" width="14" height="10" rx="2" fill="none" stroke="#bbb" stroke-width="1.4" stroke-dasharray="4 2"/>
<text x="696" y="930" fill="#333" font-size="9">Logged output</text>
</svg>

| Phase | What happens |
|---|---|
| **Intake** | `research-manager` lists `/.agents/skills/` live, reads each `SKILL.md`, returns a typed routing plan (gather seats, feeds, panel lenses, desk, chair) |
| **Gather** | All selected seats run in parallel — regulatory (13F/13D/Congress), macro (FOMC/CPI), news feeds, onchain, liquidity, derivatives, dip-screener, Polymarket odds |
| **Consolidate** | Manager-selected desk skill (`crypto-research-desk` or `stock-research-desk`) merges raw seat findings into one sourced brief |
| **Panel** | All analyst lenses debate the brief in parallel; Morgan Housel seat is non-voting behavioral guardrail |
| **Decide** | Chair skill (`crypto-chair` / `stock-chair`) synthesizes verdicts + guardrail → portfolio-aware buy/hold/trim/avoid + tranche plan |
| **Ledger** | `ledger.py` appends one dated row per asset with implied bull probability for Brier-score tracking |

---

## Installation

### Prerequisites

- **TradingView Desktop** — required by the `crypto-advisor` skill to pull live chart data (OHLCV, RSI, MACD, Bollinger Bands) via the MCP TradingView server.

  **Install (macOS):**
  ```bash
  brew install --cask tradingview
  ```
  Or download from: https://www.tradingview.com/desktop/

  **Launch with remote debugging enabled** (required every session before running `/crypto-daily` or `crypto-advisor`):
  ```bash
  open -a TradingView --args --remote-debugging-port=9222
  ```

  Wait ~10 seconds for the splash screen to clear, then run your skill. The MCP server connects to port 9222. If `crypto-advisor` reports "CDP connection failed", TradingView is not running with debugging — re-run the launch command above.

  > **Why this is needed:** The `crypto-advisor` skill reads live chart data (price, RSI, MACD, OHLCV bars, Bollinger Bands) directly from your running TradingView Desktop instance via Chrome DevTools Protocol. There is no API key or cloud alternative — the desktop app is the data source.

- **Python 3** with `yfinance` — used by the data-pulling `.py` scripts bundled in `.agents/skills/` (e.g. `dip_screener.py`, `crypto_dip_scanner.py`, `ledger.py`). Install once: `pip install yfinance`.
- **Claude Code ≥ v2.1.154** with Dynamic Workflows enabled (`/config`) — required to run `/hedge-fund-committee`, `/research-market`, and the other slash-command workflows.
- **`opencode-drawer-workflows` plugin (v1.6.0+)** — required to run `.workflow.js` files from OpenCode sessions. Provides tools: `workflow`, `workflow_status`, `workflow_stop`, `workflow_save_run`. Install:
  1. Add `"opencode-drawer-workflows"` to the `plugin` array in `~/.config/opencode/opencode.json`
  2. `cd ~/.config/opencode && npm install opencode-drawer-workflows`
  3. Restart OpenCode. Workflow scripts live in `.agents/workflows/` (main: `hedge-fund-committee.workflow.js`).
  4. Run via: `workflow` tool with `script_path: ".agents/workflows/hedge-fund-committee.workflow.js"`

### Skills

Skills live in `.agents/skills/`. A `.claude/skills` symlink already points there, making every skill in that directory available to Claude Code when you open the repo:

```
.claude/skills -> ../.agents/skills   # already present in the repo
```

To install skills onto another runtime (openclaw, hermes, Cursor):

| Runtime | Command |
|---|---|
| **Claude Code** | `npx skills add dzianisv/financial-advisor-agents` (auto-detected) |
| **openclaw** | `npx skills add dzianisv/financial-advisor-agents --agent openclaw --copy` |
| **hermes** | `npx skills add dzianisv/financial-advisor-agents --agent hermes-agent --copy` |

`--copy` ships the bundled Python scripts alongside each `SKILL.md` (needed for data-pulling skills). Without `--copy`, skills install but the `.py` helpers that pull live prices are absent.

### Workflows (Claude Code only)

Workflow scripts live in `.agents/workflows/`. Symlinks in `.claude/workflows/` register them as slash commands — present in this repo:

```
.claude/workflows/hedge-fund-committee.js   -> ../../.agents/workflows/hedge-fund-committee.workflow.js
.claude/workflows/research-market.js        -> ../../.agents/workflows/research-market.workflow.js
.claude/workflows/pairwise-eval.js          -> ../../.agents/workflows/pairwise-eval.workflow.js
.claude/workflows/multi-lens-quorum.js      # direct workflow (not a symlink)
.claude/workflows/trend-stock-research.js   # direct workflow (not a symlink)
```

To use them from another project, copy to `~/.claude/workflows/`:

```bash
cp financial-advisor-agents/.claude/workflows/*.js ~/.claude/workflows/
```

> On macOS/Linux the symlinks resolve automatically. On Windows, copy the real files from `.agents/workflows/` instead.

---

## Quick Start

### Plain-language (always works)

```
"research whether I should buy ETH, I hold 20% SOL"
"should I trim NVDA — I'm 40% in it"
```

Claude routes to the right workflow and passes your portfolio as args.

### Slash commands

With the repo open in Claude Code, the workflows are available as:

```
/hedge-fund-committee    ← weekly equity committee → staged buy brief
/research-market         ← ad-hoc crypto or equity research question
/pairwise-eval           ← blind A/B comparison of two research reports
/multi-lens-quorum       ← convene N independent analyst lenses on a judgment call
/trend-stock-research    ← research-first trend-stock screen → nominees for quorum
```

### OpenCode workflow execution

OpenCode runs workflow scripts through its installed `workflow` tool from the `opencode-drawer-workflows` plugin. The plugin supplies the workflow primitives used by `.agents/workflows/*.workflow.js`; pass the script and arguments with the Drawers tool schema:

```json
{
  "script_path": ".agents/workflows/research-market.workflow.js",
  "args": {
    "question": "Should I buy BTC today?",
    "portfolio": "no direct BTC",
    "date": "2026-06-17"
  }
}
```

### Explicit Workflow tool form

Use this when you want to pass specific args (ticker, date, portfolio):

**Ad-hoc research — crypto** (`research-market`):

```js
Workflow({
  scriptPath: "./.agents/workflows/research-market.workflow.js",
  args: {
    question:  "BTC reached 65k from the drop to 61k. I hold 30% in COIN. Should I buy BTC today?",
    portfolio: "~30% of book in COIN (levered crypto-beta proxy); no direct BTC.",
    date:      "2026-06-16",   // required — Date.now() is unavailable in the workflow runtime
    anchor:    ""              // optional seed price; leave "" to let Gather fetch live
  }
})
```

**Ad-hoc research — equity / mixed** (`research-market`):

```js
Workflow({
  scriptPath: "./.agents/workflows/research-market.workflow.js",
  args: {
    question:  "NVDA pulled back 15% from ATH. I'm 40% concentrated in it. Should I trim?",
    portfolio: "40% NVDA, remainder unspecified. $1M tradfi book, no leverage.",
    date:      "2026-06-16"
    // assets + tickers are extracted from `question` by the manager LLM — no separate ticker arg needed
  }
})
```

**Weekly equity committee** (`hedge-fund-committee`):

```js
Workflow({
  scriptPath: "./.agents/workflows/hedge-fund-committee.workflow.js",
  args: { date: "2026-06-16" }  // no ticker needed — open-universe discovery
})
// Output: reports/hedge-fund-brief-<date>.md (30-sec read) + reports/hedge-fund-committee-<date>.md (full memo)
```

**Blind A/B comparison of two research reports** (`pairwise-eval`):

```js
Workflow({
  scriptPath: "./.agents/workflows/pairwise-eval.workflow.js",
  args: {
    a:        "/path/to/iter1.report.md",   // hypothesis: worse (baseline)
    b:        "/path/to/iter2.report.md",   // hypothesis: better (candidate)
    question: "BTC reached 65k from 61k. I hold 30% in COIN. Should I buy today?",
    judges:   5                             // number of blind judges; default 5
  }
})
```

### Output

Each research workflow writes:

- `research/research.crypto.<date>.md` or `research/research.stock.<date>.md` — the full report.
- A dated row in the `forecast-ledger` (`ledger.py`) — tracked for Brier-score grading.

### Deeper docs

| Doc | Purpose |
|---|---|
| `crypto/crypto.goal.md` | Crypto book mission + constraints |
| `crypto/crypto.prd.md` | Feature spec for the crypto workflow |
| `crypto/crypto.tdd.md` | Architecture + wiring diagrams |
| `crypto/eval/IMPROVE-LOOP.md` | How to improve a workflow with pairwise-eval |

---

## Install once, then just chat

One command installs every skill onto your agent. It auto-detects the host (Claude Code, openclaw, hermes, Cursor, +others), pulls all skills, and wires them in:

```bash
npx skills add dzianisv/financial-advisor-agents
```

That's the whole setup. **You don't run a workflow or type a slash command** — the skills route themselves from what you say. After install, just ask:

```
"Should I buy the dip on BTC today?"          → crypto-dip-scanner / research-onchain
"What did Buffett just buy?"                   → analyst-smartmoney-13f
"Run the weekly committee."                    → agentic-fund-orchestration
"What's the market regime right now?"          → regime-detection
"What would Lyn Alden think of this?"          → investor-lyn-alden
"Is there a multi-source convergence signal?"  → signal-convergence-alert
```

Each skill's description is written as a routing trigger, so the right desk answers the right question with no ceremony.

### Per-runtime install

| Runtime | Command |
|---|---|
| **Claude Code** | `npx skills add dzianisv/financial-advisor-agents` (auto-detected) |
| **openclaw** | `npx skills add dzianisv/financial-advisor-agents --agent openclaw --copy` |
| **hermes** | `npx skills add dzianisv/financial-advisor-agents --agent hermes-agent --copy` |

`--copy` ships the Python helper scripts alongside each `SKILL.md` (needed for the data-pulling skills). For scheduled/proactive operation (daily scans + weekly committee), see [`docs/`](docs/) — `setup-claudecode.md`, `setup-openclaw.md`, `setup-hermes.md`.

### The multi-agent workflows (Claude Code only)

`npx skills add` installs **skills**, not the dynamic [Workflow](https://code.claude.com/docs/en/workflows) scripts (the committee / panel orchestrators). Those are a Claude-Code-native feature — they live in `.claude/workflows/` and Claude Code exposes any `.js` there as a `/<name>` command. Two ways to get them:

```bash
# Option A — clone the repo, open Claude Code in it; the workflows are project /commands
git clone https://github.com/dzianisv/financial-advisor-agents && cd financial-advisor-agents
#   → /hedge-fund-committee   /research-market   /pairwise-eval   /multi-lens-quorum   /trend-stock-research

# Option B — make them global (available in every project)
cp financial-advisor-agents/.claude/workflows/*.js ~/.claude/workflows/
```

Then run e.g. `/hedge-fund-committee` or `/research-market`. (Needs Claude Code ≥ v2.1.154 with Dynamic workflows enabled in `/config`. Workflows are a Claude Code feature — openclaw/hermes use the skills, which orchestrate via their own primitives.)

> Note: some `.claude/workflows/*.js` entries are symlinks to `.agents/workflows/` (they resolve on macOS/Linux; on Windows copy the real files). `multi-lens-quorum.js` and `trend-stock-research.js` are standalone files in `.claude/workflows/` directly.

---

## Two active workstreams

### 1. Stocks / TradFi portfolio workflow

Manages a **~$1M tradfi book** (RSP 70 / GLD 15 / IEF 15 baseline) through an AI-bubble environment. Runs the loop: **regime-detect → scan → committee → human-approve → execute → report**.

Key artifacts:

| Artifact | Purpose |
|---|---|
| [`GOAL.md`](GOAL.md) | Mission + bubble evidence + done/not-done checklist |
| [`strategy/v3`](strategy/v3-bubble-aware-all-weather.md) | Bubble-Aware All-Weather strategy (the recommended allocation) |
| [`docs/prd.md`](docs/prd.md) | Features, cadence, personas |
| [`docs/tdd.md`](docs/tdd.md) | Architecture, wiring diagrams, data contracts |
| [`.agents/workflows/hedge-fund-committee.workflow.js`](.agents/workflows/) | Weekly committee → ranked next-buy memo |

**Status:** fast-tier daily scanners live on openclaw (cron + liveness); weekly committee workflow validated (3 iterations); congress stock-watch wired (`congress/`).

---

### 2. Crypto portfolio workflow

Manages a **~$177k crypto book** with a BTC-as-hurdle filter — only deploy into tokens that pass the 6-point infrastructure value-accrual test (HYPE the current benchmark).

Full spec: [`crypto/`](crypto/) — `crypto.goal.md` · `crypto.prd.md` · `crypto.tdd.md` · `crypto.loop.md`

**Panel architecture:** 5 school-based analyst seats run in parallel per token. Each seat owns its own data source — the technical seat uses TradingView MCP directly; others independently fetch DeFiLlama, F&G index, and news. The orchestrator (`crypto-advisor`) only passes `{ token, price_usd }` — no shared data package.

| Seat | School | Data source |
|---|---|---|
| Trend | Druckenmiller / Carver | TradingView MCP (direct) |
| Value | Graham / Klarman | web_fetch: price history, ATH |
| Quality | Buffett / Fisher | web_fetch: DeFiLlama revenue + TVL |
| Cycle | Dalio / Templeton | web_fetch: F&G index + macro news |
| On-chain | Burniske | web_fetch: DeFiLlama fee distribution |

Full spec: [`docs/crypto-advisor-panel.prd.md`](docs/crypto-advisor-panel.prd.md) · [`docs/crypto-advisor-panel.tdd.md`](docs/crypto-advisor-panel.tdd.md)

**Status:** Panel redesign complete (PRD + TDD shipped). Skill rewrite in progress. G-Eval baseline: 3.5/5 (signal_correctness and source_discipline are the gaps).

---

## Skills

### Workflows (5 total, all in `.claude/workflows/`)

| Slash command | Description |
|---|---|
| `/hedge-fund-committee` | Find the next stocks to BUY and hand over a STAGED ENTRY plan. Open-universe candidate discovery → panel vote → risk veto → scale-in plan. RECOMMEND-ONLY. |
| `/research-market` | Unified portfolio-aware research (crypto + equities). LLM manager discovers skills live, decides everything — assets, seats, panel, chair. Pass `question` + optional `portfolio` + `date`. |
| `/multi-lens-quorum` | Convene N independent analyst lenses on ONE judgment call; synthesize consensus without averaging away dissent. |
| `/trend-stock-research` | Research-first trend-stock screen: prescreen → parallel journalism → non-obvious beneficiary mapping → 3-question skeptic filter → route to multi-lens-quorum. |
| `/pairwise-eval` | Blind A/B comparison of two research reports — N position-randomized judges, majority vote. Used in the improve loop. |

### Data & monitoring

| Skill | Description |
|---|---|
| `analyst-smartmoney-13f` | Watch 13F filings, surface new initiations + cross-fund conviction clusters; dedupes candidates |
| `analyst-smartmoney-ptr` | Congressional stock trades feed |
| `crypto-dip-scanner` | Daily BTC/ETH/SOL/BNB/AVAX dip scanner; alerts on -30%+ from 52w high + extreme fear |
| `dip-screener` | Equity dip screener |
| `dip-tranches-strategy` | Staged entry / tranche sizing for dip entries |
| `feed-fomc` | Fed FOMC calendar, statement, and dot-plot monitor |
| `liveness-monitor` | Monitors that scheduled jobs are running; DMs on stale job |
| `portfolio-monitor` | Portfolio state monitor |
| `analyst-smartmoney-polymarket` | Polymarket / Kalshi odds for macro/market events |
| `regime-detection` | Market regime classifier (risk-on / risk-off / transition) |
| `signal-convergence-alert` | Multi-source convergence signal detector |

### Crypto data

| Skill | Description |
|---|---|
| `crypto-liquidity-data` | Crypto liquidity and ETF flow data seat |
| `crypto-onchain-data` | On-chain valuation data (MVRV-Z, NUPL, etc.) |
| `analyst-derivatives-positioning` | Derivatives and options positioning data seat |

### News feeds (feed-*)

| Skill | Description |
|---|---|
| `feed-bitcoinmagazine` | Bitcoin Magazine RSS/API adapter |
| `feed-coinbase` | Coinbase blog + institutional research / "Coinbase Bytes" first-party adapter (via Google News proxy) |
| `feed-coindesk` | CoinDesk RSS/API adapter |
| `feed-cointelegraph` | CoinTelegraph RSS/API adapter |
| `feed-decrypt` | Decrypt RSS/API adapter |
| `feed-theblock` | The Block RSS/API adapter |
| `feed-bloomberg` | Bloomberg macro/finance headline adapter |
| `feed-ft` | Financial Times headline adapter |
| `feed-wsj` | Wall Street Journal headline adapter |

### Research desks & chairs

| Skill | Description |
|---|---|
| `crypto-research-desk` | Consolidates crypto gather seats into one sourced brief |
| `stock-research-desk` | Consolidates equity gather seats into one sourced brief |
| `crypto-chair` | Crypto committee chair; portfolio-aware buy/sell decision |
| `stock-chair` | Equity committee chair; portfolio-aware buy/sell decision |
| `research-manager` | Intake/triage desk head; discovers skills live, assembles the research desk for any query |
| `narrative-news` | Consumes feed-* adapters → deduped events with priced-in tags |
| `crypto-news-store` | Dedup/state store for crypto news events |

### Analyst lenses (analyst-* / investor-* / research-*)

| Skill | Description |
|---|---|
| `research-onchain` | Crypto analyst lens |
| `analyst-systematic-trading` | Systematic/quant trading lens |
| `research-technical` | Technical analysis lens |
| `investor-benjamin-graham` | Value investing (Graham) lens |
| `research-lacy-hunt` | Deflationary/rates dissent lens (bear seat) |
| `investor-lyn-alden` | Lyn Alden macro/monetary lens |
| `research-michael-pettis` | Global imbalances / trade lens (Pettis) |
| `research-morgan-housel` | Behavioral/sizing guardrail (non-voting) |
| `investor-ray-dalio` | Macro cycles lens (Dalio) |
| `research-russell-napier` | Credit/financial repression lens (Napier) |
| `investor-stanley-druckenmiller` | Macro momentum lens (Druckenmiller) |
| `investor-warren-buffett` | Business quality / intrinsic value lens (equity only) |
| `research-defi` | DeFi on-chain seat (Burniske value-accrual) — DeFiLlama protocol revenue + fee distribution |
| `tradingview-fetch` | Fetches TradingView OHLCV + indicators for a token list, writes to .cache/tradingview/{date}/ |
| `macro-panel` | Multi-thinker macro panel conductor |
| `fundamental-analysis` | Equity fundamentals analysis |
| `superforecasting` | Tetlock-style probabilistic forecasting |

### Portfolio management

| Skill | Description |
|---|---|
| `agentic-fund-orchestration` | Top-level agentic hedge-fund orchestration playbook |
| `defi-portfolio-manager` | DeFi portfolio management |
| `hedge-fund-13f-analysis` | 13F filings analysis |
| `hedge-fund-manager` | Portfolio-level management and sizing |
| `multi-lens-quorum` | Convene N lenses on a judgment call |
| `portfolio-construction` | Portfolio construction and allocation |
| `rebalancing` | Rebalancing logic |
| `risk-management` | Risk management and position sizing |
| `tax-loss-harvesting` | Tax-loss harvesting |
| `tradfi-portfolio-manager` | TradFi portfolio manager skill |
| `trend-following` | Trend-following strategy |
| `trend-stock-research` | Research-first trend-stock screen |

### Evaluation & ops

| Skill | Description |
|---|---|
| `crypto-workflow-eval` | G-Eval harness for crypto workflow quality |
| `forecast-ledger` | Dated forecast log with Brier-score tracking |
| `hedge-fund-committee-eval` | Blind LLM judge for committee run quality |
| `skill-supervisor` | Skill quality supervision |

---

## Citation Validation Harness

Every `web_fetch` call during narrative analysis is logged and verified after each agent turn. Hallucinated sources (cited but never fetched) are caught **outside the LLM loop** — the agent cannot self-validate past this gate.

### How it works

```
Agent turn
  └─ postToolUse(web_fetch) ──► log-web-fetch.ts
                                  writes {url, success, ts} to /tmp/cc-fetches-{session}.jsonl

Agent finishes turn
  └─ agentStop / Stop ──────► validate-citations.ts
                                  regex-scans last response for [T1]/[T2]/[T3] https:// URLs
                                  diffs against fetch log
                                  cited but not fetched → HALLUCINATED_CITATION
                                  appends to logs/citation-errors.log
                                  warns in UI if failures found
```

### Runtime coverage

| Runtime | Hook config | Events |
|---|---|---|
| **Claude Code** | `.claude/settings.json` | `PostToolUse(web_fetch)` + `Stop` |
| **Copilot CLI** | `.github/hooks/citation-validator.json` | `postToolUse(matcher=web.?fetch)` + `agentStop` |
| **OpenCode** | `.opencode/plugins/citation-validator.ts` | `tool.execute.after` + `session.idle` |

All three runtimes share the same TypeScript scripts in `.claude/hooks/` — payload format is normalized across runtimes (`tool_input.url` for Claude Code, `toolArgs` JSON for Copilot CLI).

### Audit log

Failures append to `logs/citation-errors.log`:
```
2026-06-22T17:30:00Z   session-abc   HALLUCINATED_CITATION   https://coindesk.com/fake-article
```

### Testing

```bash
# Verify hooks are wired (Claude Code)
# Open Claude Code in this repo → /hooks → should show PostToolUse + Stop entries

# Trigger a test turn with a bad citation
# Ask the agent to cite a URL, then check:
tail -f logs/citation-errors.log
```

---

## Deployment targets

Same skills install onto any of:

| Runtime | Scheduling primitive | Notification |
|---|---|---|
| **Claude Code** | `/loop` + Routines + dynamic workflows | terminal / push |
| **openclaw** | `heartbeat` + `HEARTBEAT.md` | Telegram DM |
| **hermes-ai** | hermes scheduler | configured channel |

---

## Repository layout

```
GOAL.md                    # tradfi mission north-star
crypto/                    # crypto workflow spec (goal / prd / tdd / loop)
strategy/                  # v1→v3 strategy evolution; v3 = current recommended allocation
research/                  # cited research notes (AI bubble, crypto, macro, frameworks)
backtests/                 # runnable backtest scripts + cached results
docs/                      # prd / tdd / setup guides (openclaw / claude-code / hermes)
.agents/skills/            # all skill modules (SKILL.md + implementation)
.agents/workflows/         # multi-agent workflow scripts
congress/                  # congressional stock-watch feed
report/                    # generated charts + published write-ups
```

---

## Backtest summary (tradfi v3)

1. **Don't bet the whole $1M on cap-weight S&P/QQQ at CAPE ~41.** 2000-2026 backtest: S&P −55%, QQQ −83%; 2000-2009 was a lost decade.
2. **Selection isn't the edge.** Bottom-up stock-picking doesn't reliably beat a cheap index (backtests + SPIVA).
3. **The edge is structural.** De-concentrated diversification + trend/regime overlay (crisis alpha) + dip-reserve = caps left tail without a market call. → [`strategy/v3`](strategy/v3-bubble-aware-all-weather.md)

Tracking issue: https://github.com/dzianisv/financial-advisor-agents/issues/1
