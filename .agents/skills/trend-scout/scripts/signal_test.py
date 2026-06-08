#!/usr/bin/env python3
"""
trend-scout Stage 0 — signal-information test (the Carver gate, honestly scoped).

trend-scout is a SCREENER, not a mechanical strategy. The thematic stock baskets cannot
be point-in-time backtested on free data (survivorship / no historical membership). So we
test the MECHANIC's information content on a bias-free universe — Ken French 49 industry
portfolios (free, decades, every industry that ever existed, no selection bias) — to answer:
is the signal noise, or does it carry forward-return information?

Two claims, the skill's actual differentiators:
  (a) STAGING — does relative strength (trailing 6m return) separate forward returns?
      And does EARLY (strong but NOT extended) beat LATE (strong AND extended)?
  (b) LAGGARD — within the strong-momentum cohort, does the recent LAGGARD ("cheap
      exposure that hasn't re-rated") beat the recent leader going forward?

Out-of-sample split (train < 2010, test >= 2010). Reports gross AND net of a per-rebalance
cost. This is a SANITY CHECK, not a discovery — industry momentum is already documented
(Moskowitz-Grinblatt 1999); the novel part we care about is (a)-extension and (b)-laggard.

Usage: python3 signal_test.py [--cost-bps 15] [--split 2010]
Educational, not advice.
"""
import io, sys, zipfile, urllib.request, argparse
import numpy as np
import pandas as pd

URL = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
       "49_Industry_Portfolios_CSV.zip")


def load_french_monthly():
    """Download + parse the value-weighted MONTHLY returns block (in %)."""
    raw = urllib.request.urlopen(URL, timeout=60).read()
    zf = zipfile.ZipFile(io.BytesIO(raw))
    name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
    text = zf.read(name).decode("latin-1")
    lines = text.splitlines()

    # The first data block = Avg Value Weighted Returns -- Monthly. Rows start with YYYYMM.
    # Header row is the one whose cells are industry names; capture it just before first data row.
    rows, header, started = [], None, False
    for i, ln in enumerate(lines):
        cells = [c.strip() for c in ln.split(",")]
        first = cells[0]
        if first.isdigit() and len(first) == 6:          # YYYYMM monthly row
            if header is None:
                header = [c.strip() for c in lines[i - 1].split(",")][1:]
            rows.append(cells)
            started = True
        elif started:
            break  # block ended (blank line / next section)

    def _f(x):
        try:
            return float(x)
        except ValueError:
            return np.nan
    idx = [r[0] for r in rows]
    data = [[_f(x) for x in r[1:1 + len(header)]] for r in rows]
    df = pd.DataFrame(data, index=pd.to_datetime(idx, format="%Y%m"), columns=header)
    df = df.replace([-99.99, -999], np.nan) / 100.0     # French missing codes; % -> decimal
    return df


def ann_stats(monthly_ret):
    r = monthly_ret.dropna()
    if len(r) < 12:
        return None
    cagr = (1 + r).prod() ** (12 / len(r)) - 1
    sharpe = (r.mean() / r.std()) * np.sqrt(12) if r.std() > 0 else np.nan
    return {"cagr": cagr, "sharpe": sharpe, "n": len(r)}


def t_stat(series):
    s = series.dropna()
    return s.mean() / (s.std() / np.sqrt(len(s))) if len(s) > 1 and s.std() > 0 else np.nan


