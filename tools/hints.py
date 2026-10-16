#!/usr/bin/env python3
"""Hints asked for while working a set, before it is graded (the /hint skill).

  hints.py pending                 sets handed out but not graded yet, newest first
  hints.py open SET ITEM           everything the hint session needs for one item
  hints.py log  SET ITEM --rung N --gap G --said TEXT [--cue TEXT] [--learned TEXT] [--tried TEXT]
  hints.py show SET [--json]       the hints logged for a set
  hints.py drop SET ITEM           remove a hint logged on the wrong item (only on the student's word)

The log is submissions/<SET>/hints.json.  The grader reads it, and `ledger.py record` refuses
feedback that credits work done after a logged hint as unaided, then joins the hint (rung, gap,
cue, learned) into the item's ledger row so the next set can re-test exactly that move.

Rungs: 1 nudge (a question pointing at what in the problem signals the approach), 2 method (the
method or idea named, and why it applies), 3 set-up (the first concrete step, not worked out).
Nothing beyond rung 3 is given before grading.  Gap: what was missing (concept, method, setup).
No hints on a graded set (that is /review) or on the held-out exam.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger as L  # noqa: E402
import item_context as IC  # noqa: E402

WARN_KINDS = {
    "diagnostic": "a diagnostic measures where you start, and a hint hides exactly that",
    "full": "a full mock is the grade prediction under exam conditions, and a hint weakens it",
}


def course_of(cfg, set_id):
    course = L.get_course(cfg, str(set_id).split("-")[0])
    return course, L.check_set_arg(course, set_id)


def load_open_set(cfg, set_id, item=None):
    """(course, set id, set.json) for a set that may still get hints; DataError otherwise."""
    course, sid = course_of(cfg, set_id)
    path = course.path / "sets" / sid / "set.json"
    data = L.load_json(path)
    if (course.path / "feedback" / f"{sid}.json").exists():
        raise L.DataError(f"{sid} is graded already, so there is nothing to hint: go over it with "
                          f"/review {sid}{' ' + item if item else ''}")
    if data.get("kind") == "holdout":
        raise L.DataError(f"{sid} is the held-out real exam: no hints, it is the benchmark")
    items = [it.get("item") for it in data.get("items", []) if isinstance(it, dict)]
    if item is not None and item not in items:
        raise L.DataError(f"item {item} is not in {sid}; items: {', '.join(map(str, items))}")
    return course, sid, data


def read_log(course, sid, data):
    entries, problems = L.load_hints(course, sid, {it["item"] for it in data["items"]})
    if problems:
        raise L.DataError(problems + ["the hint log is written only by tools/hints.py"])
    return entries


def write_log(course, sid, data, entries):
    path = L.hints_path(course, sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    order = [it["item"] for it in data["items"]]
    items = [entries[i] for i in order if i in entries]
    tmp = path.with_name(f".hints.json.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"course": course.key, "set": sid, "items": items}, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def rung_name(n):
    return f"{n} {L.HINT_RUNGS.get(n, '?')}"


def cmd_pending(cfg, args):
    out = []
    for course in cfg.courses.values():
        for sid in L.list_set_ids(course):
            sdir = course.path / "sets" / sid
            if not (sdir / "set.json").exists() or (course.path / "feedback" / f"{sid}.json").exists():
                continue
            try:
                data = L.load_json(sdir / "set.json")
                kind, n = data.get("kind"), len(read_log(course, sid, data))
                note = f"  {n} hint{'s' if n != 1 else ''} logged" if n else ""
            except (L.DataError, KeyError, TypeError, AttributeError):
                kind, note = "?", "  (set.json or hints.json unreadable)"
            out.append(((sdir / "set.json").stat().st_mtime, f"{sid}  {kind}  final {course.exam_date.isoformat()}{note}"))
    if not out:
        print("no set is waiting to be graded")
    for _, line in sorted(out, reverse=True):
        print(line)
    return 0


def cmd_open(cfg, args):
    course, sid, data = load_open_set(cfg, args.set, args.item)
    meta = next(it for it in data["items"] if it["item"] == args.item)
    sdir = course.path / "sets" / sid
    entries = read_log(course, sid, data)
    print(f"# {sid} item {args.item} ({data.get('kind')}, archetype `{meta['archetype']}`, level {meta.get('level')}, "
          f"{meta['max']} p, budget {meta.get('minutes')} min)")
    if data.get("kind") in WARN_KINDS:
        print(f"\nNOTE: {sid} is a {data['kind']}: {WARN_KINDS[data['kind']]}. Say so and ask once before hinting.")
    print("\n## Question (exam.tex)\n")
    print(IC.tex_item(sdir / "exam.tex", args.item))
    print("\n## Hints already given on this item\n")
    h = entries.get(args.item)
    if h is None:
        print("(none)")
    else:
        print(f"highest rung {rung_name(h['rung'])}, gap {h['gap']}; tried before: {h.get('tried') or '(not recorded)'}")
        for g in h["given"]:
            print(f"- rung {rung_name(g['rung'])} at {g.get('at', '?')}: {g['said']}")
        print(f"cue: {h['cue']}\nlearned: {h['learned']}")
    print("\n## What this student needed before on this question type\n")
    try:
        rows = [r for r in L.chrono(L.read_ledger(course)) if r["archetype"] == meta["archetype"]
                and r["status"] != "skipped_not_covered"]
    except L.DataError:
        rows = []
    shown = 0
    for r in reversed(rows):
        if L.row_hint(r):
            hh = L.row_hint(r)
            print(f"- {r['set']} {r['item']}: needed a hint ({L.HINT_RUNGS[hh['rung']]}): {hh['learned']}")
        elif r["errors"] or L.fr(r["score"]) < L.fr(r["max"]) or L.row_assisted(r):
            tag = ", ".join(r["errors"]) or "-"
            print(f"- {r['set']} {r['item']}: {L.fmt_num(r['score'])}/{L.fmt_num(r['max'])} [{tag}]"
                  f"{' assisted' if L.row_assisted(r) else ''}: {r.get('takeaway') or ''}")
        else:
            continue
        shown += 1
        if shown == 4:
            break
    if not shown:
        print("(nothing recorded)")
    lesson = course.path / "lessons" / f"{meta['archetype']}.pdf"
    if lesson.exists():
        print(f"\nA lesson on this type exists: {L.rel(lesson)}")
    print("\n## FOR THE TUTOR ONLY: never show, quote or paraphrase any of this beyond the rung you give\n")
    print("### Worked solution and rubric (key.tex)\n")
    print(IC.tex_item(sdir / "key.tex", args.item))
    bp = IC.blueprint_section(course.path / "blueprint.md", meta["archetype"])
    if bp:
        print("\n### Archetype notes (blueprint.md)\n")
        print(bp)
    return 0


def cmd_log(cfg, args):
    course, sid, data = load_open_set(cfg, args.set, args.item)
    P = []
    if args.gap not in L.HINT_GAPS:
        P.append(f"--gap must be one of {', '.join(L.HINT_GAPS)}, got {args.gap!r}")
    for name in ("said", "cue", "learned", "tried"):
        m = L.hint_text_problem(name, getattr(args, name), required=(name == "said"))
        if m:
            P.append("--" + m)
    entries = read_log(course, sid, data)
    old = entries.get(args.item)
    if old is None:
        for name in ("cue", "learned"):
            if getattr(args, name) is None:
                P.append(f"--{name} is required for the first hint on an item")
    if P:
        raise L.DataError(P + ["nothing was logged"])
    at = datetime.now().isoformat(timespec="minutes")
    given = {"rung": args.rung, "said": args.said.strip(), "at": at}
    if old is None:
        new = {"item": args.item, "rung": args.rung, "gap": args.gap, "cue": args.cue.strip(),
               "learned": args.learned.strip(), "tried": (args.tried or "").strip() or None, "given": [given]}
    else:
        new = dict(old)
        new["rung"] = max(old["rung"], args.rung)
        new["gap"] = args.gap
        for name in ("cue", "learned", "tried"):
            if getattr(args, name) is not None:
                new[name] = getattr(args, name).strip()
        new["given"] = list(old["given"]) + [given]
    entries[args.item] = new
    write_log(course, sid, data, entries)
    print(f"logged {sid} {args.item}: rung {rung_name(new['rung'])}, gap {new['gap']} "
          f"({len(new['given'])} hint{'s' if len(new['given']) != 1 else ''} on this item). When graded, the work "
          f"after the hint scores as help and this type comes back in the next training set.")
    return 0


def cmd_show(cfg, args):
    course, sid = course_of(cfg, args.set)
    data = L.load_json(course.path / "sets" / sid / "set.json")
    entries = read_log(course, sid, data)
    if args.json:
        print(json.dumps({"course": course.key, "set": sid,
                          "items": [entries[i["item"]] for i in data["items"] if i["item"] in entries]},
                         ensure_ascii=False, indent=1))
        return 0
    if not entries:
        print(f"{sid}: no hints logged")
        return 0
    print(f"{sid}: hints logged on {len(entries)} item{'s' if len(entries) != 1 else ''}")
    for it in data["items"]:
        h = entries.get(it["item"])
        if h:
            print(f"  {it['item']:>6}  rung {rung_name(h['rung']):<10} gap {h['gap']:<8} learned: {h['learned']}")
    return 0


def cmd_drop(cfg, args):
    course, sid, data = load_open_set(cfg, args.set, args.item)
    entries = read_log(course, sid, data)
    if args.item not in entries:
        raise L.DataError(f"{sid} {args.item} has no hint logged")
    del entries[args.item]
    write_log(course, sid, data, entries)
    print(f"dropped the hint on {sid} {args.item}")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="hints.py", description="Hints logged while working a set, before grading.")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="COMMAND")
    p = sub.add_parser("pending", help="sets handed out but not graded yet")
    p.set_defaults(fn=cmd_pending)
    p = sub.add_parser("open", help="context for a hint on one item (question, earlier hints, key for the tutor)")
    p.add_argument("set")
    p.add_argument("item")
    p.set_defaults(fn=cmd_open)
    p = sub.add_parser("log", help="record a hint that was given")
    p.add_argument("set")
    p.add_argument("item")
    p.add_argument("--rung", type=int, required=True, choices=sorted(L.HINT_RUNGS), help="1 nudge, 2 method, 3 set-up")
    p.add_argument("--gap", required=True, help=" | ".join(L.HINT_GAPS))
    p.add_argument("--said", required=True, help="what the student was told, in one or two sentences")
    p.add_argument("--cue", help="what in the question signals the move (required on the first hint)")
    p.add_argument("--learned", help="the move the student had to be told, as a rule for next time (required on the first hint)")
    p.add_argument("--tried", help="what the student had before asking")
    p.set_defaults(fn=cmd_log)
    p = sub.add_parser("show", help="hints logged for a set")
    p.add_argument("set")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("drop", help="remove a hint logged on the wrong item")
    p.add_argument("set")
    p.add_argument("item")
    p.set_defaults(fn=cmd_drop)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.fn(L.load_config(), args)
    except L.DataError as e:
        return L.fail(e.msgs)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
