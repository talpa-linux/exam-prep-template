#!/usr/bin/env python3
"""Set up, inspect and archive courses (used by /start; no model calls).

  course.py add KEY --name NAME --exam-date YYYY-MM-DD [--dir DIR]
  course.py study-days DAY [DAY ...]          e.g. study-days Tue Wed Thu
  course.py list                              all courses and how far their set-up is
  course.py state KEY [--json]                the set-up steps of one course, and the next one
  course.py inventory KEY                     the files in <dir>/materials/ (names, sizes, pages)
  course.py check-intake KEY                  validate <dir>/intake.json
  course.py holdout KEY FILE [FILE ...]       move the reserved real final (and its answers)
                                              from materials/ into holdout/
  course.py holdout KEY --none                no exam is held out for this course
  course.py pass-mark KEY GRADE --why TEXT    the grade the final itself must reach (0-10)
  course.py archive KEY [--label LABEL]       move the course to archive/LABEL/ and drop it
                                              from config.json (a new quarter)

Paths printed are relative to the project root. FILE arguments are relative to
<dir>/materials/ (or to the project root, or absolute).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
CONFIG = TOOLS / "config.json"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,7}$")
ROLES = ("exam", "answers", "course_info", "schedule", "notes", "exercises",
         "formula_sheet", "software", "other")
RESERVED_DIRS = {"tools", "prompts", "guide", "progress", "archive", ".claude", ".git"}


def die(msg, code=1):
    print(f"course.py: {msg}", file=sys.stderr)
    sys.exit(code)


def rel(p):
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


# ------------------------------------------------------------------------------ config
def read_config(required=True):
    if not CONFIG.exists():
        if required:
            die("no tools/config.json yet: add a course first (course.py add ...)")
        return {"courses": {}, "study_days": ["Mon", "Tue", "Wed", "Thu", "Fri"]}
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        die(f"tools/config.json does not parse: {e}")
    data.setdefault("courses", {})
    data.setdefault("study_days", ["Mon", "Tue", "Wed", "Thu", "Fri"])
    return data


def write_json(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def course_of(cfg, key):
    k = key.upper()
    if k not in cfg["courses"]:
        known = ", ".join(cfg["courses"]) or "none yet"
        die(f"unknown course {key!r} (configured: {known})")
    c = cfg["courses"][k]
    return k, c, ROOT / c["dir"]


def parse_date(s):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def today():
    return parse_date(os.environ.get("PREP_TODAY", "")) or date.today()


# ------------------------------------------------------------------------------ files
def files_under(d):
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.rglob("*"), key=lambda q: str(q).lower()):
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(d).parts):
            out.append(p)
    return out


def pdf_pages(p):
    if p.suffix.lower() != ".pdf" or not shutil.which("pdfinfo"):
        return None
    try:
        r = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"^Pages:\s+(\d+)", r.stdout, re.M)
    return int(m.group(1)) if m else None


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def resolve_material(cdir, f):
    for cand in (cdir / "materials" / f, ROOT / f, Path(f)):
        if cand.is_file():
            return cand.resolve()
    return None


# ------------------------------------------------------------------------------ intake
def load_intake(key, cdir):
    """(data, problems). data is None when the file is missing or unreadable."""
    path = cdir / "intake.json"
    if not path.exists():
        return None, ["intake.json not written yet"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, [f"intake.json does not parse: {e}"]
    probs = []
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        return None, ['intake.json: top level must be an object with a "files" list']
    if data.get("course") not in (None, key):
        probs.append(f'"course" is {data.get("course")!r}, expected "{key}"')
    id_re = re.compile(rf"^{re.escape(key)}-\d{{4}}-\d{{2}}(-[A-Za-z0-9]+)?$")
    ids, paths = set(), set()
    for i, f in enumerate(data["files"]):
        where = f"files[{i}]"
        if not isinstance(f, dict):
            probs.append(f"{where}: must be an object")
            continue
        p = f.get("path")
        where = f"files[{i}] ({p})"
        if not isinstance(p, str) or not (cdir / p).is_file():
            probs.append(f"{where}: path must be a file relative to the course directory")
        elif p in paths:
            probs.append(f"{where}: listed twice")
        paths.add(p)
        if f.get("role") not in ROLES:
            probs.append(f"{where}: role must be one of {', '.join(ROLES)}, got {f.get('role')!r}")
        if f.get("role") == "exam":
            eid = f.get("exam_id")
            if not isinstance(eid, str) or not id_re.match(eid):
                probs.append(f"{where}: exam_id must look like {key}-YYYY-MM (optionally -SUFFIX), got {eid!r}")
            elif eid in ids:
                probs.append(f"{where}: exam_id {eid} used twice")
            ids.add(eid)
            a = f.get("answers")
            if a not in (None, "same") and not (isinstance(a, str) and (cdir / a).is_file()):
                probs.append(f'{where}: answers must be null, "same" or a file path, got {a!r}')
    sw = data.get("software")
    if sw is not None and not isinstance(sw, str):
        probs.append('"software" must be null or a string such as "mathematica"')
    return data, probs


def exams(intake):
    return [f for f in intake["files"] if isinstance(f, dict) and f.get("role") == "exam"]


# ------------------------------------------------------------------------------ state
def course_state(key, c, cdir):
    """List of steps: dict(step, status: done|todo|n/a, detail)."""
    steps = []

    def add(step, ok, detail="", na=False):
        steps.append({"step": step, "status": "n/a" if na else ("done" if ok else "todo"), "detail": detail})

    mats = files_under(cdir / "materials")
    add("materials", bool(mats), f"{len(mats)} files in {rel(cdir / 'materials')}/")
    intake, probs = load_intake(key, cdir)
    intake_ok = intake is not None and not probs
    add("intake", intake_ok, "; ".join(probs[:3]) if probs else "intake.json ok")
    if intake is None:
        intake = {"files": []}
    hold = files_under(cdir / "holdout")
    none = bool(intake.get("holdout_none"))
    add("holdout", bool(hold) or none,
        "none held out (user's choice)" if none and not hold else f"{len(hold)} files in holdout/")
    ex = [e for e in exams(intake) if not e.get("holdout")]
    missing = [e.get("exam_id") for e in ex
               if not ((cdir / "bank" / f"{e.get('exam_id')}.md").is_file()
                       and (cdir / "bank" / f"{e.get('exam_id')}.index.tsv").is_file())]
    add("bank", not missing,
        f"{len(ex) - len(missing)}/{len(ex)} past exams transcribed" + (f"; to do: {' '.join(missing)}" if missing else "")
        if ex else "no past exams in intake.json: the blueprint rests on syllabus and seeds alone",
        na=not ex and intake_ok)
    add("syllabus", (cdir / "syllabus.md").is_file(), "syllabus.md")
    roles = {f.get("role") for f in intake["files"] if isinstance(f, dict)}
    sheet = (cdir / "formula_sheet.md").is_file() or (cdir / "equation_sheet.md").is_file()
    add("formula_sheet", sheet, "formula_sheet.md", na="formula_sheet" not in roles and not sheet)
    sw = str(intake.get("software") or "").lower()
    tk = (cdir / "mathematica_toolkit.md").is_file()
    add("toolkit", tk, "mathematica_toolkit.md", na="mathematica" not in sw and not tk)
    seeds = (cdir / "seeds.md").is_file()
    add("seeds", seeds, "seeds.md", na=not ({"notes", "exercises"} & roles) and not seeds)
    bp_ok, bp_detail, bp = False, "blueprint.md + blueprint.json + bank/index.tsv", None
    if (cdir / "blueprint.json").is_file():
        try:
            sys.path.insert(0, str(TOOLS))
            import ledger
            bp = ledger.load_blueprint(ledger.Course(key, c["dir"], c["name"], parse_date(c["exam_date"])))
            bp_ok = (cdir / "blueprint.md").is_file() and (cdir / "bank" / "index.tsv").is_file()
            bp_detail = f"{len(bp['archetypes'])} archetypes" + ("" if bp_ok else "; blueprint.md or bank/index.tsv missing")
        except Exception as e:  # ledger.DataError and anything unexpected
            msgs = getattr(e, "msgs", None)
            bp_detail = "blueprint.json invalid: " + ("; ".join(msgs[:3]) if msgs else str(e))
    add("blueprint", bp_ok, bp_detail)
    note = None
    if (cdir / "blueprint.json").is_file():
        try:
            raw = json.loads((cdir / "blueprint.json").read_text(encoding="utf-8"))
            note = raw.get("pass_grade_note")
            pg = raw.get("pass_grade", 5.5)
        except ValueError:
            pg = None
    add("pass_mark", bool(note), f"pass_grade {pg}: {note}" if note else "not confirmed with the user yet")
    return steps


def next_step(steps):
    return next((s for s in steps if s["status"] == "todo"), None)


# ------------------------------------------------------------------------------ commands
def cmd_add(a):
    cfg = read_config(required=False)
    key = a.key.upper()
    if not KEY_RE.match(key):
        die(f"KEY must be 2-8 capital letters or digits, starting with a letter (e.g. MECH, LA2); got {a.key!r}")
    if key in cfg["courses"]:
        die(f"course {key} already exists")
    d = a.dir or key
    if d.startswith("/") or ".." in Path(d).parts or d.split("/")[0] in RESERVED_DIRS or d.startswith("."):
        die(f"--dir must be a new folder name inside the project, not {d!r}")
    if any(c["dir"] == d for c in cfg["courses"].values()):
        die(f"folder {d!r} is already used by another course")
    ed = parse_date(a.exam_date)
    if ed is None:
        die(f"--exam-date must be YYYY-MM-DD, got {a.exam_date!r}")
    if not a.name.strip():
        die("--name must not be empty")
    cdir = ROOT / d
    for sub in ("materials", "holdout"):
        (cdir / sub).mkdir(parents=True, exist_ok=True)
    cfg["courses"][key] = {"dir": d, "name": a.name.strip(), "exam_date": ed.isoformat()}
    write_json(CONFIG, cfg)
    print(f"added {key}: {a.name.strip()}, final {ed.isoformat()} ({ed.strftime('%a')}), folder {d}/")
    print(f"  put the course files in {d}/materials/ (any sub-folders)")


def cmd_study_days(a):
    cfg = read_config(required=False)
    days = []
    for s in a.days:
        for part in s.replace(",", " ").split():
            w = part[:3].capitalize()
            if w not in WEEKDAYS:
                die(f"{part!r} is not a weekday (Mon..Sun)")
            if w not in days:
                days.append(w)
    if not days:
        die("give at least one study day")
    cfg["study_days"] = sorted(days, key=WEEKDAYS.index)
    write_json(CONFIG, cfg)
    print("study days: " + " ".join(cfg["study_days"]))


def cmd_list(a):
    cfg = read_config(required=False)
    if not cfg["courses"]:
        print("no courses yet")
        return
    print("study days: " + " ".join(cfg["study_days"]))
    for key, c in sorted(cfg["courses"].items(), key=lambda kv: kv[1]["exam_date"]):
        cdir = ROOT / c["dir"]
        steps = course_state(key, c, cdir)
        done = sum(s["status"] == "done" for s in steps)
        todo = sum(s["status"] == "todo" for s in steps)
        nxt = next_step(steps)
        ed = parse_date(c["exam_date"])
        left = (ed - today()).days if ed else "?"
        sets = len([p for p in (cdir / "sets").glob("*/set.json")]) if (cdir / "sets").is_dir() else 0
        print(f"{key:<6} {c['name']}  final {c['exam_date']} ({left} days)  folder {c['dir']}/")
        print(f"       set-up {done}/{done + todo} steps" + (f", next: {nxt['step']}" if nxt else ", complete")
              + f"; {sets} sets written")


def cmd_state(a):
    cfg = read_config()
    key, c, cdir = course_of(cfg, a.key)
    steps = course_state(key, c, cdir)
    nxt = next_step(steps)
    if a.json:
        print(json.dumps({"course": key, "dir": c["dir"], "steps": steps, "next": nxt and nxt["step"]}, indent=2))
        return
    print(f"{key}: {c['name']} (folder {c['dir']}/, final {c['exam_date']})")
    for s in steps:
        mark = {"done": "[x]", "todo": "[ ]", "n/a": "[-]"}[s["status"]]
        print(f"  {mark} {s['step']:<14} {s['detail']}")
    print(f"next: {nxt['step']}" if nxt else "set-up complete")


def cmd_inventory(a):
    cfg = read_config()
    key, c, cdir = course_of(cfg, a.key)
    mats = files_under(cdir / "materials")
    if not mats:
        print(f"{rel(cdir / 'materials')}/ is empty")
    total = 0
    for p in mats:
        size = p.stat().st_size
        total += size
        pages = pdf_pages(p)
        extra = f", {pages} pages" if pages else ""
        print(f"  {p.relative_to(cdir)}  ({human(size)}{extra})")
    if mats:
        print(f"{len(mats)} files, {human(total)}")
    hold = files_under(cdir / "holdout")
    print(f"holdout/: {len(hold)} files" + (" (names not listed: unseen on purpose)" if hold else ""))


def cmd_check_intake(a):
    cfg = read_config()
    key, c, cdir = course_of(cfg, a.key)
    data, probs = load_intake(key, cdir)
    if probs:
        for p in probs:
            print(p)
        sys.exit(1)
    listed = {f["path"] for f in data["files"]}
    unlisted = [str(p.relative_to(cdir)) for p in files_under(cdir / "materials") if str(p.relative_to(cdir)) not in listed]
    ex = exams(data)
    print(f"OK {key}: {len(data['files'])} files, {len(ex)} past exams, "
          f"{sum(1 for e in ex if e.get('answers'))} with answers")
    for u in unlisted:
        print(f"  not in intake.json: {u}")


def cmd_holdout(a):
    cfg = read_config()
    key, c, cdir = course_of(cfg, a.key)
    hdir = cdir / "holdout"
    hdir.mkdir(parents=True, exist_ok=True)
    ipath = cdir / "intake.json"
    intake = json.loads(ipath.read_text(encoding="utf-8")) if ipath.exists() else None
    if a.none:
        if files_under(hdir):
            die("holdout/ already has files; move them back to materials/ first if you want none")
        if intake is None:
            die("write intake.json first")
        intake["holdout_none"] = True
        write_json(ipath, intake)
        print(f"{key}: no exam held out")
        return
    if not a.files:
        die("name the file(s) to hold out, or pass --none")
    if files_under(hdir) and not a.replace:
        die("holdout/ already has files (pass --replace to add more)")
    moved = []
    for f in a.files:
        src = resolve_material(cdir, f)
        if src is None or (cdir / "materials") not in src.parents:
            die(f"not a file in {rel(cdir / 'materials')}/: {f}")
        dst = hdir / src.name
        if dst.exists():
            die(f"holdout/{src.name} already exists")
        old_rel = str(src.relative_to(cdir))
        shutil.move(str(src), str(dst))
        moved.append((old_rel, str(dst.relative_to(cdir))))
    if intake is not None:
        mp = dict(moved)
        for f in intake.get("files", []):
            if isinstance(f, dict):
                if f.get("path") in mp:
                    f["path"] = mp[f["path"]]
                    f["holdout"] = True
                if f.get("answers") in mp:
                    f["answers"] = mp[f["answers"]]
        intake.pop("holdout_none", None)
        write_json(ipath, intake)
    for old, new in moved:
        print(f"moved {old} -> {new}")
    print("From now on only /mock COURSE holdout opens these files.")


def cmd_pass_mark(a):
    cfg = read_config()
    key, c, cdir = course_of(cfg, a.key)
    path = cdir / "blueprint.json"
    if not path.exists():
        die(f"{rel(path)} does not exist yet; set the pass mark after the blueprint is written")
    try:
        g = float(a.grade)
    except ValueError:
        die(f"GRADE must be a number, got {a.grade!r}")
    if not 0 < g <= 10:
        die("GRADE must be between 0 and 10")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["pass_grade"] = round(g, 3)
    data["pass_grade_note"] = a.why.strip()
    write_json(path, data)
    print(f"{key}: the final must reach {data['pass_grade']} ({data['pass_grade_note']})")


def cmd_archive(a):
    cfg = read_config()
    key, c, cdir = course_of(cfg, a.key)
    label = a.label or today().strftime("%Y-%m")
    if "/" in label or label.startswith(".") or not label.strip():
        die(f"--label must be a plain folder name, got {label!r}")
    dest = ROOT / "archive" / label / c["dir"]
    if dest.exists():
        die(f"{rel(dest)} already exists")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if cdir.exists():
        shutil.move(str(cdir), str(dest))
    del cfg["courses"][key]
    arch = ROOT / "archive" / label / "config.json"
    old = json.loads(arch.read_text(encoding="utf-8")) if arch.exists() else {"courses": {}, "study_days": cfg["study_days"]}
    old["courses"][key] = c
    write_json(arch, old)
    write_json(CONFIG, cfg)
    print(f"archived {key}: {rel(cdir)}/ -> {rel(dest)}/ (its config entry kept in {rel(arch)})")
    left = ", ".join(cfg["courses"]) or "none"
    print(f"courses left: {left}. Update courses.md and run tools/build_report.py.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add"); p.add_argument("key"); p.add_argument("--name", required=True)
    p.add_argument("--exam-date", required=True); p.add_argument("--dir")
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("study-days"); p.add_argument("days", nargs="+"); p.set_defaults(fn=cmd_study_days)
    p = sub.add_parser("list"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("state"); p.add_argument("key"); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_state)
    p = sub.add_parser("inventory"); p.add_argument("key"); p.set_defaults(fn=cmd_inventory)
    p = sub.add_parser("check-intake"); p.add_argument("key"); p.set_defaults(fn=cmd_check_intake)
    p = sub.add_parser("holdout"); p.add_argument("key"); p.add_argument("files", nargs="*")
    p.add_argument("--none", action="store_true"); p.add_argument("--replace", action="store_true")
    p.set_defaults(fn=cmd_holdout)
    p = sub.add_parser("pass-mark"); p.add_argument("key"); p.add_argument("grade")
    p.add_argument("--why", required=True); p.set_defaults(fn=cmd_pass_mark)
    p = sub.add_parser("archive"); p.add_argument("key"); p.add_argument("--label")
    p.set_defaults(fn=cmd_archive)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
