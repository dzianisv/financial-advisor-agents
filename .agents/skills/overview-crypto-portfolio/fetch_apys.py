#!/usr/bin/env python3
"""
Fetch live APYs for DeFi protocols in the crypto portfolio and recommend upgrades.
No API key required. Sources:
  - Morpho Blue: blue-api.morpho.org/graphql      (Base + ETH vaults)
  - DeFiLlama:  yields.llama.fi/pools             (Maple Syrup, LIDO, ExtraFi XLend, Avantis + pool discovery)
  - Ethena:     ethena.fi/api/yields/...           (sUSDe staking yield)
  - Hyperliquid: api.hyperliquid.xyz/info          (HLP vault APR via userVaultEquities)

Usage:
  python3 fetch_apys.py              # APYs + upgrade recommendations
  python3 fetch_apys.py --apys-only  # APYs only, skip recommendations
"""

import json
import sys
import urllib.request

UPGRADE_THRESHOLD_PCT = 1.5  # recommend upgrade if better pool is >1.5% higher APY
MIN_TVL_M = 5                # only recommend pools with >$5M TVL

# Trusted protocols — audited, battle-tested, won't rug
TRUSTED_PROTOCOLS = {
    "morpho-blue", "morpho", "aave-v3", "aave", "maple",
    "fluid", "fluid-lite", "fluid-lending",
    "compound-v3", "spark", "avantis",
    "euler-v2", "moonwell", "seamless-protocol",
    "extra-finance-xlend", "steakhouse",
}

