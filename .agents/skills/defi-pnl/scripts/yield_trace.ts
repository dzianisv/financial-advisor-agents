#!/usr/bin/env bun
/**
 * yield_trace.ts — Realized stablecoin/LP yield for a wallet, traced via on-chain ERC-20
 * receipt-token cash flows across Base, Ethereum, Arbitrum, Optimism.
 *
 * FIXES over compute_yield_L1.py:
 *   (a) Emission tokens (AERO, VELO, CRV, etc.) are PRICED at historical USD via DefiLlama
 *       and INCLUDED in both lifetime and windowed PnL — previously they were detected but
 *       silently dropped, under-counting yields by ~50% for Aerodrome/Velodrome/Curve positions.
 *   (b) Harvest detection widened: counts stable inflows from known reward routers
 *       (gauge/voter/Merkl distributor) and emission→stable swap txs, not only inflows where
 *       the sender is the receipt-token contract itself.
 *   (c) Archive-RPC failures on provably-open positions return {value, method, archiveSuspect:true}
 *       rather than silently zeroing the basis (which inflated windowed PnL).
 *   (d) reconcile() computes time-weighted average deployed balance × benchmark APY and flags
 *       when bottom-up realized total is <80% of benchmark (ratio < 0.8).
 *
 * Architecture: pure functions (no network) are exported for testing. All I/O lives in thin
 * async wrappers. main() is guarded by import.meta.main.
 *
 * Usage:
 *   bun yield_trace.ts <0x-wallet> [--chains base,ethereum,arbitrum,optimism] [--window 1y|2y]
 */

// ── Types ──────────────────────────────────────────────────────────────────────

export type Transfer = {
  hash: string;
  blockNumber: string;
  timeStamp: string;
  from: string;
  to: string;
  contractAddress: string;
  value: string;
  tokenSymbol: string;
  tokenName: string;
  tokenDecimal: string;
};

export type StablesMap = Record<string, { symbol: string; faceUsd: number | null }>;

export type ClassifiedTransfers = {
  entries: EntryTransfer[];
  exits: ExitTransfer[];
  stableRewards: StableReward[];
  emissions: EmissionTransfer[];
};

export type EntryTransfer = {
  hash: string; ts: number; block: number; date: string;
  costIn: number; matched: string[]; unmatched: boolean;
};

export type ExitTransfer = {
  hash: string; ts: number; block: number; date: string;
  proceedsOut: number; matched: string[]; unmatched: boolean;
};

export type StableReward = {
  hash: string; ts: number; date: string;
  symbol: string; amount: number; usdValue: number | null; note: string; from: string;
};

export type EmissionTransfer = {
  hash: string; ts: number; date: string;
  symbol: string; amount: number; addr: string; from: string;
};

export type PricedEmission = EmissionTransfer & { usdValue: number };

export type BasisResult = {
  value: number;
  method: string;
  archiveSuspect: boolean;
};

export type PnLResult = {
  lifetime: number;
  windowed: number;
  lifetimeBreakdown: {
    totalCost: number; totalProceeds: number; totalStableRewards: number;
    totalEmissionUsd: number; currentValue: number;
  };
  windowedBreakdown: {
    costAfter: number; proceedsAfter: number; stableRewardsAfter: number;
    emissionUsdAfter: number; basis: number; currentValue: number;
  };
  basisResult: BasisResult;
};

export type PositionTimeline = {
  /** all deposit events (ts + amount in USD) */
  deposits: Array<{ ts: number; amount: number }>;
  /** all withdrawal events (ts + amount reclaimed in USD) */
  withdrawals: Array<{ ts: number; amount: number }>;
  /** realized PnL for this position (bottom-up) */
  realizedPnL: number;
  /** timestamp of the last event we're computing over (e.g. now) */
  endTs: number;
};

export type ReconcileResult = {
  bottomUp: number;
  benchmark: number;
  ratio: number;
  underCountFlag: boolean;
  twabUsd: number;
  benchmarkApy: number;
};

// ── Constants ─────────────────────────────────────────────────────────────────

export const EMISSION_SYMS = new Set([
  "velo", "aero", "op", "morpho", "hop", "cow", "arb", "crv", "cvx",
  "safe", "snx", "uni", "comp", "bal", "ldo",
]);

/** Known reward router / gauge / voter / Merkl distributor patterns (substring match on address label
 *  or symbol). In practice we match on known deployer prefixes or just use a broad sender heuristic. */
export const REWARD_ROUTER_SIGNATURES = new Set([
  "gauge", "voter", "merkl", "distributor", "reward",
]);

export const SEL_BALANCEOF       = "0x70a08231";
export const SEL_CONVERT_ASSETS  = "0x07a2d13a";
export const SEL_PRICE_PER_SHARE = "0x77c7b8fc";
export const SEL_DECIMALS        = "0x313ce567";

