#!/usr/bin/env python3
"""Print everything about one item of a graded set, for a chat review.

Usage:
  item_context.py SET ITEM     e.g.  item_context.py MATH-D01 3.2
  item_context.py SET          list the set's items with score, tags and archetype
  item_context.py latest       list the most recently graded set

The bundle: the question (from exam.tex), any hint the student was given before the
attempt (submissions/<SET>/hints.json), the student's transcribed work (from the
grader's transcript.md), the grading (feedback JSON entry and the grader's comment),
the worked solution and rubric (from key.tex), and the archetype's section of the
blueprint (what is always asked, pitfalls). Item ids are <problem>.<sub-question>, as
printed on the exam.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "tools" / "config.json").read_text())


def course_dir(set_id):
    key = set_id.split("-")[0]
    if key not in CFG["courses"]:
        sys.exit(f"unknown course in set id {set_id!r}; expected one of {', '.join(CFG['courses'])}")
    return ROOT / CFG["courses"][key]["dir"]


def latest_graded():
    best = None
    for key, c in CFG["courses"].items():
        for f in (ROOT / c["dir"] / "feedback").glob("*.json"):
            if best is None or f.stat().st_mtime > best.stat().st_mtime:
                best = f
    if best is None:
        sys.exit("no graded sets yet")
    return best.stem


def tex_item(path, item):
    """The problem's introduction plus the k-th sub-question of problem n."""
    if not path.exists():
        return f"({path.name} not found)"
    tex = path.read_text()
    tex = tex.split("\\end{document}")[0]
    try:
        n, k = (int(x) for x in item.split(".")[:2])
    except ValueError:
        return f"(item id {item!r} is not of the form problem.subquestion)"
    starts = [m.start() for m in re.finditer(r"\\problem\{", tex)]
    if n < 1 or n > len(starts):
        return f"(problem {n} not found in {path.name}; it has {len(starts)} problems)"
    block = tex[starts[n - 1]: starts[n] if n < len(starts) else len(tex)]
    head, sep, rest = block.partition("\\begin{subqs}")
    if not sep:
        return block.strip()
    rest = rest.split("\\end{subqs}")[0]
    parts = re.split(r"(?m)^[ \t]*(?=\\subq\{)", rest)
    subs = [p for p in parts if p.lstrip().startswith("\\subq{")]
    if k < 1 or k > len(subs):
        return f"(sub-question {k} not found in problem {n} of {path.name}; it has {len(subs)})"
    return (head.strip() + "\n\n" + subs[k - 1].strip()).strip()


def transcript_item(path, item):
    if not path.exists():
        return "(no transcript)"
    text = path.read_text()
    sections = re.split(r"(?m)^(?=## )", text)
    n = item.split(".")[0]
    pats = [rf"^## +(Item +)?{re.escape(item)}\b", rf"^## +(P|Problem +){n}\b",
            rf"^## .*\b{re.escape(item)}\b", rf"^## .*\b(P|Problem +){n}\b"]
    for pat in pats:
        hits = [s for s in sections if re.match(pat, s)]
        if hits:
            return "\n".join(h.strip() for h in hits)
    return "(no section for this item in the transcript; read it whole: " + str(path.relative_to(ROOT)) + ")"


def fbitem_block(path, item):
    if not path.exists():
        return ""
    tex = path.read_text()
    m = re.search(r"\\begin\{fbitem\}\{" + re.escape(item) + r"\}.*?\\end\{fbitem\}", tex, re.S)
    return m.group(0) if m else ""


def blueprint_section(path, archetype):
    if not path.exists() or not archetype:
        return ""
    lines = path.read_text().split("\n")
    out, on = [], False
    for ln in lines:
        if ln.startswith("#") and f"`{archetype}`" in ln:
            on = True
        elif on and re.match(r"^#{2,3} ", ln):
            break
        if on:
            out.append(ln)
    return "\n".join(out).strip()


