// End-to-end tests for portfolio-memory recall.ts + remember.ts.
// Exercises the real CLIs via subprocess (not internal fns) so we validate the
// contract the skills actually depend on. Run: bun test .agents/skills/portfolio-memory/memory.test.ts
import { test, expect } from "bun:test";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const REMEMBER = path.join(import.meta.dir, "remember.ts");
const RECALL = path.join(import.meta.dir, "recall.ts");

function freshDir(): string {
  return mkdtempSync(path.join(tmpdir(), "pmem-"));
}

function remember(dir: string, args: string[]): { out: string; code: number } {
  const r = Bun.spawnSync(["bun", REMEMBER, "--dir", dir, ...args], { stdout: "pipe", stderr: "pipe" });
  return { out: new TextDecoder().decode(r.stdout) + new TextDecoder().decode(r.stderr), code: r.exitCode };
}
function recall(dir: string, args: string[]): { out: string; code: number } {
  const r = Bun.spawnSync(["bun", RECALL, "--dir", dir, ...args], { stdout: "pipe", stderr: "pipe" });
  return { out: new TextDecoder().decode(r.stdout), code: r.exitCode };
}
const positions = (dir: string) =>
  existsSync(path.join(dir, "positions.md")) ? readFileSync(path.join(dir, "positions.md"), "utf8") : "";
const canonLines = (dir: string) =>
  positions(dir).split("\n").filter((l) => l.trim() && !l.trim().startsWith("#"));

test("new verdict creates exactly one canonical line, tagged [new]", () => {
  const dir = freshDir();
  const { out } = remember(dir, ["--desk", "stocks", "--ticker", "COIN", "--verdict", "HOLD", "--date", "2026-06-24", "--conviction", "3", "--body", "crypto bullish; below 200d"]);
  expect(out).toContain("[new]");
  const lines = canonLines(dir).filter((l) => l.startsWith("stocks:COIN |"));
  expect(lines.length).toBe(1);
  expect(lines[0]).toContain("HOLD");
});

test("same-day supersede overwrites canonical (one line), keeps both in dated log", () => {
  const dir = freshDir();
  remember(dir, ["--desk", "stocks", "--ticker", "COIN", "--verdict", "HOLD", "--date", "2026-06-24", "--body", "keep core"]);
  const { out } = remember(dir, ["--desk", "stocks", "--ticker", "COIN", "--verdict", "TRIM", "--date", "2026-06-24", "--body", "harvest half"]);
  expect(out).toContain("[superseded]");
  const coin = canonLines(dir).filter((l) => l.startsWith("stocks:COIN |"));
  expect(coin.length).toBe(1); // supersede, not duplicate
  expect(coin[0]).toContain("TRIM");
  expect(coin[0]).not.toContain("HOLD");
  // dated log keeps the full audit trail
  const dated = readFileSync(path.join(dir, "2026-06-24.md"), "utf8");
  expect(dated).toContain("COIN HOLD");
  expect(dated).toContain("COIN TRIM");
});

test("different tickers coexist as separate canonical lines", () => {
  const dir = freshDir();
  remember(dir, ["--desk", "stocks", "--ticker", "COIN", "--verdict", "HOLD", "--date", "2026-06-24", "--body", "x"]);
  remember(dir, ["--desk", "stocks", "--ticker", "PYPL", "--verdict", "EXIT", "--date", "2026-06-24", "--body", "value trap"]);
  expect(canonLines(dir).length).toBe(2);
});

test("desk isolation: stocks:COIN and crypto:COIN are distinct; recall --desk filters canonical", () => {
  const dir = freshDir();
  remember(dir, ["--desk", "stocks", "--ticker", "COIN", "--verdict", "HOLD", "--date", "2026-06-24", "--body", "stock"]);
  remember(dir, ["--desk", "crypto", "--ticker", "COIN", "--verdict", "BUY", "--date", "2026-06-24", "--body", "token"]);
  expect(canonLines(dir).filter((l) => l.startsWith("stocks:COIN |")).length).toBe(1);
  expect(canonLines(dir).filter((l) => l.startsWith("crypto:COIN |")).length).toBe(1);
  const { out } = recall(dir, ["--desk", "stocks", "--tickers", "COIN"]);
  expect(out).toContain("stocks:COIN");
  // crypto canonical line must not leak into a stocks recall's canonical block
  const canonBlock = out.split("episodic")[0];
  expect(canonBlock).not.toContain("crypto:COIN");
});

test("recall shows canonical (current) first, then dated history newest-first", () => {
  const dir = freshDir();
  remember(dir, ["--desk", "stocks", "--ticker", "COIN", "--verdict", "WATCH", "--date", "2026-06-20", "--body", "older note"]);
  remember(dir, ["--desk", "stocks", "--ticker", "COIN", "--verdict", "TRIM", "--date", "2026-06-24", "--body", "newer note"]);
  const { out } = recall(dir, ["--desk", "stocks", "--tickers", "COIN"]);
  expect(out).toContain("canonical");
  // canonical reflects latest write
  const canonBlock = out.split("episodic")[0];
  expect(canonBlock).toContain("TRIM");
  // dated: 2026-06-24 must appear before 2026-06-20 (recency)
  const i24 = out.indexOf("[2026-06-24]");
  const i20 = out.indexOf("[2026-06-20]");
  expect(i24).toBeGreaterThan(-1);
  expect(i20).toBeGreaterThan(-1);
  expect(i24).toBeLessThan(i20);
});

test("recall with no --tickers returns all canonical incl preferences", () => {
  const dir = freshDir();
  remember(dir, ["--desk", "stocks", "--ticker", "PREF_CRYPTO", "--verdict", "HOLD", "--date", "2026-06-24", "--body", "crypto bullish — do not force-sell COIN"]);
  const { out } = recall(dir, ["--desk", "stocks"]);
  expect(out).toContain("PREF_CRYPTO");
});

test("recall on empty memory prints sentinel and exits 0", () => {
  const dir = freshDir();
  const { out, code } = recall(dir, ["--desk", "stocks", "--tickers", "COIN"]);
  expect(code).toBe(0);
  expect(out).toContain("[no prior memory for this run]");
});

test("ticker matching is word-boundary: 'CO' does not match 'COIN'", () => {
  const dir = freshDir();
  remember(dir, ["--desk", "stocks", "--ticker", "COIN", "--verdict", "HOLD", "--date", "2026-06-24", "--body", "x"]);
  const { out } = recall(dir, ["--desk", "stocks", "--tickers", "CO"]);
  expect(out).toContain("[no prior memory for this run]");
});

test("remember requires --ticker and --verdict (exits non-zero otherwise)", () => {
  const dir = freshDir();
  const { code } = remember(dir, ["--desk", "stocks", "--ticker", "COIN", "--date", "2026-06-24", "--body", "missing verdict"]);
  expect(code).not.toBe(0);
});

test("verdict is normalized to upper-case in canonical line", () => {
  const dir = freshDir();
  remember(dir, ["--desk", "stocks", "--ticker", "NVDA", "--verdict", "buy", "--date", "2026-06-24", "--body", "x"]);
  expect(canonLines(dir).find((l) => l.startsWith("stocks:NVDA |"))).toContain("BUY");
});