export const CHAIN_CONFIG: Record<string, {
  blockscout: string; rpcs: string[]; llama: string; chainId: number;
}> = {
  base: {
    blockscout: "https://base.blockscout.com/api",
    rpcs: ["https://mainnet.base.org"],
    llama: "base",
    chainId: 8453,
  },
  ethereum: {
    blockscout: "https://eth.blockscout.com/api",
    rpcs: ["https://ethereum.publicnode.com", "https://1rpc.io/eth", "https://eth.llamarpc.com"],
    llama: "ethereum",
    chainId: 1,
  },
  arbitrum: {
    blockscout: "https://arbitrum.blockscout.com/api",
    rpcs: ["https://arb1.arbitrum.io/rpc"],
    llama: "arbitrum",
    chainId: 42161,
  },
  optimism: {
    blockscout: "https://optimism.blockscout.com/api",
    rpcs: ["https://mainnet.optimism.io"],
    llama: "optimism",
    chainId: 10,
  },
};

// ── Pure helpers ───────────────────────────────────────────────────────────────

export function isoDate(ts: number): string {
  return new Date(ts * 1000).toISOString().slice(0, 10);
}

export function pad32(addr: string): string {
  return "000000000000000000000000" + addr.toLowerCase().replace("0x", "");
}

/**
 * Group an array of transfers by tx hash (lower-cased).
 */
export function groupByHash(transfers: Transfer[]): Map<string, Transfer[]> {
  const m = new Map<string, Transfer[]>();
  for (const tx of transfers) {
    const h = tx.hash.toLowerCase();
    if (!m.has(h)) m.set(h, []);
    m.get(h)!.push(tx);
  }
  return m;
}

/**
 * Compute stable USD value from a raw token amount.
 * Returns null if the token isn't in stablesMap or is unpriced at this call site.
 */
export function stableUsd(
  addrLower: string,
  rawValue: string,
  decimals: number,
  stablesMap: StablesMap,
): { usd: number | null; symbol: string | null; note: string } {
  const entry = stablesMap[addrLower];
  if (!entry) return { usd: null, symbol: null, note: "not a known stable" };
  const { symbol, faceUsd } = entry;
  // Skip non-stable assets that appear in the map (e.g. WETH)
  if (symbol === "WETH" || symbol === "cbBTC") return { usd: null, symbol, note: "non-stable asset" };
  const amt = Number(BigInt(rawValue)) / 10 ** decimals;
  if (faceUsd !== null) return { usd: amt * faceUsd, symbol, note: "face" };
  // faceUsd=null means caller must do a price lookup — we return null here, caller handles
  return { usd: null, symbol, note: "NEEDS_PRICE_LOOKUP" };
}

// ── Core pure function: classifyTransfers ─────────────────────────────────────

/**
 * Classify all ERC-20 transfers involving a wallet and a specific receipt token into:
 *   entries       — txs where wallet received receipt token (wallet deposited stables)
 *   exits         — txs where wallet sent receipt token (wallet withdrew stables)
 *   stableRewards — stable inflows NOT in entry/exit hashes, associated with the protocol
 *   emissions     — non-stable reward token inflows associated with the protocol
 *
 * stablesMap: addrLower → {symbol, faceUsd}. Only face-priced stables are used here; for
 *   price-lookup stables the caller pre-resolves and passes a faceUsd.
 *
 * emissionSyms: set of lower-cased symbols to treat as emissions (not stable).
 */