def fetch(url, method="GET", data=None, headers=None):
    req = urllib.request.Request(url, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if data:
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def morpho_apys():
    """Query Morpho Blue GraphQL for vault APYs (Base + ETH mainnet)."""
    query = {
        "query": "{ vaults(first:500, where:{chainId_in:[1,8453]}) { items { name chain { id } address state { netApy } } } }"
    }
    result = fetch(
        "https://blue-api.morpho.org/graphql",
        method="POST",
        data=query,
        headers={"Content-Type": "application/json"}
    )
    if "error" in result or "data" not in result:
        return {"error": result.get("error", "unknown")}

    # ExtraFi XLend is NOT a MetaMorpho vault — sourced from DeFiLlama instead.
    name_map = {
        "seamless usdc vault": "morpho_seamless_usdc_base",
        "universal usdc": "morpho_universal_usdc_base",
        "morpho eusd": "morpho_eusd_base",
        "gauntlet eusd core": "morpho_eusd_eth",
    }
    out = {}
    for v in result["data"]["vaults"]["items"]:
        name_lower = v["name"].lower().strip()
        state = v.get("state") or {}
        raw_apy = state.get("netApy")  # None = missing data; 0.0 = genuinely idle
        for pattern, key in name_map.items():
            if pattern in name_lower:
                out[key] = None if raw_apy is None else round(raw_apy * 100, 2)
                break
    return out

def defi_llama_apys():
    """Single DeFiLlama fetch for portfolio APYs + pool discovery data."""
    result = fetch("https://yields.llama.fi/pools")
    if "error" in result or "data" not in result:
        return {"error": result.get("error", "fetch failed")}, []

    portfolio_apys = {}
    all_pools = []

    for p in result["data"]:
        proj = (p.get("project") or "").lower()
        sym = (p.get("symbol") or "").lower()
        chain = (p.get("chain") or "").lower()
        meta = (p.get("poolMeta") or "").lower()
        apy = round(p.get("apy") or 0, 2)
        tvl = p.get("tvlUsd") or 0

        # --- Portfolio positions ---
        if "maple" in proj and "usdc" in sym and "syrup" in meta:
            portfolio_apys["maple_syrup_usdc"] = apy
        elif "maple" in proj and "usdt" in sym and "syrup" in meta:
            portfolio_apys["maple_syrup_usdt"] = apy
        elif "lido" in proj and "steth" in sym and chain == "ethereum":
            portfolio_apys["lido_steth"] = apy
        elif proj == "extra-finance-xlend" and "usdc" in sym and chain == "base":
            portfolio_apys["extrafi_xlend_usdc_base"] = apy
        elif "avantis" in proj and "usdc" in sym and chain == "base":
            portfolio_apys["avantis_junior_usdc"] = apy

        # --- Pool discovery candidates (stable, single-asset, trusted, Base or ETH) ---
        is_trusted = any(t in proj for t in TRUSTED_PROTOCOLS)
        if (chain in ["base", "ethereum"]
                and p.get("stablecoin")
                and p.get("ilRisk") == "no"
                and p.get("exposure") == "single"
                and apy > 0
                and tvl >= MIN_TVL_M * 1e6
                and is_trusted):
            all_pools.append({
                "chain": p["chain"],
                "project": p["project"],
                "symbol": p["symbol"],
                "apy": apy,
                "tvl_m": round(tvl / 1e6, 1),
                "meta": (p.get("poolMeta") or ""),
                "pool_id": p.get("pool", ""),
                "url": f"https://defillama.com/yields/pool/{p.get('pool', '')}",
            })

    return portfolio_apys, all_pools

def ethena_apy():
    """Fetch Ethena sUSDe staking yield."""
    result = fetch("https://ethena.fi/api/yields/protocol-and-staking-yield")
    if "error" in result or "stakingYield" not in result:
        return {"error": result.get("error", "fetch failed")}
    return {"ethena_susde": round(result["stakingYield"]["value"], 2)}

def hyperliquid_vault_apr(user_addr, vault_addr=None):
    """Fetch Hyperliquid HLP vault APR for a given user address."""
    equities = fetch(
        "https://api.hyperliquid.xyz/info",
        method="POST",
        data={"type": "userVaultEquities", "user": user_addr},
        headers={"Content-Type": "application/json"}
    )
    if "error" in equities or not isinstance(equities, list) or not equities:
        return {"error": f"no vault equities for {user_addr}"}

    target = vault_addr or equities[0].get("vaultAddress")
    if not target:
        return {"error": "no vaultAddress in equities"}

    details = fetch(
        "https://api.hyperliquid.xyz/info",
        method="POST",
        data={"type": "vaultDetails", "vaultAddress": target},
        headers={"Content-Type": "application/json"}
    )
    if "error" in details or "apr" not in details:
        return {"error": f"no APR for vault {target}"}

    apr_pct = round((details["apr"] or 0) * 100, 2)
    return {"hyperliquid_hlp_vault": apr_pct, "_vault_name": details.get("name", target)}

def find_better_pool(current_apy, asset_sym, chain, all_pools):
    """
    Find the best DeFiLlama pool for an asset that beats current_apy by UPGRADE_THRESHOLD_PCT.
    Prefers same chain (cheaper gas). Returns None if no upgrade found.
    """
    if current_apy is None:
        current_apy = 0

    sym_lower = asset_sym.lower()
    chain_lower = chain.lower()

    # Score: same-chain pools rank higher
    candidates = []
    for p in all_pools:
        p_sym = p["symbol"].lower()
        p_chain = p["chain"].lower()
        # Must contain the asset (e.g. USDC) in the symbol
        if sym_lower not in p_sym:
            continue
        if p["apy"] < current_apy + UPGRADE_THRESHOLD_PCT:
            continue
        same_chain = (p_chain == chain_lower)
        candidates.append((not same_chain, -p["apy"], p))  # sort: same chain first, then desc APY

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]

