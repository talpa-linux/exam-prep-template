#!/usr/bin/env python3
"""Pick the items of a graded set that get a full review, a short review, and a lesson.

Usage: select_review.py COURSE SET [--full N] [--lessons N]

Full review: lost at least a third of the item's points, or assisted, or blank;
ranked by points lost times the archetype's exam weight; at most N (default 6).
Short review: every other item that lost points (skipped items excluded).
Lessons: archetypes of full-review items whose gap was conceptual (tags concept or
method, or assisted, or blank) and that have no lessons/<id>.pdf yet; highest weight
first; at most N (default 3).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course")
    ap.add_argument("set")
    ap.add_argument("--full", type=int, default=6)
    ap.add_argument("--lessons", type=int, default=3)
    a = ap.parse_args()

    cfg = json.loads((ROOT / "tools" / "config.json").read_text())
    cdir = ROOT / cfg["courses"][a.course]["dir"]
    fb = json.loads((cdir / "feedback" / f"{a.set}.json").read_text())
    st = json.loads((cdir / "sets" / a.set / "set.json").read_text())
    bp = json.loads((cdir / "blueprint.json").read_text())
    weight = {x["id"]: x["weight"] for x in bp["archetypes"]}
    arch = {x["item"]: x["archetype"] for x in st["items"]}

    cands = []
    for it in fb["items"]:
        if it["status"] == "skipped_not_covered":
            continue
        lost = it["max"] - (it.get("score") or 0)
        if lost <= 0 and not it.get("assisted"):
            continue
        a_id = arch.get(it["item"], "?")
        heavy = (lost >= it["max"] / 3) or it.get("assisted") or it["status"] == "blank"
        cands.append({"item": it["item"], "archetype": a_id, "lost": lost,
                      "heavy": bool(heavy), "rank": lost * weight.get(a_id, 0),
                      "gap": bool(set(it.get("errors", [])) & {"concept", "method"})
                      or it.get("assisted") or it["status"] == "blank"})

    heavy = sorted((c for c in cands if c["heavy"]), key=lambda c: -c["rank"])
    full = heavy[: a.full]
    full_ids = {c["item"] for c in full}
    short = [c for c in cands if c["item"] not in full_ids]

    lessons, seen = [], set()
    for c in sorted(full, key=lambda c: -weight.get(c["archetype"], 0)):
        aid = c["archetype"]
        if not c["gap"] or aid in seen or (cdir / "lessons" / f"{aid}.pdf").exists():
            continue
        seen.add(aid)
        lessons.append(aid)
    lessons = lessons[: a.lessons]

    existing = sorted({c["archetype"] for c in cands
                       if (cdir / "lessons" / f"{c['archetype']}.pdf").exists()})
    out = {"full": [c["item"] for c in full], "short": [c["item"] for c in short],
           "lessons_to_write": lessons, "lessons_existing": existing,
           "archetype_of": {c["item"]: c["archetype"] for c in cands}}
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