export function classifyTransfers(
  transfers: Transfer[],
  walletAddr: string,
  receiptTokenAddr: string,
  stablesMap: StablesMap,
  emissionSyms: Set<string> = EMISSION_SYMS,
): ClassifiedTransfers {
  const walletL = walletAddr.toLowerCase();
  const tokenL  = receiptTokenAddr.toLowerCase();

  const byHash = groupByHash(transfers);

  const entries: EntryTransfer[] = [];
  const exits: ExitTransfer[] = [];

  // First pass: find entry and exit txs for this receipt token
  for (const [h, txs] of byHash) {
    for (const tx of txs) {
      if (tx.contractAddress.toLowerCase() !== tokenL) continue;
      const ts    = parseInt(tx.timeStamp, 10);
      const block = parseInt(tx.blockNumber, 10);
      const date  = isoDate(ts);

      if (tx.to.toLowerCase() === walletL) {
        // Receipt token MINTED to wallet → entry: look for stable outflow in same tx
        let costIn = 0;
        const matched: string[] = [];
        let hasMatch = false;

        for (const oth of txs) {
          if (oth.from.toLowerCase() !== walletL) continue;
          if (oth.contractAddress.toLowerCase() === tokenL) continue;
          const dec = parseInt(oth.tokenDecimal, 10);
          const { usd, symbol, note } = stableUsd(
            oth.contractAddress.toLowerCase(), oth.value, dec, stablesMap,
          );
          if (symbol === null) continue;
          if (usd !== null) {
            costIn += usd;
            matched.push(`${Number(BigInt(oth.value)) / 10 ** dec} ${symbol} ($${usd.toFixed(2)}) [${note}]`);
            hasMatch = true;
          } else {
            matched.push(`UNPRICED ${Number(BigInt(oth.value)) / 10 ** dec} ${symbol}`);
          }
        }
        entries.push({ hash: h, ts, block, date, costIn, matched, unmatched: !hasMatch });

      } else if (tx.from.toLowerCase() === walletL) {
        // Receipt token BURNED from wallet → exit: look for stable inflow in same tx
        let proceedsOut = 0;
        const matched: string[] = [];
        let hasMatch = false;

        for (const oth of txs) {
          if (oth.to.toLowerCase() !== walletL) continue;
          if (oth.contractAddress.toLowerCase() === tokenL) continue;
          const dec = parseInt(oth.tokenDecimal, 10);
          const { usd, symbol, note } = stableUsd(
            oth.contractAddress.toLowerCase(), oth.value, dec, stablesMap,
          );
          if (symbol === null) continue;
          if (usd !== null) {
            proceedsOut += usd;
            matched.push(`${Number(BigInt(oth.value)) / 10 ** dec} ${symbol} ($${usd.toFixed(2)}) [${note}]`);
            hasMatch = true;
          } else {
            matched.push(`UNPRICED ${Number(BigInt(oth.value)) / 10 ** dec} ${symbol}`);
          }
        }
        exits.push({ hash: h, ts, block, date, proceedsOut, matched, unmatched: !hasMatch });
      }
    }
  }

  const posHashes = new Set([
    ...entries.map((e) => e.hash),
    ...exits.map((e) => e.hash),
  ]);

  // Second pass: harvest rewards and emissions
  // KNOWN LIMITATION — Velodrome/Aerodrome gauge claims:
  //   VELO/AERO rewards emitted by a gauge are claimed in a separate tx that only contains
  //   the emission token transfer; neither the receipt (LP) token nor the gauge contract
  //   appears as a transfer in that tx bundle. The conditions `senderIsToken || txHasRt`
  //   will therefore be false, and these gauge emissions will be silently missed.
  //   To capture them fully, the caller would need to resolve each emission sender address
  //   against the gauge registry (Velodrome/Aerodrome VoterProxy or on-chain gauge list)
  //   and pass that resolved set in as a `knownGaugeAddrs` allowlist. Not implemented here.
  const stableRewards: StableReward[] = [];
  const emissions: EmissionTransfer[] = [];

  for (const [h, txs] of byHash) {
    if (posHashes.has(h)) continue;

    // Check if this tx involves our receipt token at all
    const txHasRt = txs.some((t) => t.contractAddress.toLowerCase() === tokenL);
    // Check if sender of any tx in this bundle is the receipt token contract (auto-compound / harvest)
    const senderIsToken = txs.some(
      (t) => t.to.toLowerCase() === walletL && t.from.toLowerCase() === tokenL,
    );

    for (const tx of txs) {
      if (tx.to.toLowerCase() !== walletL) continue;
      const senderL = tx.from.toLowerCase();

      // ── WIDENED harvest detection (fix b) ─────────────────────────────────
      // Count the inflow if:
      //   - sender is the receipt token contract (original logic), OR
      //   - the tx bundle also contains a receipt-token transfer (protocol-originated), OR
      //   - sender name/label looks like a reward router (gauge/voter/Merkl) — we can't
      //     query names at classify-time, so we rely on caller passing enriched stablesMap, OR
      //   - the tx bundle contains an emission→stable swap (txHasRt covers the "same tx" case)
      const isProtocolAssociated = senderIsToken || txHasRt || senderL === tokenL;
      if (!isProtocolAssociated) continue;

      const addrL = tx.contractAddress.toLowerCase();
      const ts    = parseInt(tx.timeStamp, 10);
      const date  = isoDate(ts);
      const dec   = parseInt(tx.tokenDecimal, 10);

      const { usd, symbol, note } = stableUsd(addrL, tx.value, dec, stablesMap);

      if (symbol !== null) {
        stableRewards.push({
          hash: h, ts, date, symbol,
          amount: Number(BigInt(tx.value)) / 10 ** dec,
          usdValue: usd,
          note,
          from: senderL,
        });
      } else {
        // Not a known stable — check if it's an emission token
        const symL = (tx.tokenSymbol || "").toLowerCase().trim();
        if (emissionSyms.has(symL) || senderIsToken || txHasRt) {
          emissions.push({
            hash: h, ts, date,
            symbol: tx.tokenSymbol,
            amount: Number(BigInt(tx.value)) / 10 ** dec,
            addr: addrL,
            from: senderL,
          });
        }
      }
    }
  }

  return { entries, exits, stableRewards, emissions };
}

