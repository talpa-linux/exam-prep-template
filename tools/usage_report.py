#!/usr/bin/env python3
"""usage_report.py [DAYS]

What this project has used, from Claude Code's own transcripts (main sessions and
sub-agents), priced at list API rates. Default: the last 8 days. The dollar figure is
an "API-equivalent": the plan's percentage meters are the real limit, this only shows
how your use is spread over days, models and sessions.

Calibration seen in October 2026 on a Pro plan: about $26 of this per 5-hour window and
about $200 per week were 100%. Your plan may differ: compare the app's usage meters with
this report once to calibrate. See guide/usage.pdf, section "What it costs".
"""
import collections
import datetime
import glob
import json
import os
import re
import sys

# Claude Code keeps each project's transcripts in ~/.claude/projects/<path with every
# character other than a letter or digit replaced by "-">.
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
ROOT = os.path.join(CONFIG, "projects", re.sub(r"[^A-Za-z0-9]", "-", PROJECT))
# $ per million tokens: input, cache write (5 min), cache read, output; by model family
PRICE = {"opus": (4, 5, 0.2, 20), "sonnet": (2, 2.5, 0.2, 10), "haiku": (1, 1.25, 0.1, 5)}

FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def family(model):
    return next((f for f in PRICE if f in str(model)), None)


def messages():
    seen = {}
    for path in glob.glob(ROOT + "/**/*.jsonl", recursive=True):
        for line in open(path, errors="ignore"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            m = d.get("message")
            if d.get("type") != "assistant" or not isinstance(m, dict):
                continue
            if family(m.get("model")) and m.get("usage"):
                key = m.get("id") or d.get("uuid")  # forked sessions repeat messages
                seen.setdefault(key, (d["timestamp"], family(m["model"]), m["usage"]))
    for ts, model, u in seen.values():
        t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
        yield t, model, [u.get(f, 0) for f in FIELDS]


def dollars(model, toks):
    return sum(n * p for n, p in zip(toks, PRICE[model])) / 1e6


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    since = datetime.datetime.now().astimezone() - datetime.timedelta(days=days)
    per_day = collections.defaultdict(lambda: collections.defaultdict(float))
    tokens = collections.defaultdict(lambda: [0, 0, 0, 0])
    for t, model, toks in messages():
        if t < since:
            continue
        per_day[t.date()][model] += dollars(model, toks)
        for i, n in enumerate(toks):
            tokens[model][i] += n
    if not per_day:
        print(f"no usage found in the last {days} days under {ROOT}")
        return
    total = 0.0
    print(f"{'day':<12}{'Opus':>9}{'Sonnet':>9}{'Haiku':>9}{'total':>9}   (API-equivalent $)")
    for day in sorted(per_day):
        o, s, h = (per_day[day][f] for f in ("opus", "sonnet", "haiku"))
        total += o + s + h
        print(f"{day!s:<12}{o:>9.2f}{s:>9.2f}{h:>9.2f}{o + s + h:>9.2f}")
    print(f"{'total':<12}{'':>27}{total:>9.2f}")
    print("\ntokens (millions)   fresh in   cache write   cache read   output")
    for model, n in tokens.items():
        print(f"{model:<19}{n[0] / 1e6:>8.2f}{n[1] / 1e6:>13.2f}{n[2] / 1e6:>13.1f}{n[3] / 1e6:>9.2f}")


if __name__ == "__main__":
    main()
