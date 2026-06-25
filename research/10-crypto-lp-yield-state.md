# 10 — State of Crypto LP / Stablecoin Yield (live snapshot)

*Where to earn yield on stablecoins right now **without shady collateral**. Educational
analysis, not advice. All numbers pulled live from the DefiLlama free yields API
(`https://yields.llama.fi/pools`) and the Morpho GraphQL API (`https://api.morpho.org/graphql`)
on **2026-05-30**. Updated **2026-06-24** with Fluid vs Maple deep research. Re-run the
queries at the bottom to refresh — DeFi rates move hourly.*

---

## 2026-06-24 Update — Fluid vs Maple Deep Research

*Full deep-dive comparison run June 24, 2026. Sources: 30+ URLs, 3 parallel research agents.*

### Verified APYs (30-day cross-check applied)

| Venue | Today | 30d Mean | Sigma | Verdict |
|---|---|---|---|---|
| Maple syrupUSDC (ETH) | 5.00% | 4.75% | 0.09 | ✅ Stable — confirmed |
| Maple syrupUSDT (ETH) | 4.00% | ~4.0% | ~0.09 | ✅ Stable — confirmed |
| Fluid USDC lending (ETH) | 7.60% | 7.05% | 0.17 | ✅ Stable ~7% |
| Fluid USDT lending (ETH) | 7.34% ⚠️ | **4.73%** | 0.19 | ⚠️ SPIKE — real avg ~4.7% |
| Aave v3 USDC Umbrella (ETH) | 6.91% | 7.32% | ~0.15 | ✅ Stable ~7%, safety-module stake |
| Morpho Reservoir USDC (ETH) | 6.08% | 6.21% | 0.07 | ✅ Most stable of all |
| Aerodrome CL1 USDC-USDT (Base) | 20.6% | 24.5% | 0.55 | ⚠️ Real but wildly volatile; active mgmt |

> ⚠️ **Rule (from defi-portfolio-manager skill):** Always cross-check today's APY against 30d
> mean before sizing. A spike today (Fluid USDT: 7.34% vs 4.73% mean) = utilization event,
> not a new normal. DeFiLlama `/chart/{poolId}` gives 30d history.

---

### Fluid Protocol — Key Facts

| Item | Detail |
|---|---|
| **What it is** | Permissionless DeFi lending protocol by Instadapp |
| **Founded** | Instadapp 2018 (middleware); Fluid protocol launched Jan 2024 |
| **Legal entity** | None disclosed — operates as DAO (`instadapp-gov.eth`) |
| **Jurisdiction** | Unknown; no corporate registration found |
| **TVL (Jun 2026)** | $698M supply-side; peak ~$1.47B (Oct–Nov 2025) |
| **Chains** | Ethereum ($487M), Arbitrum ($105M), Plasma ($87M), Base ($18M) |
| **Backers** | Coinbase Ventures, Pantera Capital, Binance (medium confidence) |
| **FLUID token** | ~$0.93; 100M max supply; −96% from ATH $24.40; ~$72M market cap |
| **US access** | ✅ Open to everyone, no KYC |
| **Known exploits** | None found |
| **Audits** | Formal audits pre-launch (Nov–Dec 2023); $500k live bug bounty deployed before mainnet |
| **Withdrawals** | Instant (ERC-4626 redeem anytime) |