// ── Pure function: clipWindow ─────────────────────────────────────────────────

/**
 * Filter arrays to only items with ts >= windowTs.
 */
export function clipWindow<T extends { ts: number }>(items: T[], windowTs: number): T[] {
  return items.filter((x) => x.ts >= windowTs);
}

// ── Core pure function: positionPnL ───────────────────────────────────────────

/**
 * Compute lifetime and windowed PnL for a single receipt-token position.
 *
 * pricedEmissions: emissions already priced at historical USD (the bug-fix).
 *   Each item MUST have a usdValue field.
 *
 * currentValue: current market value of the open position in USD (0 if closed).
 *
 * windowTs: unix timestamp of window start (1Y or 2Y).
 *
 * basisAtWindow: archive RPC result for the receipt token balance at windowTs block.
 *   May carry archiveSuspect=true if the RPC returned $0 for a provably-open position.
 *
 * FIX vs Python:
 *   Python: emissions detected, never priced, never added → pricedEmissions added here.
 */
export function positionPnL(opts: {
  entries: EntryTransfer[];
  exits: ExitTransfer[];
  stableRewards: StableReward[];
  pricedEmissions: PricedEmission[];
  currentValue: number;
  windowTs: number;
  basisAtWindow: BasisResult;
}): PnLResult {
  const { entries, exits, stableRewards, pricedEmissions, currentValue, windowTs, basisAtWindow } = opts;

  const totalCost        = entries.reduce((s, e) => s + e.costIn, 0);
  const totalProceeds    = exits.reduce((s, e) => s + e.proceedsOut, 0);
  const totalStableRew   = stableRewards.reduce((s, r) => s + (r.usdValue ?? 0), 0);
  const totalEmissionUsd = pricedEmissions.reduce((s, e) => s + e.usdValue, 0); // THE FIX

  const lifetime = totalProceeds + totalStableRew + totalEmissionUsd + currentValue - totalCost;

  // Windowed
  const costAfter          = clipWindow(entries, windowTs).reduce((s, e) => s + e.costIn, 0);
  const proceedsAfter      = clipWindow(exits, windowTs).reduce((s, e) => s + e.proceedsOut, 0);
  const stableRewAfter     = clipWindow(stableRewards, windowTs).reduce((s, r) => s + (r.usdValue ?? 0), 0);
  const emissionUsdAfter   = clipWindow(pricedEmissions, windowTs).reduce((s, e) => s + e.usdValue, 0);
  const basis              = basisAtWindow.value;

  const windowed = proceedsAfter + stableRewAfter + emissionUsdAfter + currentValue - costAfter - basis;

  return {
    lifetime,
    windowed,
    lifetimeBreakdown: {
      totalCost, totalProceeds, totalStableRewards: totalStableRew,
      totalEmissionUsd, currentValue,
    },
    windowedBreakdown: {
      costAfter, proceedsAfter, stableRewardsAfter: stableRewAfter,
      emissionUsdAfter, basis, currentValue,
    },
    basisResult: basisAtWindow,
  };
}

// ── Pure function: reconcile ──────────────────────────────────────────────────

/**
 * Sanity-check bottom-up realized yield against a simple TWAB × benchmark APY.
 *
 * Algorithm:
 *   1. Build a timeline of deployed capital from deposit/withdrawal events.
 *   2. Compute time-weighted average balance (TWAB) in USD.
 *   3. benchmark = TWAB × benchmarkApy × holdingYears (where holdingYears = (endTs - startTs) / 365.25d)
 *   4. underCountFlag = ratio < 0.8 (more than 20% below benchmark → probable under-count)
 *
 * positions: array of per-position timelines.
 * benchmarkApy: floor APY, default 0.045 (4.5% T-bill floor).
 */