# --- Position table: what we know about the portfolio (USD size, asset, chain) ---
# These are updated when DeBank scan finds new values; defaults from last scan 2026-06-19.
POSITIONS = [
    {"label": "L3 Morpho Seamless USDC",    "key": "morpho_seamless_usdc_base",  "usd": 29366, "asset": "USDC", "chain": "Base"},
    {"label": "L3 Morpho Universal USDC",   "key": "morpho_universal_usdc_base", "usd": 10186, "asset": "USDC", "chain": "Base"},
    {"label": "L3 Morpho eUSD",             "key": "morpho_eusd_base",           "usd":  6204, "asset": "eUSD", "chain": "Base"},
    {"label": "L3 ExtraFi XLend USDC",      "key": "extrafi_xlend_usdc_base",    "usd": 10232, "asset": "USDC", "chain": "Base"},
    {"label": "L3 Maple Syrup USDC",        "key": "maple_syrup_usdc",           "usd":  9207, "asset": "USDC", "chain": "Ethereum"},
    {"label": "L3 Ethena sUSDe",            "key": "ethena_susde",               "usd":  2938, "asset": "USDe", "chain": "Ethereum"},
    {"label": "L3 LIDO stETH",              "key": "lido_steth",                 "usd":  2442, "asset": "ETH",  "chain": "Ethereum"},
    {"label": "L3 Hyperliquid HLP",         "key": "hyperliquid_hlp_vault",      "usd":  5340, "asset": "USDC", "chain": "Hyperliquid"},
    {"label": "L1 Morpho Universal USDC",   "key": "morpho_universal_usdc_base", "usd":  4295, "asset": "USDC", "chain": "Base"},
    {"label": "L1 Morpho eUSD",             "key": "morpho_eusd_base",           "usd":  2840, "asset": "eUSD", "chain": "Base"},
    {"label": "B3 Maple Syrup USDC",        "key": "maple_syrup_usdc",           "usd":  8456, "asset": "USDC", "chain": "Ethereum"},
    {"label": "B3 Idle USDT",               "key": None,                         "usd": 15616, "asset": "USDT", "chain": "Ethereum"},
    {"label": "B3 Avantis Junior USDC",     "key": "avantis_junior_usdc",        "usd":  1040, "asset": "USDC", "chain": "Base"},
]

