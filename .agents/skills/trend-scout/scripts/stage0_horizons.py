#!/usr/bin/env python3
"""
Stage 0 extension — test the LAGGARD and STAGING claims across forward horizons.

The 1-month test refuted "buy the cheap laggard within a hot theme." But a fundamental
catch-up thesis could live at 3/6/12 months, not 1. This checks every horizon, OOS, so the
design decision (invert to buy-strength vs keep laggard) rests on evidence, not the 1m point.

Overlapping forward windows inflate t-stats; we read the SIGN and magnitude, not significance.
Educational, not advice.
"""
import numpy as np, pandas as pd
from signal_test import load_french_monthly

def fwd_cum(df, h):
    return (1 + df).rolling(h).apply(lambda x: x.prod(), raw=True).shift(-h) - 1

def diffs_at(df, h, split=2010):
    mom6 = df.rolling(6).apply(lambda x: (1 + x).prod() - 1, raw=True)
    ret12 = df.rolling(12).apply(lambda x: (1 + x).prod() - 1, raw=True)
    fwd = fwd_cum(df, h)
    rows = []
    for t in df.index[12:-h-1]:
        rs = mom6.loc[t].dropna()
        if len(rs) < 30: continue
        f = fwd.loc[t]; ext = mom6.loc[t]-ret12.loc[t]; recent1 = df.loc[t]
        q = pd.qcut(rs,5,labels=False,duplicates="drop")
        q5 = f.reindex(rs.index)[q==q.max()].mean(); q1 = f.reindex(rs.index)[q==0].mean()
        strong = rs[q==q.max()].index
        e = ext.reindex(strong).dropna(); half=len(e)//2
        early = f.reindex(e.nsmallest(half).index).mean() if half else np.nan
        late  = f.reindex(e.nlargest(half).index).mean() if half else np.nan
        cohort = rs.nlargest(10).index; rc = recent1.reindex(cohort).dropna()
        if len(rc)>=6:
            lag=f.reindex(rc.nsmallest(len(rc)//2).index).mean()
            led=f.reindex(rc.nlargest(len(rc)//2).index).mean()
        else: lag=led=np.nan
        rows.append({"date":t,"q5q1":q5-q1,"early_late":early-late,"lag_led":lag-led})
    R=pd.DataFrame(rows).set_index("date")
    te=R[R.index.year>=split]
    # express as %/month (annualize-neutral) by dividing the h-horizon diff by h
    return {k: te[k].mean()/h*100 for k in ["q5q1","early_late","lag_led"]}, len(te)

if __name__=="__main__":
    df=load_french_monthly()
    print("Stage 0 multi-horizon (OOS >=2010, Ken French 49). Values = %/MONTH-equivalent diff.")
    print("="*72)
    print(f"{'horizon':>8} {'Q5-Q1(mom)':>12} {'EARLY-LATE':>12} {'LAG-LED':>12} {'n':>6}")
    for h in [1,3,6,12]:
        d,n=diffs_at(df,h)
        print(f"{h:>6}m {d['q5q1']:>11.3f} {d['early_late']:>12.3f} {d['lag_led']:>12.3f} {n:>6}")
    print("-"*72)
    print("LAG-LED > 0 at some horizon would rescue the laggard thesis. Negative = buy-strength wins.")