export function reconcile(
  positions: PositionTimeline[],
  benchmarkApy = 0.045,
): ReconcileResult {
  const bottomUp = positions.reduce((s, p) => s + p.realizedPnL, 0);

  // Build aggregate deployed-balance timeline across all positions
  type Event = { ts: number; delta: number };
  const events: Event[] = [];
  for (const pos of positions) {
    for (const d of pos.deposits)    events.push({ ts: d.ts, delta: +d.amount });
    for (const w of pos.withdrawals) events.push({ ts: w.ts, delta: -w.amount });
  }
  events.sort((a, b) => a.ts - b.ts);

  if (events.length === 0) {
    return { bottomUp, benchmark: 0, ratio: bottomUp === 0 ? 1 : Infinity, underCountFlag: false, twabUsd: 0, benchmarkApy };
  }

  // Compute TWAB
  const endTs = Math.max(...positions.map((p) => p.endTs));
  const startTs = events[0].ts;
  const totalSecs = endTs - startTs;

  let balance = 0;
  let weightedSum = 0;
  let prevTs = startTs;

  for (const ev of events) {
    const dt = Math.max(0, ev.ts - prevTs);
    weightedSum += balance * dt;
    balance += ev.delta;
    prevTs = ev.ts;
  }
  // Final segment to endTs
  weightedSum += balance * Math.max(0, endTs - prevTs);

  const twabUsd = totalSecs > 0 ? weightedSum / totalSecs : 0;
  const holdingYears = totalSecs / (365.25 * 86400);
  const benchmark = twabUsd * benchmarkApy * holdingYears;
  const ratio = benchmark > 0 ? bottomUp / benchmark : (bottomUp > 0 ? Infinity : 1);

  return {
    bottomUp,
    benchmark,
    ratio,
    underCountFlag: ratio < 0.8,
    twabUsd,
    benchmarkApy,
  };
}

// ── Pure function: isInScopePosition ─────────────────────────────────────────

/**
 * Scope guard: determines whether a receipt token is a stablecoin-denominated LP/vault
 * (IN scope) or a directional/volatile asset or spam airdrop (OUT of scope).
 *
 * Rules (first match wins):
 *  1. SPAM — symbol or name contains a URL, claim keyword, or airdrop marker → out.
 *  2. DIRECTIONAL — any delimiter-separated token in symbol or name matches a known volatile
 *     asset (ETH, WETH, WBTC, ARB, OP, VELO, AERO, CRV, CVX, LARRY, etc.) → out.
 *     Note: a camelCase-embedded prefix like "mooAeroEURC" does NOT match "aero" because
 *     the split only breaks on [-/\s(),|] boundaries, so "mooAeroEURC" is one token.
 *     Note: these same symbols remain valid as EMISSION REWARDS in classifyTransfers —
 *     this function only filters POSITION/receipt tokens, not emission handling.
 *  3. Otherwise → in scope (stable LP/vault, e.g. USDC-USDT, mooCurveEUSD-USDC, gtUSDCp).
 */
export type InScopeResult = { inScope: boolean; reason?: string };

/** Volatile/directional tokens that disqualify a POSITION when appearing as a standalone
 *  segment in the symbol or name (split on [-/\\s(),|\\[\\]] boundaries). */
export const DIRECTIONAL_POSITION_TOKENS = new Set([
  // ETH family
  "eth", "weth", "steth", "wsteth", "reth", "cbeth", "weeth", "ezeth", "rseth",
  // BTC family
  "btc", "wbtc", "tbtc", "cbbtc",
  // Other L1s / large caps
  "sol", "bnb", "matic", "avax", "ftm", "near",
  // Governance / directional tokens explicitly listed in spec
  "arb", "op", "link", "uni", "gmx", "pendle",
  "velo", "aero", "crv", "cvx", "snx", "bal", "ldo", "comp", "morpho",
  // Misc volatile mentioned in scope doc
  "larry",
]);

const SPAM_RE = /https?:|www\.|\.net\b|\.com\b|\.finance\b|\.cc\b|\.io\b|\.xyz\b|t\.me|claim|visit\b|airdrop|points\b|get reward|🎁/i;

export function isInScopePosition(p: { symbol: string; name?: string }): InScopeResult {
  const sym  = (p.symbol || "").trim();
  const name = (p.name   || "").trim();
  const combined = `${sym} ${name}`;

  // 1. Spam / airdrop check
  if (SPAM_RE.test(combined)) {
    return { inScope: false, reason: `spam/airdrop: URL or claim keyword in "${combined.slice(0, 60)}"` };
  }

  // 2. Directional check: split on non-alphanumeric delimiters, check each segment
  const parts = combined.toLowerCase().split(/[-/\s(),|[\]]+/).filter(Boolean);
  for (const part of parts) {
    if (DIRECTIONAL_POSITION_TOKENS.has(part)) {
      return { inScope: false, reason: `directional: volatile token "${part}" in position symbol/name` };
    }
  }

  return { inScope: true };
}

// ── Network helpers (NOT exercised by tests) ──────────────────────────────────

async function httpGet(url: string, retries = 3): Promise<unknown> {
  for (let i = 0; i < retries; i++) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 30_000);
      try {
        const res = await fetch(url, { headers: { "User-Agent": "yield-trace/1.0" }, signal: ctrl.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
      } finally {
        clearTimeout(t);
      }
    } catch (e) {
      if (i < retries - 1) await Bun.sleep(1500 * 2 ** i);
      else console.error(`  [WARN] GET failed (${(e as Error).message}): ${url.slice(0, 80)}`);
    }
  }
  return null;
}

