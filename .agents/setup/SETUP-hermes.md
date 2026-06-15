# Proactive Advisor on Hermes-AI

Native primitives: **hermes scheduler** (or system crontab) + **hermes skills** + preloaded sessions.
Same RECOMMEND-ONLY skills as the other two backends.

## 1. Install skills

```bash
npx -y skills add dzianisv/backtest --agent hermes-agent
# or by URL, per skill:
hermes skills install https://raw.githubusercontent.com/dzianisv/backtest/main/.agents/skills/dip-screener/SKILL.md
hermes skills install https://raw.githubusercontent.com/dzianisv/backtest/main/.agents/skills/crypto-dip-scanner/SKILL.md
hermes skills install https://raw.githubusercontent.com/dzianisv/backtest/main/.agents/skills/signal-convergence-alert/SKILL.md
hermes skills install https://raw.githubusercontent.com/dzianisv/backtest/main/.agents/skills/regime-detection/SKILL.md
# ... + fomc-monitor, trend-stock-research, 13f-watch, congressman-stock-watch, multi-lens-quorum, risk-management
hermes skills list   # each installed skill shows as a /slash-command
```
The `dip-screener` / `crypto-dip-scanner` scripts ride along; ensure the install copies `scripts/`
(URL install pulls SKILL.md only — for the .py helpers use `npx skills add ... --copy` or vendor them).

## 2. Scheduled runs

If hermes has a native scheduler, register the slots there. Otherwise system crontab driving a preloaded
hermes session:

```bash
# scripts/hermes-run.sh
#!/usr/bin/env bash
cd "$HOME/workspace/backtest"
hermes -s dip-screener,crypto-dip-scanner,regime-detection,signal-convergence-alert \
  -p "$1"   # one-shot prompt mode
```

```cron
CRON_TZ=UTC
45 7 * * 1-5  ~/workspace/backtest/scripts/hermes-run.sh "/dip-screener: scan, regime-gate, alert only HIGH dips in RISK_ON"
50 7 * * 1-5  ~/workspace/backtest/scripts/hermes-run.sh "/crypto-dip-scanner: alert only if coin >=-30% from ATH AND F&G<25"
0  8 * * 1-5  ~/workspace/backtest/scripts/hermes-run.sh "/regime-detection + /fomc-monitor: alert only if changed"
15 8 * * 1-5  ~/workspace/backtest/scripts/hermes-run.sh "/trend-stock-research broad: append to the durable narrative pool, no alert"
30 8 * * 1-5  ~/workspace/backtest/scripts/hermes-run.sh "/signal-convergence-alert: alert if >=2 signals same ticker"
30 9 * * 1    ~/workspace/backtest/scripts/hermes-run.sh "Run full weekly brief pipeline (collect, quorum top5, risk veto, synthesize) and DM it"
```

## 3. Standing mandate

Hermes loads agent identity from its system prompt / agent config. Paste the contents of
`.agents/setup/AGENTS.template.md` into the hermes investor agent's system prompt so the standing
RECOMMEND-ONLY mandate + weekly pipeline persists across sessions.

## 4. Notify

Pipe non-SILENT output to your channel (Telegram CLI / hermes' own delivery):
```bash
OUT=$(hermes -s ... -p "$1"); [ "${OUT//[[:space:]]/}" = SILENT ] || notify "$OUT"
```

## Done when
- [ ] `hermes skills list` shows all skills as slash-commands.
- [ ] Scheduler/crontab has the 6 slots (CRON_TZ=UTC).
- [ ] AGENTS.template.md mandate is in the hermes system prompt.
- [ ] A test run alerts on a real condition and prints SILENT otherwise.
