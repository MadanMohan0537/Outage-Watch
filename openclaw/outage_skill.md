# OpenClaw Skill: Outage Watch

This defines how to wire the diagnosis script into OpenClaw as a heartbeat
skill. OpenClaw skills are just instructions + a tool/command it's allowed
to run — adapt the exact registration syntax to whatever your installed
OpenClaw version expects (check `openclaw skills --help` or the skills
directory in your OpenClaw config, since this changes between releases).

## Skill definition

```yaml
name: outage-watch
description: >
  Periodically checks the sample site's health and, on failure, runs the
  local log-matching diagnosis script. Reports findings only — does not
  take remediation action on its own.
trigger: heartbeat
schedule: "*/5 * * * *"   # every 5 minutes; tune to taste
command: >
  python3 /absolute/path/to/outage-agent/scripts/diagnose.py
  --url http://localhost:5001 --use-llm --model qwen2.5:7b
on_success: report_to_user
on_failure: report_to_user
permissions:
  - read: outage-agent/logs/app.log
  - read_write: outage-agent/incidents/incident_history.json
  - network: localhost only
notes: >
  This skill is intentionally diagnose-and-recommend only. It must not be
  given permission to restart services, modify code, or run remediation
  commands. If you later want it to auto-apply LOW-RISK fixes (e.g.
  restarting a known-safe service), add that as an explicit, narrowly
  scoped follow-up skill with its own permission grant — do not broaden
  this skill's permissions to do it.
```

## What happens each heartbeat

1. OpenClaw wakes up on its schedule (heartbeat) and runs the command above.
2. `diagnose.py` hits `/health` on the sample site.
3. If healthy, it prints `[OK]` and OpenClaw has nothing to report.
4. If down, it reads the latest outage block from `logs/app.log`, matches
   it against `incidents/incident_history.json`, and prints a diagnosis +
   recommended fix (optionally polished by the local Qwen model via
   Ollama, if `--use-llm` is set and `ollama` is running).
5. OpenClaw should relay that output to you (via whatever channel you've
   configured — WhatsApp, Telegram, Slack, etc.) rather than acting on it.
6. If no historical match is found, the script logs an "unconfirmed"
   incident to the history file so you can fill in the real diagnosis and
   fix later — this is how the match quality improves over time.

## Closing the loop (manual, by design)

After you investigate and fix a real or unconfirmed incident, edit its
entry in `incidents/incident_history.json`:
- Replace `"diagnosis": "UNCONFIRMED - needs human triage"` with what
  actually happened.
- Replace `"recommended_fix"` with what actually fixed it.
- Set `"confirmed_resolution": true`.

This keeps the match quality trustworthy — the agent only ever recommends
fixes that a human has actually verified worked before.