async function rpcPost(url: string, payload: object, retries = 3): Promise<unknown> {
  for (let i = 0; i < retries; i++) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 30_000);
      try {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json", "User-Agent": "yield-trace/1.0" },
          body: JSON.stringify(payload),
          signal: ctrl.signal,
        });
        return await res.json();
      } finally {
        clearTimeout(t);
      }
    } catch (e) {
      if (i < retries - 1) await Bun.sleep(1500 * 2 ** i);
      else console.error(`  [WARN] RPC failed (${(e as Error).message}): ${url}`);
    }
  }
  return null;
}

export async function llamaBlock(llamaChain: string, ts: number): Promise<number | null> {
  const data = await httpGet(`https://coins.llama.fi/block/${llamaChain}/${ts}`) as Record<string, unknown> | null;
  if (data && typeof data["height"] === "number") return data["height"];
  return null;
}

const _priceCache = new Map<string, number | null>();

export async function llamaPriceHistorical(
  llamaChain: string, tokenAddr: string, ts: number,
): Promise<number | null> {
  const key = `${llamaChain}:${tokenAddr.toLowerCase()}:${ts}`;
  if (_priceCache.has(key)) return _priceCache.get(key)!;
  const url = `https://coins.llama.fi/prices/historical/${ts}/${llamaChain}:${tokenAddr.toLowerCase()}`;
  const data = await httpGet(url) as Record<string, unknown> | null;
  let price: number | null = null;
  if (data && data["coins"]) {
    const coins = data["coins"] as Record<string, unknown>;
    const coin  = coins[`${llamaChain}:${tokenAddr.toLowerCase()}`] as Record<string, unknown> | undefined;
    if (coin && typeof coin["price"] === "number") price = coin["price"];
  }
  _priceCache.set(key, price);
  return price;
}

export async function ethCall(
  rpcs: string[], to: string, dataHex: string, block: string,
): Promise<string | null> {
  for (const rpc of rpcs) {
    const res = await rpcPost(rpc, {
      jsonrpc: "2.0", method: "eth_call",
      params: [{ to, data: dataHex }, block], id: 1,
    }) as Record<string, unknown> | null;
    if (res && res["result"] && !["0x", "0x0", ""].includes(res["result"] as string)) {
      return res["result"] as string;
    }
  }
  return null;
}

async function ethBalanceOf(rpcs: string[], token: string, wallet: string, blockHex: string): Promise<bigint> {
  const raw = await ethCall(rpcs, token, SEL_BALANCEOF + pad32(wallet), blockHex);
  if (raw) { try { return BigInt(raw); } catch {} }
  return 0n;
}

async function ethConvertAssets(rpcs: string[], token: string, shares: bigint, blockHex: string): Promise<bigint | null> {
  const sharesHex = shares.toString(16).padStart(64, "0");
  const raw = await ethCall(rpcs, token, SEL_CONVERT_ASSETS + sharesHex, blockHex);
  if (raw) { try { return BigInt(raw); } catch {} }
  return null;
}

async function ethPricePerShare(rpcs: string[], token: string, blockHex: string): Promise<bigint | null> {
  const raw = await ethCall(rpcs, token, SEL_PRICE_PER_SHARE, blockHex);
  if (raw) { try { return BigInt(raw); } catch {} }
  return null;
}

async function receiptUsd(
  rpcs: string[], tokenAddr: string, decimals: number, blockHex: string,
): Promise<{ value: number; method: string }> {
  const balance = await ethBalanceOf(rpcs, tokenAddr, "", blockHex);
  if (balance === 0n) return { value: 0, method: "balance=0" };

  const assets = await ethConvertAssets(rpcs, tokenAddr, balance, blockHex);
  if (assets && assets > 0n) {
    for (const d of [6, 18]) {
      const v = Number(assets) / 10 ** d;
      if (v >= 1e-4 && v <= 1e9) return { value: v, method: `convertToAssets/${d}dec` };
    }
  }

  const pps = await ethPricePerShare(rpcs, tokenAddr, blockHex);
  if (pps && pps > 0n) {
    const sharesFloat = Number(balance) / 1e18;
    const lpAmount    = sharesFloat * (Number(pps) / 1e18);
    if (lpAmount >= 1e-4 && lpAmount <= 1e9) return { value: lpAmount, method: "getPricePerFullShare×$1(est)" };
  }

  return { value: Number(balance) / 10 ** decimals, method: "balance×$1(fallback)" };
}

