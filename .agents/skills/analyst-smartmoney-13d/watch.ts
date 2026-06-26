#!/usr/bin/env -S node --experimental-strip-types
/**
 * 13D Watch — Dedup Ledger + Activist Roster Manager
 *
 * Subcommands:
 *   roster                   List tracked activists (from roster.json)
 *   seen <TICKER> [filing]   Check if ticker+filing_type combo already recommended (exit 0=seen, 1=new)
 *   record                   Record a new recommendation (reads JSON from stdin)
 *   list [--json]            List all recorded recommendations
 *
 * Storage: JSONL at $THIRTEEND_LEDGER or .cache/13D/recommended.jsonl
 * Roster:  JSON  at $THIRTEEND_ROSTER or .cache/13D/roster.json
 *
 * Exit codes: 0=seen/success, 1=new/not-found, 2=error, 3=dup-on-record
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { parseArgs } from "node:util";

// --- Types ---

interface RosterEntry {
  id: string;
  name: string;
  cik?: string;
  style: string;
  notes?: string;
}

interface LedgerRecord {
  ticker: string;
  filing_type: "13D" | "13G" | "13F" | "STOCK_ACT";
  filer: string;
  filing_date?: string;  // YYYY-MM-DD — part of dedup key so a new filing on the same ticker+filer re-alerts
  stake_pct?: number;
  intent?: string;
  score?: number;
  tier?: number;
  action: string;
  reason: string;
  price_at_rec?: number;
  source: string;
  recommended_on: string;
}

// --- Paths ---

const SCRIPT_DIR = dirname(new URL(import.meta.url).pathname);
const REPO_ROOT = join(SCRIPT_DIR, "..", "..", "..");
const LEDGER_PATH =
  process.env.THIRTEEND_LEDGER || join(REPO_ROOT, ".cache", "13D", "recommended.jsonl");
const ROSTER_PATH =
  process.env.THIRTEEND_ROSTER || join(REPO_ROOT, ".cache", "13D", "roster.json");

// --- Helpers ---

function ensureDir(filePath: string): void {
  const dir = dirname(filePath);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function loadLedger(): LedgerRecord[] {
  if (!existsSync(LEDGER_PATH)) return [];
  return readFileSync(LEDGER_PATH, "utf-8")
    .split("\n")
    .filter((line: string) => line.trim())
    .map((line: string) => JSON.parse(line) as LedgerRecord);
}

function appendLedger(record: LedgerRecord): void {
  ensureDir(LEDGER_PATH);
  writeFileSync(LEDGER_PATH, JSON.stringify(record) + "\n", { flag: "a" });
}

function loadRoster(): RosterEntry[] {
  if (!existsSync(ROSTER_PATH)) {
    console.error(`Roster not found: ${ROSTER_PATH}`);
    process.exit(2);
  }
  return JSON.parse(readFileSync(ROSTER_PATH, "utf-8")) as RosterEntry[];
}

// --- Subcommands ---

function cmdRoster(): void {
  const roster = loadRoster();
  console.log(`Tracked activists (${roster.length}):\n`);
  for (const entry of roster) {
    const cik = entry.cik ? ` [CIK: ${entry.cik}]` : "";
    const notes = entry.notes ? ` — ${entry.notes}` : "";
    console.log(`  ${entry.name}${cik} (${entry.style})${notes}`);
  }
}

function cmdSeen(ticker: string, filingType?: string, filingDate?: string): void {
  if (!ticker) {
    console.error("Usage: watch.ts seen <TICKER> [filing_type] [filing_date]");
    process.exit(2);
  }
  const records = loadLedger();
  const upperTicker = ticker.toUpperCase();
  const match = records.find(
    (r: LedgerRecord) =>
      r.ticker.toUpperCase() === upperTicker &&
      (!filingType || r.filing_type === filingType.toUpperCase()) &&
      (!filingDate || (r.filing_date ?? "") === filingDate)
  );

  if (match) {
    console.log(
      `SEEN: ${upperTicker} (${match.filing_type}) filed ${match.filing_date ?? "?"} — recorded ${match.recommended_on} by ${match.filer}`
    );
    process.exit(0);
  } else {
    console.log(
      `NEW: ${upperTicker}${filingType ? ` (${filingType})` : ""}${filingDate ? ` filed ${filingDate}` : ""} not in ledger`
    );
    process.exit(1);
  }
}

function cmdRecord(): void {
  let input = "";
  try {
    input = readFileSync("/dev/stdin", "utf-8");
  } catch {
    console.error("Error reading stdin. Pipe a JSON record.");
    process.exit(2);
  }

  let record: LedgerRecord;
  try {
    record = JSON.parse(input) as LedgerRecord;
  } catch {
    console.error("Invalid JSON on stdin.");
    process.exit(2);
  }

  // Validate required fields
  const required = ["ticker", "filing_type", "filer", "action", "reason", "source"] as const;
  for (const field of required) {
    if (!record[field]) {
      console.error(`Missing required field: ${field}`);
      process.exit(2);
    }
  }

  // Set recommended_on if not provided
  if (!record.recommended_on) {
    record.recommended_on = new Date().toISOString().split("T")[0]!;
  }

  // Dedup check: ticker + filing_type + filer + filing_date
  // filing_date is the identity of the specific filing event; missing field ("") matches "" only,
  // so a new filing date on the same ticker+filer re-alerts rather than being permanently suppressed.
  const existing = loadLedger();
  const dup = existing.find(
    (r: LedgerRecord) =>
      r.ticker.toUpperCase() === record.ticker.toUpperCase() &&
      r.filing_type === record.filing_type &&
      r.filer.toLowerCase() === record.filer.toLowerCase() &&
      (r.filing_date ?? "") === (record.filing_date ?? "")
  );
  if (dup) {
    console.log(
      `DUP: ${record.ticker} (${record.filing_type}) by ${record.filer} filed ${record.filing_date ?? "?"} already recorded ${dup.recommended_on}`
    );
    process.exit(3);
  }

  appendLedger(record);
  console.log(
    `RECORDED: ${record.ticker} (${record.filing_type}) by ${record.filer} — score: ${record.score ?? "N/A"}, tier: ${record.tier ?? "N/A"}`
  );
}

function cmdList(asJson: boolean): void {
  const records = loadLedger();
  if (records.length === 0) {
    console.log("No recommendations recorded yet.");
    return;
  }
  if (asJson) {
    console.log(JSON.stringify(records, null, 2));
  } else {
    console.log(`Recommendations (${records.length}):\n`);
    for (const r of records) {
      const score = r.score != null ? `score=${r.score}` : "";
      const tier = r.tier != null ? `T${r.tier}` : "";
      const tag = [score, tier].filter(Boolean).join(" ");
      console.log(
        `  ${r.recommended_on}  ${r.ticker.padEnd(6)} ${r.filing_type.padEnd(10)} by ${r.filer.padEnd(20)} ${tag}`
      );
      console.log(`    Action: ${r.action} | ${r.reason}`);
    }
  }
}

// --- Main ---

const { positionals, values } = parseArgs({
  allowPositionals: true,
  options: {
    json: { type: "boolean", default: false },
    help: { type: "boolean", short: "h", default: false },
  },
});

const [command, ...args] = positionals;

if (values.help || !command) {
  console.log(`Usage: watch.ts <command> [args]

Commands:
  roster              List tracked activists
  seen <TICKER> [type]  Check if ticker (+filing type) is already recommended
  record              Record a recommendation (pipe JSON to stdin)
  list [--json]       List all recommendations`);
  process.exit(0);
}

switch (command) {
  case "roster":
    cmdRoster();
    break;
  case "seen":
    cmdSeen(args[0]!, args[1], args[2]);
    break;
  case "record":
    cmdRecord();
    break;
  case "list":
    cmdList(values.json as boolean);
    break;
  default:
    console.error(`Unknown command: ${command}`);
    process.exit(2);
}
