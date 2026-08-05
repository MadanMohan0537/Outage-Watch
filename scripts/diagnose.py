#!/usr/bin/env python3
"""
Outage detection + log matching + diagnosis (recommend-only, no auto-fix).

What it does, each time it's run:
  1. Calls the sample site's /health endpoint.
  2. If healthy: prints "no outage" and exits.
  3. If down: reads the most recent outage block from logs/app.log,
     extracts an error signature (error_type + keywords), and matches
     it against incidents/incident_history.json.
  4. If a confident match is found: prints the historical diagnosis and
     recommended fix (optionally polished into a short write-up by a
     local Ollama model, if available).
  5. If no match is found: prints the raw log excerpt and says this is
     a new/unrecognized outage type that needs human triage, and
     appends an "unconfirmed" record to the incident history so a
     human can fill in the diagnosis/fix later.

This script intentionally does NOT execute any remediation. It only
diagnoses and recommends. Wire it into OpenClaw's heartbeat via
openclaw/outage_skill.md.

Usage:
  python diagnose.py [--url BASE_URL] [--use-llm]
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
LOG_FILE = os.path.join(BASE_DIR, "logs", "app.log")
HISTORY_FILE = os.path.join(BASE_DIR, "incidents", "incident_history.json")

OUTAGE_BLOCK_RE = re.compile(
    r"---- OUTAGE START ----\n(.*?)\n---- OUTAGE END ----", re.DOTALL
)


def load_history():
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def get_latest_outage_block():
    if not os.path.exists(LOG_FILE):
        return None
    with open(LOG_FILE, "r") as f:
        content = f.read()
    matches = OUTAGE_BLOCK_RE.findall(content)
    if not matches:
        return None
    return matches[-1]


def parse_outage_block(block):
    fields = {}
    lines = block.splitlines()
    trace_lines = []
    in_trace = False
    for line in lines:
        if line.startswith("traceback:"):
            in_trace = True
            continue
        if in_trace:
            trace_lines.append(line)
        elif ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()
    fields["traceback"] = "\n".join(trace_lines).strip()
    return fields


def extract_keywords(text):
    text = text.lower()
    return set(re.findall(r"[a-z0-9_]+(?:\s[a-z0-9_]+)?", text))


def score_match(incident, error_type, traceback_text):
    score = 0
    if incident["error_type"] == error_type:
        score += 5
    trace_lower = traceback_text.lower()
    for kw in incident.get("keywords", []):
        if kw.lower() in trace_lower:
            score += 1
    return score


def find_best_match(history, error_type, traceback_text):
    best = None
    best_score = 0
    for incident in history["incidents"]:
        s = score_match(incident, error_type, traceback_text)
        if s > best_score:
            best_score = s
            best = incident
    return best, best_score


def polish_with_ollama(diagnosis, fix, raw_trace, model="qwen2.5:7b"):
    """Optional: ask a local Ollama model to write a short human-readable
    summary. Falls back silently to the raw diagnosis/fix if Ollama isn't
    running or the ollama Python package isn't installed."""
    try:
        import ollama
    except ImportError:
        return None
    try:
        prompt = (
            "You are an SRE assistant. Given a matched historical diagnosis and fix "
            "for a site outage, write a concise 3-4 sentence incident summary a human "
            "on-call engineer can read in 10 seconds. Do not invent new facts.\n\n"
            f"Diagnosis: {diagnosis}\n\nRecommended fix: {fix}\n\n"
            f"Raw error trace:\n{raw_trace}\n"
        )
        resp = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
        return resp["message"]["content"].strip()
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Check for outage, match logs, diagnose.")
    parser.add_argument("--url", default="http://localhost:5001", help="base URL of the sample site")
    parser.add_argument("--use-llm", action="store_true", help="polish output with local Ollama model")
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model name")
    args = parser.parse_args()

    try:
        resp = requests.get(f"{args.url}/health", timeout=5)
        healthy = resp.status_code == 200
    except requests.exceptions.RequestException:
        healthy = False

    if healthy:
        print("[OK] Site is healthy. No outage detected.")
        return

    print("[ALERT] Outage detected (health check failed or unreachable).")

    block = get_latest_outage_block()
    if not block:
        print("No log entry found to diagnose. Manual investigation needed.")
        sys.exit(1)

    fields = parse_outage_block(block)
    error_type = fields.get("error_type", "Unknown")
    traceback_text = fields.get("traceback", "")

    print(f"\nIncident: {fields.get('incident_id', 'unknown')}")
    print(f"Timestamp: {fields.get('timestamp', 'unknown')}")
    print(f"Error type: {error_type}")
    print(f"\nRaw trace:\n{traceback_text}\n")

    history = load_history()
    match, score = find_best_match(history, error_type, traceback_text)

    if match and score >= 5:
        print(f"[MATCH] Matched against historical incident {match['incident_id']} (score={score})")
        diagnosis = match["diagnosis"]
        fix = match["recommended_fix"]

        summary = None
        if args.use_llm:
            summary = polish_with_ollama(diagnosis, fix, traceback_text, model=args.model)

        if summary:
            print(f"\n--- AI Summary ---\n{summary}\n")
        print(f"--- Diagnosis ---\n{diagnosis}\n")
        print(f"--- Recommended fix (human review required) ---\n{fix}\n")
    else:
        print("[NO MATCH] This does not closely match any known past incident.")
        print("Recommend manual investigation. Logging as an unconfirmed incident for future reference.\n")
        new_record = {
            "incident_id": fields.get("incident_id", f"unconfirmed-{datetime.now(timezone.utc).isoformat()}"),
            "error_type": error_type,
            "first_seen": fields.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "log_excerpt": traceback_text[:500],
            "keywords": list(extract_keywords(traceback_text))[:10],
            "diagnosis": "UNCONFIRMED - needs human triage",
            "recommended_fix": "UNCONFIRMED - needs human triage",
            "confirmed_resolution": False,
        }
        history["incidents"].append(new_record)
        save_history(history)
        print(f"Recorded as {new_record['incident_id']} pending human review.")


if __name__ == "__main__":
    main()