def run(df, cost_bps, split_year):
    mom6 = df.rolling(6).apply(lambda x: (1 + x).prod() - 1, raw=True)   # trailing 6m cum return (RS)
    ret12 = df.rolling(12).apply(lambda x: (1 + x).prod() - 1, raw=True)  # trailing 12m cum return
    fwd1 = df.shift(-1)                                                  # forward 1m return
    cost = cost_bps / 10000.0

    months = df.index[12:-1]   # need 12m history + 1m forward
    recs = []
    for t in months:
        rs = mom6.loc[t].dropna()
        if len(rs) < 30:
            continue
        f = fwd1.loc[t]
        ext = (mom6.loc[t] - ret12.loc[t])  # 6m minus 12m cum return = 2nd-half acceleration proxy
                                            # (NOT price-vs-MA; a momentum-recency gauge for EARLY/LATE)
        recent1 = df.loc[t]                # last month's return (within-cohort leader/laggard)

        # (a) staging: quintiles by RS
        q = pd.qcut(rs, 5, labels=False, duplicates="drop")
        qf = {f"Q{k+1}": f.reindex(rs.index)[q == k].mean() for k in range(5)}

        # (a-ext) within top-quintile (strong): early (low extension) vs late (high extension)
        strong = rs[q == q.max()].index
        if len(strong) >= 4:
            e = ext.reindex(strong).dropna()
            half = len(e) // 2
            early = e.nsmallest(half).index        # strong but least extended = EARLY
            late = e.nlargest(half).index          # strong and most extended = LATE
            early_f, late_f = f.reindex(early).mean(), f.reindex(late).mean()
        else:
            early_f = late_f = np.nan

        # (b) laggard within strong cohort: top-10 by RS, split by last-month return
        cohort = rs.nlargest(10).index
        rc = recent1.reindex(cohort).dropna()
        if len(rc) >= 6:
            lag = rc.nsmallest(len(rc)//2).index   # laggards (cheap, hasn't run)
            led = rc.nlargest(len(rc)//2).index     # leaders (already ran)
            lag_f, led_f = f.reindex(lag).mean(), f.reindex(led).mean()
        else:
            lag_f = led_f = np.nan

        recs.append({"date": t, **qf, "early": early_f, "late": late_f,
                     "lag": lag_f, "led": led_f, "mkt": f.mean()})

    R = pd.DataFrame(recs).set_index("date")
    train, test = R[R.index.year < split_year], R[R.index.year >= split_year]

    def block(name, S):
        out = [f"\n## {name}  (n={len(S)} months)"]
        # staging quintiles
        qmeans = {q: S[q].mean() for q in ["Q1","Q2","Q3","Q4","Q5"]}
        spread = qmeans["Q5"] - qmeans["Q1"]
        out.append("STAGING (RS quintile, mean fwd 1m %):  " +
                   "  ".join(f"{q} {qmeans[q]*100:+.2f}" for q in qmeans))
        out.append(f"  Q5-Q1 spread {spread*100:+.2f}%/mo  t={t_stat(S['Q5']-S['Q1']):.2f}"
                   f"  vs mkt {S['mkt'].mean()*100:+.2f}%/mo")
        # early vs late within strong
        ev = (S["early"] - S["late"]).dropna()
        out.append(f"EARLY vs LATE (within strong): early {S['early'].mean()*100:+.2f}  "
                   f"late {S['late'].mean()*100:+.2f}  diff {ev.mean()*100:+.2f}%/mo  t={t_stat(ev):.2f}")
        # laggard vs leader within cohort, gross + net (this pick turns over fully each month)
        lv = (S["lag"] - S["led"]).dropna()
        net = lv.mean() - 2 * cost   # buy laggard / not-leader ~ one extra round-trip
        out.append(f"LAGGARD vs LEADER (within strong cohort): lag {S['lag'].mean()*100:+.2f}  "
                   f"led {S['led'].mean()*100:+.2f}")
        out.append(f"  gross diff {lv.mean()*100:+.2f}%/mo  t={t_stat(lv):.2f}  "
                   f"net@{cost_bps}bps {net*100:+.2f}%/mo")
        return "\n".join(out), {"q5q1": spread, "early_late": ev.mean(),
                                "lag_led_gross": lv.mean(), "lag_led_net": net,
                                "lag_led_t": t_stat(lv)}

    print(f"TREND-SCOUT Stage 0 — signal-information test (Ken French 49 industries)")
    print(f"bias-free universe | OOS split {split_year} | cost {cost_bps}bps | months {len(R)}")
    print("=" * 78)
    tr_txt, _ = block("TRAIN (pre-%d)" % split_year, train)
    te_txt, te = block("TEST / OUT-OF-SAMPLE (>=%d)" % split_year, test)
    print(tr_txt); print(te_txt)

    print("\n" + "=" * 78)
    print("VERDICT (out-of-sample is what counts):")
    def mark(x, thr=0): return "signal" if x > thr else "no/weak"
    print(f"  (a) staging Q5-Q1:        {te['q5q1']*100:+.2f}%/mo  -> {mark(te['q5q1'])}")
    print(f"  (a) EARLY>LATE:           {te['early_late']*100:+.2f}%/mo  -> {mark(te['early_late'])}")
    print(f"  (b) LAGGARD>LEADER net:   {te['lag_led_net']*100:+.2f}%/mo "
          f"(t={te['lag_led_t']:.2f}) -> {mark(te['lag_led_net'])}")
    print("\nScreener bar: signal carries forward info OOS, net of costs. Momentum itself is")
    print("known (Moskowitz-Grinblatt 1999); the EARLY>LATE and LAGGARD claims are the novel test.")
    print("Educational, not advice. Sanity check, not a tradeable strategy.")
    return te


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost-bps", type=float, default=15)
    ap.add_argument("--split", type=int, default=2010)
    a = ap.parse_args()
    df = load_french_monthly()
    run(df, a.cost_bps, a.split)