def main():
    apys_only = "--apys-only" in sys.argv
    results = {"sources": {}}

    print("Fetching Morpho Blue vaults...", flush=True)
    morpho = morpho_apys()
    if "error" in morpho:
        results["sources"]["morpho"] = f"[UNAVAILABLE: {morpho['error']}]"
    else:
        results.update(morpho)
        results["sources"]["morpho"] = "blue-api.morpho.org/graphql"

    print("Fetching DeFiLlama (Maple/LIDO/ExtraFi/Avantis + pool discovery)...", flush=True)
    llama_apys, all_pools = defi_llama_apys()
    if "error" in llama_apys:
        results["sources"]["defi_llama"] = f"[UNAVAILABLE: {llama_apys['error']}]"
        all_pools = []
    else:
        results.update(llama_apys)
        results["sources"]["defi_llama"] = f"yields.llama.fi/pools ({len(all_pools)} trusted pools indexed)"

    print("Fetching Ethena sUSDe...", flush=True)
    ethena = ethena_apy()
    if "error" in ethena:
        results["sources"]["ethena"] = f"[UNAVAILABLE: {ethena['error']}]"
    else:
        results.update(ethena)
        results["sources"]["ethena"] = "ethena.fi/api/yields"

    print("Fetching Hyperliquid HLP vault (L3)...", flush=True)
    hlp = hyperliquid_vault_apr("0x5d039ece117073323ade5057a516864f4c40e653")
    if "error" in hlp:
        results["hyperliquid_hlp_vault"] = None
        results["sources"]["hyperliquid"] = f"[UNAVAILABLE: {hlp['error']}]"
    else:
        results["hyperliquid_hlp_vault"] = hlp["hyperliquid_hlp_vault"]
        results["_hyperliquid_vault_name"] = hlp.get("_vault_name", "")
        results["sources"]["hyperliquid"] = f"api.hyperliquid.xyz ({hlp.get('_vault_name', '')})"

    # Print live APYs
    print("\n--- LIVE APYs ---")
    for k, v in results.items():
        if k == "sources" or k.startswith("_"):
            continue
        label = k.replace("_", " ").title()
        if v is None:
            print(f"  {label}: [UNAVAILABLE — API returned no data]")
        elif isinstance(v, str):
            print(f"  {label}: {v}")
        elif v == 0.0 and "morpho" in k:
            print(f"  {label}: 0% ⚠️ IDLE — verify on morpho.org")
        else:
            print(f"  {label}: {v}%")

    print("\n--- SOURCES ---")
    for k, v in results["sources"].items():
        print(f"  {k}: {v}")

    if apys_only:
        return

    # --- UPGRADE RECOMMENDATIONS ---
    print("\n--- UPGRADE RECOMMENDATIONS ---")
    print(f"(threshold: >{UPGRADE_THRESHOLD_PCT}% APY gain, trusted protocols only, TVL >${MIN_TVL_M}M)\n")

    recs = []
    for pos in POSITIONS:
        current_apy = results.get(pos["key"]) if pos["key"] else 0.0
        if current_apy is None:
            current_apy = 0.0

        # Skip non-stable assets (ETH, HLP) and high-APY positions already well-placed
        if pos["asset"] not in ("USDC", "USDT", "eUSD", "USDe"):
            continue
        if pos["chain"] == "Hyperliquid":
            # HLP has structural lumpy returns — don't blindly recommend switching
            if isinstance(current_apy, (int, float)) and current_apy < UPGRADE_THRESHOLD_PCT:
                print(f"  ⚠️  {pos['label']} ({current_apy}% — HLP trough): consider USDC alternatives below")
            continue

        better = find_better_pool(current_apy or 0, pos["asset"], pos["chain"], all_pools)
        if better:
            gain = round(better["apy"] - (current_apy or 0), 2)
            annual_gain = round((pos["usd"] * gain) / 100, 0)
            same_chain = better["chain"].lower() == pos["chain"].lower()
            gas_note = "~$0.10 gas (Base)" if same_chain and pos["chain"] == "Base" else "~$15-30 gas (mainnet)" if pos["chain"] == "Ethereum" else "check gas"
            recs.append({
                "position": pos["label"],
                "usd": pos["usd"],
                "current_apy": current_apy,
                "better_project": better["project"],
                "better_symbol": better["symbol"],
                "better_chain": better["chain"],
                "better_apy": better["apy"],
                "better_tvl_m": better["tvl_m"],
                "gain_pct": gain,
                "annual_gain_usd": annual_gain,
                "gas_note": gas_note,
                "url": better["url"],
            })
            print(f"  UPGRADE: {pos['label']}")
            print(f"    Current:  {current_apy}% (${pos['usd']:,})")
            print(f"    Better:   {better['project']} — {better['symbol']} on {better['chain']} @ {better['apy']}% (TVL ${better['tvl_m']}M)")
            print(f"    Gain:     +{gain}% = +${annual_gain:,.0f}/yr")
            print(f"    Gas:      {gas_note}")
            print(f"    Link:     {better['url']}")
            print()
        elif isinstance(current_apy, (int, float)) and current_apy == 0.0:
            print(f"  ⚠️  {pos['label']}: 0% — deploy to any yielding pool (see best options below)")
            print()

    if not recs:
        print("  No upgrades found above threshold — all positions near-optimal.\n")

    # Show top 5 best available USDC pools on Base as reference
    usdc_base = sorted(
        [p for p in all_pools if "usdc" in p["symbol"].lower() and p["chain"] == "Base"],
        key=lambda x: -x["apy"]
    )[:5]
    if usdc_base:
        print("--- TOP USDC POOLS ON BASE (reference) ---")
        for p in usdc_base:
            print(f"  {p['apy']:6.2f}%  {p['project']:30}  TVL ${p['tvl_m']}M  {p['url']}")

    usdc_eth = sorted(
        [p for p in all_pools if "usdc" in p["symbol"].lower() and p["chain"] == "Ethereum"],
        key=lambda x: -x["apy"]
    )[:5]
    if usdc_eth:
        print("\n--- TOP USDC POOLS ON ETHEREUM (reference) ---")
        for p in usdc_eth:
            print(f"  {p['apy']:6.2f}%  {p['project']:30}  TVL ${p['tvl_m']}M  {p['url']}")

    print("\nJSON:")
    print(json.dumps({"apys": {k: v for k, v in results.items() if not k.startswith("_") and k != "sources"},
                      "sources": results["sources"],
                      "recommendations": recs}, indent=2))

if __name__ == "__main__":
    main()