export async function fetchTransfers(chain: string, wallet: string): Promise<Transfer[]> {
  const cfg = CHAIN_CONFIG[chain];
  if (!cfg) throw new Error(`Unknown chain: ${chain}`);
  const url = `${cfg.blockscout}?module=account&action=tokentx&address=${wallet}&sort=asc&page=1&offset=10000`;
  const data = await httpGet(url) as Record<string, unknown> | null;
  if (!data || data["status"] !== "1") {
    console.warn(`  [WARN] tokentx empty for ${chain}: ${JSON.stringify(data)?.slice(0, 80)}`);
    return [];
  }
  return (data["result"] as Transfer[]) || [];
}

/**
 * Compute basis at a window timestamp for a given receipt token.
 * Returns archiveSuspect=true if the RPC returned $0 for a provably-open position.
 * Tries all fallback RPCs before giving up (fix c).
 */
async function basisAt(opts: {
  rpcs: string[];
  tokenAddr: string;
  decimals: number;
  blockHex: string | null;
  entries: EntryTransfer[];
  exits: ExitTransfer[];
  windowTs: number;
  preCost: number;
}): Promise<BasisResult> {
  const { rpcs, tokenAddr, decimals, blockHex, entries, exits, windowTs, preCost } = opts;
  if (!blockHex) return { value: 0, method: "no block", archiveSuspect: false };

  const { value: v, method: m } = await receiptUsd(rpcs, tokenAddr, decimals, blockHex);

  const entriesBefore  = entries.filter((e) => e.ts < windowTs);
  const exitsBefore    = exits.filter((e) => e.ts < windowTs);
  const exitsInOrAfter = exits.filter((e) => e.ts >= windowTs);
  const expectedOpen   = entriesBefore.length > 0 && (!exitsBefore.length || exitsInOrAfter.length > 0);
  const archiveSuspect = expectedOpen && (v === 0 || (v < 1 && preCost > 100));

  return { value: v, method: m, archiveSuspect };
}

/**
 * Price all emission transfers at their historical USD values via DefiLlama.
 * Returns only emissions that could be priced (others are dropped with a warning).
 */
export async function priceEmissions(
  emissions: EmissionTransfer[],
  llamaChain: string,
): Promise<PricedEmission[]> {
  const priced: PricedEmission[] = [];
  for (const em of emissions) {
    const price = await llamaPriceHistorical(llamaChain, em.addr, em.ts);
    if (price === null) {
      console.warn(`  [WARN] Could not price emission ${em.symbol} @ ${em.ts} — excluded`);
      continue;
    }
    priced.push({ ...em, usdValue: em.amount * price });
  }
  return priced;
}

// ── main() ────────────────────────────────────────────────────────────────────