**How it works:** Shared Liquidity Layer aggregates all deposits → borrowers post ETH/wBTC/wstETH
collateral on-chain → borrow against it → you earn their interest rate. Key innovations: Automated
debt ceilings (limit exploit blast radius), slot-based liquidations (like swaps, ~150k gas vs
300k–1M), Smart Debt (borrowers' debt earns DEX swap fees), up to 95% LTV on ETH.

**USDT yield breakdown:**
- `apyBase` = borrower interest (variable, utilization-curve driven)
- `apyReward` = 1.03% INST/FLUID token emissions (must claim + sell to realize)
- 30d realistic expectation: **~4.5–5.5%** (today's spike reverts)

---

### Maple Finance — Updated Facts (Jun 2026)

| Item | Detail |
|---|---|
| **AUM** | $3.99B; $22.46B total originated since founding |
| **Operating company** | Maple Labs Pty Ltd — **Melbourne, Australia** |
| **Issuer (syrupUSDC/USDT)** | Maple International Operations SPC — **Cayman Islands** (segregated portfolios) |
| **Interface operator** | Syrup Ltd; governing law **British Virgin Islands** |
| **US access** | 🚫 Blocked (also Australia, Russia, Belarus, etc.) |
| **Backing** | BlockTower, Framework, Polychain, Circle, GSR, Spartan Group |
| **Early investor** | Alameda Research ⚠️ (seed 2020, collapsed Nov 2022) |
| **Audits** | 9 rounds: Trail of Bits, Spearbit, Three Sigma, 0xMacro, Sherlock, Dedaub, Sigma Prime |
| **Known exploits** | None (smart contract). Credit default history: see below |
| **Withdrawals** | FIFO queue, typically <24h; worst case 30 days. OR: sell syrupUSDC on Uniswap instantly (slippage applies) |

**2022 Orthogonal Trading default (the critical history):**
- Dec 2022: Orthogonal Trading (pool delegate) defaulted on ~$36M in Maple V1 loans
- Root cause: Maple V1 allowed undercollateralized loans; Orthogonal misrepresented FTX exposure
- **No insurance fund.** Losses borne entirely by LPs in those pools, pro-rata
- LPs who withdrew during impairment locked in permanent losses; no future recovery
- **Response:** V2 launched Dec 11, 2022 — requires overcollateralization on ALL loans
- syrupUSDC/syrupUSDT use V2 model with Cayman SPC legal isolation

**Withdrawal mechanics (verified from docs):**
- Official path: FIFO withdrawal queue — "average <24h" on US banking days; as fast as ~3h intraday
- Emergency/instant path: swap syrupUSDC on Uniswap — immediate, but syrupUSDC ≠ 1:1 USDC (NAV-based, slippage applies)
- Worst case: up to 30 days if pool is heavily deployed and withdrawal demand is high

---

### Fluid vs Maple — Head-to-Head

| Dimension | Maple syrupUSDC | Fluid USDT |
|---|---|---|
| Expected APY | ~4.75–5.0% (stable) | ~4.5–5.5% (variable) |
| APY source | Institutional credit + basis trades | On-chain borrower interest + INST rewards |
| APY stability | ✅ Very stable (sigma 0.09) | ⚠️ More volatile (sigma 0.19) |
| Withdrawal | Queue <24h typical; Uniswap instant exit | ✅ Instant (ERC-4626) |
| US access | 🚫 Blocked | ✅ Open |
| KYC | Self-cert (non-US) | None |
| Legal structure | Cayman SPC, BVI law, Australian company | DAO, no disclosed entity |
| Legal recourse if loss | Some (Cayman court, MLA contracts) | Effectively none |
| Default history | ❗ $36M (2022, V1 undercollateralized) | None (2.5 years old) |
| Smart contract exploits | None | None |
| Audits | 9 rounds, 6 named firms | Pre-launch audits; fewer details available |
| Token emissions in yield | None (clean yield) | ⚠️ 1.03% INST must be claimed + sold |
| CEX exposure | ⚠️ Basis trades on CEXes | None — fully on-chain |
| Borrower type | KYC'd institutional firms (MLAs) | Permissionless on-chain wallets |

**Choose Maple if:** non-US, want stable yield, comfortable with queue withdrawal, prefer regulated entity structure.

**Choose Fluid if:** US-based, want instant withdrawal, comfortable with variable rate, prefer fully on-chain.

---

## TL;DR

- **The honest base rate for stablecoins is ~3–5%.** It tracks US T-bills (the risk-free rate),
  because the safest large pools are now backed by tokenized treasuries or overcollateralized
  blue-chip lending. Anything materially above ~6% sustained is paying you for *extra risk*
  (curator risk, exotic collateral, depeg risk) or is a temporary spike / token emission.
- **"No shady collateral" has a precise meaning here:** the pool lends only against
  cash-equivalents (T-bills), BTC, or ETH — not long-tail tokens, leveraged PT positions, or
  reflexive synthetic dollars.
- **Best risk-adjusted picks right now:** Maple `Syrup USDT/USDC` (~4.1–4.7%, overcollateralized
  institutional lending) and Morpho `steakUSDC` (~3.8%, lends only vs WBTC/cbBTC/ETH).

## The landscape — largest stablecoin pools, all chains (TVL > $200M)

| Protocol | Chain | TVL | APY | What backs it | Collateral grade |
|----------|-------|-----|-----|---------------|------------------|
| Sky `sUSDS` | Ethereum | $6.2B | 3.6% | Maker/Sky reserves | Cash-equiv ✅ |
| Maple `Syrup USDC` | Ethereum | $3.3B | 4.67% | Overcollateralized institutional loans | Blue-chip ✅ |
| Circle `USYC` | BSC | $2.8B | 3.0% | Tokenized T-bills (Hashnote) | Cash-equiv ✅ |
| Ethena `sUSDe` | Ethereum | $1.8B | 3.8% | Delta-neutral perp basis | ⚠️ Synthetic |
| Spark Savings `USDT` | Ethereum | $1.3B | 2.5% | Sky reserves | Cash-equiv ✅ |
| Ondo `USDY` | Ethereum | $1.1B | 3.55% | Tokenized T-bills + bank deposits | Cash-equiv ✅ |
| Maple `Syrup USDT` | Ethereum | $986M | 4.13% | Overcollateralized institutional loans | Blue-chip ✅ |
| BlackRock `BUIDL` | Ethereum | $838M | 3.55% | Tokenized T-bills (BlackRock/Securitize) | Cash-equiv ✅ |
| Superstate `USTB` | Ethereum | $759M | 3.3% | Tokenized T-bills | Cash-equiv ✅ |
| Aave v3 `USDT` | Ethereum | $555M | 2.37% | Overcollateralized crypto lending | Blue-chip ✅ |

**Read:** the entire top of the market has converged on **T-bill yield (~3.5%)** plus a small
spread for overcollateralized lending (Maple/Aave at 4–4.7%). That *is* the no-shady-collateral
yield right now. There is no safe 10%.

## Protocol-by-protocol

### Morpho — the one to understand
Morpho is **not one pool**. It's a permissionless vault layer: independent *curators*
(Steakhouse, Gauntlet, MEV Capital…) each run a vault, pick the collateral, the loan-to-value
(LLTV), and the oracle. So a "Morpho APY" is meaningless without naming the **vault and its
collateral**. The headline 8–13%+ numbers you see are almost always: (a) token emissions, (b) a
transient utilization spike, (c) exotic collateral risk premium, or (d) a near-zero-TVL vault
where one borrow distorts the instantaneous rate.

Verified collateral books (Morpho API, 2026-05-30):

| Vault | TVL | APY | Collateral (actual) | Verdict |
|-------|-----|-----|---------------------|---------|
| **`steakUSDC`** | $109M | **3.73%** | 65% WBTC, 20% cbBTC, 10% ETH/stETH | ✅ **Blue-chip only** |
| `steakUSDT` | $92M | 13.71%* | 73% wstETH, 23% BTC, 3% gold | ✅ collateral, ⚠️ *yield is a utilization spike, 30d mean ~3%* |
| `steakUSDTBethena` | $120M | 1.5% | 100% sUSDe (Ethena) | ⚠️ Synthetic-dollar collateral — avoid for low-risk |

→ **`steakUSDC` pool:** https://defillama.com/yields/pool/b55f43a8-f444-4cd8-a3a4-0a4e786ba566
→ **`steakUSDC` vault (deposit here):** https://app.morpho.org/ethereum/vault/0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB
*(\* `steakUSDT` netAPY swings — it showed 6.2% base on DefiLlama, 13.7% live on Morpho, 30-day
mean ~3%, trend "Down". Same good collateral as steakUSDC but a rate you can't count on.)*

### Maple Finance — best blue-chip lending spread
`Syrup USDT/USDC`. Overcollateralized lending to vetted institutional borrowers. Single-asset
(no IL), `apyReward: 0` (real yield, not emissions), ~$1B (USDT) / $3.3B (USDC) TVL. **~4.1–4.7%.**
The protocol you already trust; it earns its spread above T-bills by taking *overcollateralized*
counterparty risk, not by holding junk. Withdrawals route through a cycle/notice window (not
always instant) — check the current cooldown before depositing.

### Beefy — autocompounder, *inherits* its collateral risk
Beefy doesn't originate yield; it auto-compounds someone else's LP. Its risk = the underlying
pool's risk plus a smart-contract layer. Current Ethereum stablecoin Beefy vaults are small
($3–9M) and mostly Curve stable-LP wrappers (e.g. `RLUSD-USDC` ~7%, `USDS-stUSDS` ~4.5%). Fine as
an autocompounding convenience on an L2 with cheap gas, **not** where you want size on mainnet.

### Aave v3 — the liquidity benchmark
`USDT` 2.37% base (6.5% on the incentivized market with rewards). The most battle-tested,
most liquid, instant-withdraw option. Lowest yield, lowest risk. The thing everything else is
measured against.

### Curve / Convex — yield is mostly emissions now
Large stable LPs (`USDC-RLUSD` 7.6%, `PYUSD-USDC` 5.3%) but the APY is **mostly `apyReward`**
(CRV/CVX token emissions), not trading fees. When emissions taper the rate collapses, and you
take pair/depeg exposure (RLUSD, PYUSD are newer than USDC). Not "no-shady" for size.

### RWA / tokenized T-bills — the genuinely safest tier
BlackRock `BUIDL`, Superstate `USTB`, Ondo `USDY/OUSG`, Circle `USYC`. These hold **actual US
Treasuries**. ~3.3–3.6%. The collateral literally cannot be shady — it's T-bills. Catch: most
require KYC / accredited-investor onboarding and have minimums, so they're not click-to-deposit
for a retail wallet.

## The shady-collateral checklist (how to screen any pool)

Reject a pool if any are true:
1. **APY is mostly `apyReward`** → token emissions, not real yield; collapses when they end.
2. **TVL < ~$20M** → instantaneous APY is noise; one borrow distorts it.
3. **Collateral is long-tail / PT / looped / a reflexive synthetic** → you eat the bad debt.
4. **Sustained APY >> ~6% on a "stablecoin"** → you're being paid for risk you haven't priced.
5. **`outlook: Down` + APY far above 30-day mean** → you're buying a transient spike.

Keep it if: single-asset (`ilRisk: no`), `apyReward ≈ 0`, TVL > $100M, collateral ∈
{T-bills, BTC, ETH}, reputable curator/protocol.

## How to refresh this (free, no API key, no wallet)

```bash
# Top no-shady stablecoin pools on Ethereum, real yield only:
curl -s https://yields.llama.fi/pools | jq -r '
  [.data[] | select(.chain=="Ethereum" and .stablecoin==true)
   | select(.tvlUsd>100e6) | select((.apyReward//0) < 0.5) | select(.apy<6)]
  | sort_by(-.apy) | .[]
  | "\(.project) [\(.symbol)] $\(.tvlUsd/1e6|floor)M  \(.apy)%"'

# Verify a Morpho vault's actual collateral before depositing:
curl -s https://api.morpho.org/graphql -X POST -H 'Content-Type: application/json' \
  -d '{"query":"{ vaults(first:300,where:{chainId_in:[1]}){items{symbol state{netApy allocation{supplyAssetsUsd market{collateralAsset{symbol} lltv}}}}}}"}'
```

Or just ask the installed **`risk-assessment`** skill ("is Maple safe?") — it walks hack history
→ oracle → treasury → yield sustainability before you commit.

## Sources
- DefiLlama Yields API — https://yields.llama.fi/pools (free, public)
- Morpho GraphQL API — https://api.morpho.org/graphql
- DefiLlama yields UI — https://defillama.com/yields
- Morpho app (collateral per vault) — https://app.morpho.org