def hint_entry(cdir, set_id, item):
    """The item's entry in the hint log written by hints.py during the set, or None."""
    path = cdir / "submissions" / set_id / "hints.json"
    try:
        items = json.loads(path.read_text()).get("items", [])
    except (OSError, ValueError, AttributeError):
        return None
    return next((h for h in items if isinstance(h, dict) and h.get("item") == item), None)


def list_set(set_id):
    cdir = course_dir(set_id)
    fb = json.loads((cdir / "feedback" / f"{set_id}.json").read_text())
    st = json.loads((cdir / "sets" / set_id / "set.json").read_text())
    arch = {x["item"]: x["archetype"] for x in st["items"]}
    tot = sum(i["score"] or 0 for i in fb["items"] if i["status"] != "skipped_not_covered")
    mx = sum(i["max"] for i in fb["items"] if i["status"] != "skipped_not_covered")
    print(f"{set_id}: {tot:g}/{mx:g} (graded {fb.get('graded_on')})")
    for i in fb["items"]:
        flag = " assisted" if i.get("assisted") else ""
        h = hint_entry(cdir, set_id, i["item"])
        if h:
            flag += f" hint-{h.get('gap')}"
        mins = f" {i['minutes']}min" if i.get("minutes") else ""
        print(f"  {i['item']:>6}  {i['score'] if i['score'] is not None else '-':>4}/{i['max']:<3} "
              f"{i['status']:<20} {','.join(i.get('errors') or []):<28} {arch.get(i['item'], '?')}{flag}{mins}")


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    set_id = latest_graded() if args[0] == "latest" else args[0]
    if len(args) == 1:
        list_set(set_id)
        return
    item = args[1]
    cdir = course_dir(set_id)
    sdir = cdir / "sets" / set_id
    st = json.loads((sdir / "set.json").read_text())
    meta = next((x for x in st["items"] if x["item"] == item), None)
    if meta is None:
        sys.exit(f"item {item} is not in {set_id}; items: {', '.join(x['item'] for x in st['items'])}")
    fbp = cdir / "feedback" / f"{set_id}.json"
    fb = json.loads(fbp.read_text()) if fbp.exists() else {"items": []}
    entry = next((x for x in fb["items"] if x["item"] == item), None)
    lesson = cdir / "lessons" / f"{meta['archetype']}.tex"

    print(f"# {set_id} item {item} ({st.get('kind')}, archetype `{meta['archetype']}`, "
          f"level {meta.get('level')}, {meta['max']} p, budget {meta.get('minutes')} min)")
    if lesson.exists():
        print(f"Lesson available: {lesson.relative_to(ROOT)}")
    print("\n## Question (exam.tex)\n")
    print(tex_item(sdir / "exam.tex", item))
    h = hint_entry(cdir, set_id, item)
    if h:
        rungs = {1: "nudge", 2: "method", 3: "set-up"}
        print("\n## Hint given before the attempt (/hint)\n")
        print(f"highest rung {h.get('rung')} {rungs.get(h.get('rung'), '?')}, gap {h.get('gap')}; "
              f"tried before: {h.get('tried') or '(not recorded)'}")
        for g in h.get("given", []):
            print(f"- rung {g.get('rung')}: {g.get('said')}")
        print(f"cue: {h.get('cue')}\nlearned: {h.get('learned')}")
    print("\n## Student's work (transcript)\n")
    print(transcript_item(cdir / "submissions" / set_id / "transcript.md", item))
    print("\n## Grading\n")
    print(json.dumps(entry, ensure_ascii=False) if entry else "(not graded)")
    blk = fbitem_block(cdir / "feedback" / f"{set_id}.tex", item)
    if blk:
        print("\n" + blk)
    print("\n## Worked solution and rubric (key.tex)\n")
    print(tex_item(sdir / "key.tex", item))
    bp = blueprint_section(cdir / "blueprint.md", meta["archetype"])
    if bp:
        print("\n## Archetype notes (blueprint.md)\n")
        print(bp)


if __name__ == "__main__":
    main()