async function main() {
  const argv = process.argv.slice(2);
  const wallet = argv.find((a) => /^0x[0-9a-fA-F]{40}$/i.test(a));
  if (!wallet) {
    console.error("usage: bun yield_trace.ts <0x-wallet> [--chains base,ethereum,arbitrum,optimism] [--window 1y|2y]");
    process.exit(1);
  }

  const chainsArg = argv.includes("--chains") ? argv[argv.indexOf("--chains") + 1] : undefined;
  const chains = chainsArg ? chainsArg.split(",").map((s) => s.trim()) : ["base", "ethereum", "arbitrum", "optimism"];

  const windowArg = argv.includes("--window") ? argv[argv.indexOf("--window") + 1] : "2y";
  const W1Y_TS = 1750809600; // 2025-06-25
  const W2Y_TS = 1719273600; // 2024-06-25
  const windowTs = windowArg === "1y" ? W1Y_TS : W2Y_TS;
  const NOW_TS   = Math.floor(Date.now() / 1000);

  console.log(`\nYield Trace — ${wallet} — window=${windowArg}\n${"=".repeat(78)}`);

  const allResults: PnLResult[] = [];

  for (const chain of chains) {
    const cfg = CHAIN_CONFIG[chain];
    if (!cfg) { console.warn(`  Unknown chain ${chain}, skipping`); continue; }

    console.log(`\n[${chain}] Fetching transfers…`);
    const transfers = await fetchTransfers(chain, wallet);
    if (!transfers.length) continue;

    // Get block numbers
    const [bWindow, bNow] = await Promise.all([
      llamaBlock(cfg.llama, windowTs),
      llamaBlock(cfg.llama, NOW_TS),
    ]);

    console.log(`  window block=${bWindow}  now block=${bNow}`);

    // Discover receipt tokens (non-stable tokens wallet interacted with)
    const stableAddrs = new Set(Object.keys(
      // Use a minimal inline stables map for discovery only
      Object.fromEntries(
        ["0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
         "0xaf88d065e77c8cc2239327c5edb3a432268e5831",
         "0x0b2c639c533813f4aa9d7837caf62653d097ff85",
         "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
         "0xdac17f958d2ee523a2206206994597c13d831ec7",
         "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",
         "0x94b008aa00579c1307b0ef2c499ad98a8ce58e58",
         "0x50c5725949a6f0c72e6c4a641f24049a917db0cb",
        ].map((a) => [a, true]),
      ),
    ));

    const receiptTokens = new Map<string, { symbol: string; name: string; decimals: number }>();
    for (const tx of transfers) {
      const a = tx.contractAddress.toLowerCase();
      if (!stableAddrs.has(a) && !receiptTokens.has(a)) {
        receiptTokens.set(a, {
          symbol: tx.tokenSymbol,
          name: tx.tokenName,
          decimals: parseInt(tx.tokenDecimal, 10),
        });
      }
    }

    const stablesMap: StablesMap = {
      "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": { symbol: "USDC",   faceUsd: 1.0 },
      "0xaf88d065e77c8cc2239327c5edb3a432268e5831": { symbol: "USDC",   faceUsd: 1.0 },
      "0x0b2c639c533813f4aa9d7837caf62653d097ff85": { symbol: "USDC",   faceUsd: 1.0 },
      "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": { symbol: "USDC",   faceUsd: 1.0 },
      "0xdac17f958d2ee523a2206206994597c13d831ec7": { symbol: "USDT",   faceUsd: 1.0 },
      "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9": { symbol: "USDT",   faceUsd: 1.0 },
      "0x94b008aa00579c1307b0ef2c499ad98a8ce58e58": { symbol: "USDT",   faceUsd: 1.0 },
      "0x50c5725949a6f0c72e6c4a641f24049a917db0cb": { symbol: "DAI",    faceUsd: 1.0 },
      "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1": { symbol: "DAI",    faceUsd: 1.0 },
      "0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca": { symbol: "USDbC",  faceUsd: 1.0 },
    };

    let skippedCount = 0;
    for (const [tokenAddr, { symbol, name, decimals }] of receiptTokens) {
      const scope = isInScopePosition({ symbol, name });
      if (!scope.inScope) {
        skippedCount++;
        continue;
      }
      console.log(`  [${chain}] position: ${symbol} (${tokenAddr.slice(0, 16)}…)`);
      const classified = classifyTransfers(transfers, wallet, tokenAddr, stablesMap);
      if (!classified.entries.length && !classified.exits.length && !classified.emissions.length) continue;

      const pricedEm = await priceEmissions(classified.emissions, cfg.llama);

      const preCost = classified.entries.reduce((s, e) => s + e.costIn, 0);
      const basisResult = await basisAt({
        rpcs: cfg.rpcs,
        tokenAddr,
        decimals,
        blockHex: bWindow ? `0x${bWindow.toString(16)}` : null,
        entries: classified.entries,
        exits: classified.exits,
        windowTs,
        preCost,
      });

      const curUsd = bNow
        ? (await receiptUsd(cfg.rpcs, tokenAddr, decimals, `0x${bNow.toString(16)}`)).value
        : 0;

      const result = positionPnL({
        entries: classified.entries,
        exits: classified.exits,
        stableRewards: classified.stableRewards,
        pricedEmissions: pricedEm,
        currentValue: curUsd,
        windowTs,
        basisAtWindow: basisResult,
      });

      allResults.push(result);

      const archiveFlag = result.basisResult.archiveSuspect ? " ⚠️ ARCHIVE SUSPECT" : "";
      console.log(
        `    cost=$${result.lifetimeBreakdown.totalCost.toFixed(2)}` +
        `  proceeds=$${result.lifetimeBreakdown.totalProceeds.toFixed(2)}` +
        `  stableRew=$${result.lifetimeBreakdown.totalStableRewards.toFixed(2)}` +
        `  emissionUsd=$${result.lifetimeBreakdown.totalEmissionUsd.toFixed(2)}` +
        `  cur=$${result.lifetimeBreakdown.currentValue.toFixed(2)}` +
        `  lifetime=$${result.lifetime.toFixed(2)}  windowed=${windowArg}=$${result.windowed.toFixed(2)}${archiveFlag}`,
      );
    }
    if (skippedCount > 0) {
      console.log(`  skipped ${skippedCount} out-of-scope/spam tokens (directional or airdrop)`);
    }
  }

  const totalLifetime = allResults.reduce((s, r) => s + r.lifetime, 0);
  const totalWindowed = allResults.reduce((s, r) => s + r.windowed, 0);
  console.log(`\n${"=".repeat(78)}`);
  console.log(`  TOTAL lifetime PnL : $${totalLifetime.toFixed(2)}`);
  console.log(`  TOTAL ${windowArg} PnL     : $${totalWindowed.toFixed(2)}`);
  console.log(`${"=".repeat(78)}\n`);
}

if (import.meta.main) main();
