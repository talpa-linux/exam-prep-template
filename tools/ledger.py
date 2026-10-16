#!/usr/bin/env python3
"""Ledger, mastery and next-set planner for the exam-prep loop.

Python 3 standard library only, no model calls.  The project root is the parent of
the directory this file lives in; the scripts work from any working directory.

  ledger.py newid    COURSE diagnostic|train|full|holdout
  ledger.py checkset COURSE SET
  ledger.py record   COURSE SET
  ledger.py mastery  COURSE [--json]
  ledger.py next     COURSE --kind diagnostic|train|full [--minutes N] [--date YYYY-MM-DD]
  ledger.py status   [--json]

Results go to stdout, problems to stderr (exit 1 for bad data, 2 for bad usage).
Environment variable PREP_TODAY=YYYY-MM-DD overrides today's date (used by the tests).
All mastery arithmetic is exact (fractions), so thresholds such as 0.80 are not
subject to floating-point surprises.
"""
import argparse
import json
import math
import os
import re
import sys
from datetime import date, timedelta
from fractions import Fraction

from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent

# --------------------------------------------------------------------------- vocab

ERROR_TAGS = {
    "concept": "wrong or missing idea",
    "method": "wrong approach, or did not know how to start",
    "setup": "right method, wrong set-up (limits, parametrisation, boundary conditions, coordinates)",
    "algebra": "slip in manipulation",
    "sign": "sign error",
    "arithmetic": "numeric slip",
    "notation": "notation that cost points",
    "justification": "result right, required motivation missing or insufficient",
    "misread": "answered a different question than the one asked",
    "incomplete": "stopped before the end / ran out of time",
}
STATUSES = ("graded", "blank", "skipped_not_covered")
CONFIDENCES = ("high", "medium", "low")
KIND_LETTER = {"diagnostic": "D", "train": "T", "full": "F", "holdout": "H"}
LETTER_KIND = {v: k for k, v in KIND_LETTER.items()}
FORMATS = ("open", "mc", "mathematica-mc", "proof")
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

F = Fraction
LEVEL_C = {1: F(65, 100), 2: F(1), 3: F(11, 10)}   # evidence factor per level
LEVEL_MIN = {1: F(7, 10), 2: F(1), 3: F(13, 10)}   # minutes factor per level
MAX_TAKEAWAY_WORDS = 25
SLOW_FACTOR = F(3, 2)                              # "too slow": more than 1.5 x the budgeted minutes
DEFAULT_TRAIN_MINUTES = 90
RETENTION_DAYS = 5

# hints asked for before or during an attempt (tools/hints.py writes submissions/<SET>/hints.json)
HINT_RUNGS = {1: "nudge", 2: "method", 3: "set-up"}
HINT_GAPS = ("concept", "method", "setup")
HINT_WORDS = {"cue": 25, "learned": 30, "tried": 40, "said": 50}
HELD_LEVEL_F = F(4, 5)                             # score_with_help fraction that holds the level after a hint

MAX_PROBLEMS_SHOWN = 40


# --------------------------------------------------------------------------- errors

class DataError(Exception):
    """Bad or missing input data.  Carries one or more printable messages."""

    def __init__(self, msgs):
        if isinstance(msgs, str):
            msgs = [msgs]
        self.msgs = list(msgs)
        super().__init__("; ".join(self.msgs))


class MissingFile(DataError):
    pass


def rel(path):
    try:
        return os.path.relpath(str(path), str(ROOT))
    except ValueError:
        return str(path)


class Problems:
    """Collects validation messages for one file."""

    def __init__(self, path):
        self.path = path
        self.msgs = []

    def add(self, where, msg):
        head = rel(self.path)
        self.msgs.append(f"{head}: {where}: {msg}" if where else f"{head}: {msg}")

    def __bool__(self):
        return bool(self.msgs)

    def raise_if_any(self):
        if self.msgs:
            raise DataError(self.msgs)


def fail(msgs, code=1):
    if isinstance(msgs, str):
        msgs = [msgs]
    shown = msgs[:MAX_PROBLEMS_SHOWN]
    for m in shown:
        print(f"ERROR {m}", file=sys.stderr)
    if len(msgs) > len(shown):
        print(f"ERROR ... and {len(msgs) - len(shown)} more problems", file=sys.stderr)
    return code


# --------------------------------------------------------------------------- helpers

def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def fr(x):
    """Exact decimal value of a JSON number (2.3 -> 23/10, not the binary float)."""
    return Fraction(str(x))


def row_assisted(r):
    """True if the ledger row was written with outside help (old rows lack the field: False)."""
    return r.get("assisted") is True


def row_minutes(r):
    """Minutes the student spent on the item, or None (absent, null or not a positive number)."""
    m = r.get("minutes")
    return m if is_num(m) and m > 0 else None


def row_budget(r):
    """The item's budgeted minutes from set.json, or None (old rows, or no budget in set.json)."""
    m = r.get("budget_minutes")
    return m if is_num(m) and m > 0 else None


def row_slow(r):
    """True if the item took more than 1.5 x its budget (needs both numbers)."""
    m, b = row_minutes(r), row_budget(r)
    return m is not None and b is not None and fr(m) > SLOW_FACTOR * fr(b)


def row_hint(r):
    """The logged hint joined into the row ({rung, gap, cue, learned}), or None."""
    h = r.get("hint")
    return h if isinstance(h, dict) else None


def row_help_f(r):
    """score_with_help / max for an assisted row, or None."""
    s = r.get("score_with_help")
    return fr(s) / fr(r["max"]) if row_assisted(r) and is_num(s) else None


def jf(x, nd=3):
    """Fraction -> float for JSON output."""
    return round(float(x), nd)


def jm(x):
    """Minutes for JSON/text output: integer if integral, else one decimal."""
    v = round(float(x), 1)
    return int(v) if v == int(v) else v


def fmt_num(x):
    if isinstance(x, Fraction):
        x = float(x)
    if isinstance(x, float) and x == int(x):
        return str(int(x))
    return str(x)


def pct_str(x, nd=0):
    return f"{float(x) * 100:.{nd}f}".rstrip("0").rstrip(".") if nd else f"{float(x) * 100:.0f}"


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(s):
    if not isinstance(s, str) or not DATE_RE.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def today():
    env = os.environ.get("PREP_TODAY")
    if env:
        d = parse_date(env)
        if d is None:
            raise DataError(f"PREP_TODAY={env!r} is not a YYYY-MM-DD date")
        return d
    return date.today()


def load_json(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise MissingFile(f"{rel(path)}: file not found")
    except (OSError, UnicodeDecodeError) as e:
        raise DataError(f"{rel(path)}: cannot read file: {e}")

    def bad_const(c):
        raise ValueError(f"non-standard number {c}")

    try:
        return json.loads(text, parse_constant=bad_const)
    except json.JSONDecodeError as e:
        raise DataError(f"{rel(path)}: invalid JSON at line {e.lineno} column {e.colno}: {e.msg}")
    except ValueError as e:
        raise DataError(f"{rel(path)}: invalid JSON: {e}")


def dumps_compact(obj):
    """Valid JSON, compact, with one list element per line for lists of objects."""
    def one(v):
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))

    if isinstance(obj, dict):
        parts = []
        for k, v in obj.items():
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                parts.append(f"{one(k)}:[\n" + ",\n".join(one(x) for x in v) + "\n]")
            else:
                parts.append(f"{one(k)}:{one(v)}")
        return "{" + ",\n".join(parts) + "}"
    return one(obj)


# --------------------------------------------------------------------------- config

class Course:
    def __init__(self, key, dirname, name, exam_date):
        self.key = key
        self.dirname = dirname
        self.path = ROOT / dirname
        self.name = name
        self.exam_date = exam_date

    def __repr__(self):
        return f"Course({self.key})"


class Config:
    def __init__(self, courses, study_weekdays):
        self.courses = courses              # dict key -> Course, in file order
        self.study_weekdays = study_weekdays  # set of ints, Monday = 0


def load_config():
    path = TOOLS / "config.json"
    if not path.exists():
        raise DataError("tools/config.json not found: no courses are set up yet. "
                        "Run /start in Claude, or tools/course.py add (see SETUP.md).")
    data = load_json(path)
    P = Problems(path)
    courses = {}
    if not isinstance(data, dict) or not isinstance(data.get("courses"), dict):
        P.add("", '"courses" must be an object (empty until the first course is added)')
    else:
        for key, c in data["courses"].items():
            if not isinstance(c, dict):
                P.add(f"courses.{key}", "must be an object")
                continue
            d, n, e = c.get("dir"), c.get("name"), parse_date(c.get("exam_date"))
            if not isinstance(d, str) or not d or d.startswith("/") or ".." in Path(d).parts:
                P.add(f"courses.{key}.dir", "must be a directory name relative to the project root")
            if not isinstance(n, str) or not n:
                P.add(f"courses.{key}.name", "must be a non-empty string")
            if e is None:
                P.add(f"courses.{key}.exam_date", "must be a YYYY-MM-DD date")
            if isinstance(d, str) and isinstance(n, str) and e is not None:
                courses[key] = Course(key, d, n, e)
    weekdays = set()
    sd = data.get("study_days") if isinstance(data, dict) else None
    if not isinstance(sd, list):
        P.add("", '"study_days" must be a list such as ["Tue", "Wed", "Thu"]')
    else:
        for s in sd:
            names = [w.lower() for w in WEEKDAYS]
            if isinstance(s, str) and s[:3].lower() in names:
                weekdays.add(names.index(s[:3].lower()))
            else:
                P.add("study_days", f"{s!r} is not a weekday name (Mon..Sun)")
    P.raise_if_any()
    return Config(courses, weekdays)


def get_course(cfg, key):
    k = str(key).upper()
    if k not in cfg.courses:
        raise DataError(f"unknown course {key!r}; configured courses: {', '.join(cfg.courses)}")
    return cfg.courses[k]


# --------------------------------------------------------------------------- blueprint

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def load_blueprint(course):
    path = course.path / "blueprint.json"
    try:
        data = load_json(path)
    except MissingFile:
        raise MissingFile(f"{rel(path)}: file not found (no blueprint written for {course.key} yet)")
    P = Problems(path)
    if not isinstance(data, dict):
        P.add("", "top level must be a JSON object")
        P.raise_if_any()
    if "course" in data and data["course"] != course.key:
        P.add("course", f'is {data["course"]!r}, expected "{course.key}"')
    for fld in ("total_points", "duration_min"):
        if not is_num(data.get(fld)) or data[fld] <= 0:
            P.add(fld, f"must be a number > 0, got {data.get(fld)!r}")
    divisor = data.get("grade_divisor", 10)
    if not is_num(divisor) or divisor <= 0:
        P.add("grade_divisor", f"must be a number > 0, got {divisor!r}")
    pass_grade = data.get("pass_grade", 5.5)
    if not is_num(pass_grade):
        P.add("pass_grade", f"must be a number, got {pass_grade!r}")
    arch = data.get("archetypes")
    out = []
    if not isinstance(arch, list) or not arch:
        P.add("archetypes", "must be a non-empty list")
        arch = []
    seen = set()
    for i, a in enumerate(arch):
        where = f"archetypes[{i}]"
        if not isinstance(a, dict):
            P.add(where, "must be an object")
            continue
        aid = a.get("id")
        if not isinstance(aid, str) or not ID_RE.match(aid):
            P.add(where, f'"id" must be a string of letters, digits, ".", "_" or "-", got {aid!r}')
            continue
        where = f'archetypes[{i}] ("{aid}")'
        if aid in seen:
            P.add(where, "duplicate archetype id")
        seen.add(aid)
        name = a.get("name")
        if not isinstance(name, str) or not name.strip():
            P.add(where, '"name" must be a non-empty string')
        group = a.get("group", "Other")
        if not isinstance(group, str) or not group.strip():
            P.add(where, '"group" must be a non-empty string')
        for fld, lo_ok in (("weight", True), ("typical_points", True), ("typical_minutes", False)):
            v = a.get(fld)
            if not is_num(v) or v < 0 or (not lo_ok and v == 0):
                P.add(where, f'"{fld}" must be a number {">= 0" if lo_ok else "> 0"}, got {v!r}')
        fmt = a.get("format", "open")
        if fmt not in FORMATS:
            P.add(where, f'"format" must be one of {", ".join(FORMATS)}, got {fmt!r}')
        cf = a.get("covered_from")
        cfd = None
        if cf is not None:
            cfd = parse_date(cf)
            if cfd is None:
                P.add(where, f'"covered_from" must be YYYY-MM-DD or absent, got {cf!r}')
        out.append({"id": aid, "name": name, "group": group, "raw_weight": a.get("weight"),
                    "typical_points": a.get("typical_points"), "typical_minutes": a.get("typical_minutes"),
                    "format": fmt, "covered_from": cfd})
    P.raise_if_any()
    total_w = sum(fr(a["raw_weight"]) for a in out)
    if total_w <= 0:
        P.add("archetypes", "weights sum to 0; at least one archetype needs weight > 0")
        P.raise_if_any()
    for a in out:
        a["w"] = fr(a["raw_weight"]) / total_w
        a["typical_minutes"] = fr(a["typical_minutes"])
        a["typical_points"] = fr(a["typical_points"])
    return {
        "course": course.key,
        "duration_min": data["duration_min"],
        "total_points": data["total_points"],
        "grade_divisor": divisor,
        "pass_grade": pass_grade,
        "archetypes": out,
        "by_id": {a["id"]: a for a in out},
        "full_exam_structure": data.get("full_exam_structure"),
    }


def try_blueprint(course):
    """(blueprint or None, problem message or None) -- for callers that can live without it."""
    try:
        return load_blueprint(course), None
    except DataError as e:
        return None, "; ".join(e.msgs)


# --------------------------------------------------------------------------- sets

def set_id_re(key):
    return re.compile(r"^" + re.escape(key) + r"-([DTFH])(\d{2,})$")


def check_set_arg(course, set_id):
    sid = str(set_id).upper()
    if not set_id_re(course.key).match(sid):
        raise DataError(f'bad set id {set_id!r}: expected {course.key}-<D|T|F|H><NN>, e.g. {course.key}-T03')
    return sid


def list_set_ids(course):
    d = course.path / "sets"
    rx = set_id_re(course.key)
    ids = []
    if d.is_dir():
        for p in d.iterdir():
            if p.is_dir() and rx.match(p.name):
                ids.append(p.name)
    return sorted(ids, key=lambda s: (rx.match(s).group(1), int(rx.match(s).group(2))))


def next_set_id(course, kind):
    letter = KIND_LETTER[kind]
    rx = set_id_re(course.key)
    names = list_set_ids(course)
    fb = course.path / "feedback"
    if fb.is_dir():
        names += [p.stem for p in fb.glob("*.json")]
    try:
        names += [r.get("set", "") for r in read_ledger(course)]
    except DataError:
        pass
    nums = [int(m.group(2)) for m in (rx.match(n) for n in names) if m and m.group(1) == letter]
    return f"{course.key}-{letter}{max(nums, default=0) + 1:02d}"


def core_set_problems(course, set_id, data, arch_ids, where):
    """Checks shared by `checkset` and `record`.  Returns a list of messages."""
    P = []

    def add(label, msg):
        P.append(f"{where}: {label + ': ' if label else ''}{msg}")

    if not isinstance(data, dict):
        add("", "top level must be a JSON object")
        return P
    if data.get("course") != course.key:
        add("course", f'is {data.get("course")!r}, expected "{course.key}"')
    if data.get("set") != set_id:
        add("set", f'is {data.get("set")!r}, expected "{set_id}"')
    if data.get("kind") not in KIND_LETTER:
        add("kind", f'{data.get("kind")!r} is not one of {", ".join(KIND_LETTER)}')
    items = data.get("items")
    if not isinstance(items, list) or not items:
        add("items", "must be a non-empty list")
        return P
    positions = {}
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            add(f"items[{idx}]", "must be an object")
            continue
        iid = it.get("item")
        if not isinstance(iid, str) or not iid.strip():
            add(f"items[{idx}]", f'"item" must be a non-empty string, got {iid!r}')
            label = f"items[{idx}]"
        else:
            positions.setdefault(iid, []).append(idx)
            label = f'item "{iid}"'
        lv = it.get("level")
        if type(lv) is not int or lv not in (1, 2, 3):
            add(label, f"level {lv!r} is not the integer 1, 2 or 3")
        fm = it.get("format")
        if fm not in FORMATS:
            add(label, f'format {fm!r} is not one of {", ".join(FORMATS)}')
        ar = it.get("archetype")
        if not isinstance(ar, str) or not ar:
            add(label, f'"archetype" must be a string, got {ar!r}')
        elif arch_ids is not None and ar not in arch_ids:
            add(label, f'archetype "{ar}" does not exist in blueprint.json')
        mx = it.get("max")
        if not is_num(mx) or mx <= 0:
            add(label, f'"max" must be a number > 0, got {mx!r}')
    for iid, idxs in positions.items():
        if len(idxs) > 1:
            add(f'item "{iid}"', "item id is not unique: appears " + " and ".join(f"items[{i}]" for i in idxs))
    return P


def blueprint_ids_lenient(course):
    """Archetype ids from blueprint.json, or (None, problem) if it is missing/unparseable."""
    path = course.path / "blueprint.json"
    try:
        data = load_json(path)
    except DataError as e:
        return None, f"{'; '.join(e.msgs)} -- archetype check skipped"
    arch = data.get("archetypes") if isinstance(data, dict) else None
    if not isinstance(arch, list):
        return None, f"{rel(path)}: no \"archetypes\" list -- archetype check skipped"
    return {a.get("id") for a in arch if isinstance(a, dict) and isinstance(a.get("id"), str)}, None


def checkset(course, set_id):
    """Return (problems, n_items, points)."""
    sdir = course.path / "sets" / set_id
    path = sdir / "set.json"
    where = rel(path)
    try:
        data = load_json(path)
    except DataError as e:
        return e.msgs, 0, 0
    arch_ids, bp_problem = blueprint_ids_lenient(course)
    P = core_set_problems(course, set_id, data, arch_ids, where)
    if bp_problem:
        P.append(bp_problem)
    items = data.get("items") if isinstance(data, dict) else None
    items = items if isinstance(items, list) else []
    total = F(0)
    for it in items:
        if not isinstance(it, dict):
            continue
        label = f'item "{it["item"]}"' if isinstance(it.get("item"), str) else None
        if is_num(it.get("max")):
            total += fr(it["max"])
        if it.get("format") in ("mc", "mathematica-mc"):
            a = it.get("mc_answer")
            if not (isinstance(a, str) and len(a) == 1 and a.isascii() and a.isalpha()):
                P.append(f"{where}: {label or 'item ?'}: format {it['format']} needs mc_answer to be a "
                         f"single letter A-Z, got {a!r}")
    tp = data.get("total_points") if isinstance(data, dict) else None
    if not is_num(tp):
        P.append(f"{where}: total_points must be a number, got {tp!r}")
    elif fr(tp) != total:
        P.append(f"{where}: items' max values sum to {fmt_num(total)} but total_points is {fmt_num(tp)}")
    for fname in ("exam.pdf", "key.pdf"):
        if not (sdir / fname).is_file():
            P.append(f"{rel(sdir / fname)}: file not found (exam.pdf and key.pdf must sit next to set.json)")
    return P, len(items), total


def load_set(course, set_id, arch_ids=None):
    """Strict load of set.json for `record`."""
    path = course.path / "sets" / set_id / "set.json"
    data = load_json(path)
    P = core_set_problems(course, set_id, data, arch_ids, rel(path))
    if P:
        raise DataError(P)
    cr = data.get("created")
    if cr is not None and parse_date(cr) is None:
        raise DataError(f'{rel(path)}: created: {cr!r} is not a YYYY-MM-DD date')
    return data


def sets_lenient(course, warnings):
    """All parseable set.json files (for variation strings); problems become warnings."""
    out = {}
    for sid in list_set_ids(course):
        path = course.path / "sets" / sid / "set.json"
        if not path.exists():
            continue
        try:
            d = load_json(path)
        except DataError as e:
            warnings.append(f"skipped {e.msgs[0]}")
            continue
        if isinstance(d, dict) and isinstance(d.get("items"), list):
            out[sid] = d
    return dict(sorted(out.items(), key=lambda kv: (str(kv[1].get("created") or ""), kv[0])))


# --------------------------------------------------------------------------- feedback / record

def count_words(text):
    """Words in a takeaway; a $...$ stretch counts as one word."""
    t = re.sub(r"\$[^$]*\$", "M", text)
    return len(t.split())


def hints_path(course, set_id):
    return course.path / "submissions" / set_id / "hints.json"


def is_rung(v):
    return type(v) is int and v in HINT_RUNGS


def hint_text_problem(name, v, required=True):
    """Problem with one text field of a hint entry, or None."""
    if v is None and not required:
        return None
    if not isinstance(v, str) or not v.strip():
        return f"{name} must be a non-empty string, got {v!r}"
    if count_words(v) > HINT_WORDS[name]:
        return f"{name} has {count_words(v)} words; the limit is {HINT_WORDS[name]}"
    return None


def load_hints(course, set_id, set_items):
    """Strict load of submissions/<SET>/hints.json.  Returns ({item: entry}, problems); no file = no hints.

    The file is written only by tools/hints.py, so any problem here means it was edited by hand."""
    path = hints_path(course, set_id)
    if not path.exists():
        return {}, []
    try:
        data = load_json(path)
    except DataError as e:
        return {}, e.msgs
    P = Problems(path)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        P.add("", 'must be an object with an "items" list')
        return {}, P.msgs
    if data.get("course") != course.key:
        P.add("course", f'is {data.get("course")!r}, expected "{course.key}"')
    if data.get("set") != set_id:
        P.add("set", f'is {data.get("set")!r}, expected "{set_id}"')
    out = {}
    for idx, h in enumerate(data["items"]):
        iid = h.get("item") if isinstance(h, dict) else None
        label = f'item "{iid}"' if isinstance(iid, str) else f"items[{idx}]"
        if not isinstance(iid, str) or iid not in set_items:
            P.add(label, f"is not an item of {set_id}")
            continue
        if iid in out:
            P.add(label, "is logged twice")
            continue
        if not is_rung(h.get("rung")):
            P.add(label, f"rung must be 1, 2 or 3, got {h.get('rung')!r}")
        if not isinstance(h.get("gap"), str) or h.get("gap") not in HINT_GAPS:
            P.add(label, f"gap must be one of {', '.join(HINT_GAPS)}, got {h.get('gap')!r}")
        for name in ("cue", "learned"):
            m = hint_text_problem(name, h.get(name))
            if m:
                P.add(label, m)
        m = hint_text_problem("tried", h.get("tried"), required=False)
        if m:
            P.add(label, m)
        given = h.get("given")
        if not isinstance(given, list) or not given:
            P.add(label, '"given" must be a non-empty list of the hints given')
        else:
            for g in given:
                if not isinstance(g, dict) or not is_rung(g.get("rung")) or hint_text_problem("said", g.get("said")):
                    P.add(label, f"bad entry in given: {g!r}")
                    break
        out[iid] = h
    return out, P.msgs


def build_rows(course, set_id, setdata, fb, where, hints=None):
    """Validate feedback against the set (and its hint log) and return (rows, problems)."""
    P = []
    hints = hints or {}

    def add(label, msg):
        P.append(f"{where}: {label + ': ' if label else ''}{msg}")

    if not isinstance(fb, dict):
        return [], [f"{where}: top level must be a JSON object"]
    if fb.get("course") != course.key:
        add("course", f'is {fb.get("course")!r}, expected "{course.key}"')
    if fb.get("set") != set_id:
        add("set", f'is {fb.get("set")!r}, expected "{set_id}"')
    gd = parse_date(fb.get("graded_on"))
    if gd is None:
        add("graded_on", f'must be a YYYY-MM-DD date, got {fb.get("graded_on")!r}')
    ts = fb.get("time_spent_min")
    if ts is not None and (not is_num(ts) or ts < 0):
        add("time_spent_min", f"must be null or a number >= 0, got {ts!r}")
    items = fb.get("items")
    if not isinstance(items, list):
        add("items", "must be a list")
        return [], P

    by_id = {}
    for idx, it in enumerate(items):
        iid = it.get("item") if isinstance(it, dict) else None
        if not isinstance(iid, str):
            add(f"items[{idx}]", f'"item" must be a string naming a set item (e.g. "1.1"), got {iid!r}')
            continue
        by_id.setdefault(iid, []).append(idx)

    set_items = {it["item"]: it for it in setdata["items"]}
    for iid, idxs in by_id.items():
        if iid not in set_items:
            add(f'item "{iid}"', f"is not an item of {set_id} (set.json has: {', '.join(set_items)})")
        elif len(idxs) > 1:
            add(f'item "{iid}"', "appears " + " and ".join(f"items[{i}]" for i in idxs) + "; each item must appear exactly once")
    for iid in set_items:
        if iid not in by_id:
            add(f'item "{iid}"', 'is in set.json but missing from feedback (use status "blank" or '
                                 '"skipped_not_covered" for work that was not graded)')

    rows = []
    for sit in setdata["items"]:
        iid = sit["item"]
        idxs = by_id.get(iid, [])
        if len(idxs) != 1 or iid not in set_items:
            continue
        it = items[idxs[0]]
        label = f'item "{iid}"'
        score, mx, status = it.get("score"), it.get("max"), it.get("status")
        ok = True
        if status not in STATUSES:
            add(label, f'status {status!r} is not one of {", ".join(STATUSES)}')
            ok = False
        if not is_num(score):
            add(label, f"score must be a number, got {score!r}")
            ok = False
        if not is_num(mx):
            add(label, f"max must be a number, got {mx!r}")
            ok = False
        elif fr(mx) != fr(sit["max"]):
            add(label, f"max {fmt_num(mx)} differs from the set's max {fmt_num(sit['max'])}")
            ok = False
        if ok and (fr(score) < 0 or fr(score) > fr(mx)):
            add(label, f"score {fmt_num(score)} is outside 0..{fmt_num(mx)}")
            ok = False
        if ok and status in ("blank", "skipped_not_covered") and fr(score) != 0:
            add(label, f'status "{status}" needs score 0, got {fmt_num(score)}')
        errs = it.get("errors", [])
        if not isinstance(errs, list):
            add(label, f'errors must be a list of tags, got {errs!r}')
            errs = []
        else:
            for t in errs:
                if not isinstance(t, str) or t not in ERROR_TAGS:
                    add(label, f"unknown error tag {t!r}; allowed: {', '.join(ERROR_TAGS)}")
        assisted = it.get("assisted", False)
        if type(assisted) is not bool:
            add(label, f"assisted must be true or false, got {assisted!r}")
            assisted = False
        elif assisted and status in ("blank", "skipped_not_covered"):
            add(label, f'assisted is true but status is "{status}"; an item with nothing graded '
                       f'cannot have been written with help')
        hint = hints.get(iid)
        if hint is not None and status == "graded" and assisted is not True:
            add(label, f"has a hint logged in {rel(hints_path(course, set_id))} ({HINT_RUNGS.get(hint.get('rung'), '?')}: "
                       f"{hint.get('learned')!r}) but assisted is not true; work done after a hint must be graded as "
                       f"assisted, scoring only what was done without it")
        swh = it.get("score_with_help")
        if swh is not None:
            if not assisted:
                add(label, "score_with_help is only for assisted items")
                swh = None
            elif not is_num(swh) or (ok and not (fr(score) <= fr(swh) <= fr(mx))):
                add(label, f"score_with_help must be a number from the score ({fmt_num(score) if is_num(score) else '?'}) "
                           f"to max ({fmt_num(mx) if is_num(mx) else '?'}), got {swh!r}")
                swh = None
        elif hint is not None and status == "graded":
            add(label, "has a logged hint, so score_with_help is required: the points the whole answer earns "
                       "if the hint is allowed")
        minutes = it.get("minutes")
        if minutes is not None and (not is_num(minutes) or minutes <= 0):
            add(label, f"minutes must be null or a number > 0, got {minutes!r}")
            minutes = None
        budget = sit.get("minutes")
        budget = budget if is_num(budget) and budget > 0 else None
        conf = it.get("confidence")
        if conf is None and status != "graded":
            conf = "high"
        if conf not in CONFIDENCES:
            add(label, f"confidence {conf!r} is not one of {', '.join(CONFIDENCES)}")
        tk = it.get("takeaway", "")
        if tk is None:
            tk = ""
        if not isinstance(tk, str):
            add(label, f"takeaway must be a string, got {tk!r}")
            tk = ""
        elif count_words(tk) > MAX_TAKEAWAY_WORDS:
            add(label, f"takeaway has {count_words(tk)} words; the limit is {MAX_TAKEAWAY_WORDS}")
        if ok:
            dedup = []
            for t in errs:
                if isinstance(t, str) and t in ERROR_TAGS and t not in dedup:
                    dedup.append(t)
            rows.append({
                "course": course.key, "set": set_id, "kind": setdata["kind"], "date": fb.get("graded_on"),
                "item": iid, "archetype": sit["archetype"], "level": sit["level"], "format": sit["format"],
                "score": score, "max": mx, "status": status, "errors": dedup,
                "confidence": conf, "takeaway": tk,
                "assisted": assisted, "minutes": minutes, "budget_minutes": budget,
                "score_with_help": swh,
                "hint": None if hint is None else {k: hint[k] for k in ("rung", "gap", "cue", "learned")},
            })
    return rows, P


# --------------------------------------------------------------------------- ledger io

ROW_REQUIRED = ("set", "kind", "date", "item", "archetype", "level", "score", "max", "status")


def read_ledger(course):
    path = course.path / "ledger.jsonl"
    if not path.exists():
        return []
    rows, P = [], []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise DataError(f"{rel(path)}: cannot read file: {e}")
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            P.append(f"{rel(path)}: line {n}: invalid JSON: {e.msg}")
            continue
        miss = [k for k in ROW_REQUIRED if not isinstance(r, dict) or k not in r]
        if miss:
            P.append(f"{rel(path)}: line {n}: row lacks {', '.join(miss)}")
            continue
        if (parse_date(r["date"]) is None or r["status"] not in STATUSES or r["level"] not in (1, 2, 3)
                or not is_num(r["score"]) or not is_num(r["max"]) or r["max"] <= 0):
            P.append(f"{rel(path)}: line {n}: row for set {r.get('set')} item {r.get('item')} has an "
                     f"invalid date, status, level, score or max")
            continue
        rows.append(r)
    if P:
        raise DataError(P + ["the ledger is only written by `ledger.py record`; fix or restore the file"])
    return rows


def write_ledger(course, rows):
    path = course.path / "ledger.jsonl"
    tmp = path.with_name(f".ledger.jsonl.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(tmp, path)


# --------------------------------------------------------------------------- mastery

def chrono(rows):
    """Rows by date, then file order (stable)."""
    return [r for _, r in sorted(enumerate(rows), key=lambda t: (t[1]["date"], t[0]))]


def compute_stats(bp, rows):
    """Per-archetype statistics.  Returns (stats by id, {unknown archetype: row count})."""
    by = {a["id"]: [] for a in bp["archetypes"]}
    unknown = {}
    for r in chrono(rows):
        if r["status"] == "skipped_not_covered":
            continue
        if r["archetype"] in by:
            by[r["archetype"]].append(r)
        else:
            unknown[r["archetype"]] = unknown.get(r["archetype"], 0) + 1
    stats = {}
    for a in bp["archetypes"]:
        rs = by[a["id"]]
        if not rs:
            stats[a["id"]] = {"id": a["id"], "attempts": 0, "assisted": 0, "mastery": None, "status": "unmeasured",
                              "last": None, "last_f": None, "last_level": None, "last_date": None}
            continue
        num = den = F(0)
        for k, r in enumerate(reversed(rs)):
            w = F(1, 2 ** k)
            f = fr(r["score"]) / fr(r["max"])
            e = min(F(1), f * LEVEL_C[r["level"]])
            num += w * e
            den += w
        m = num / den
        last = rs[-1]
        if m >= F(4, 5) and last["level"] >= 2:
            status = "exam-ready"
        elif m >= F(11, 20):
            status = "close"
        else:
            status = "needs-work"
        stats[a["id"]] = {"id": a["id"], "attempts": len(rs), "assisted": sum(1 for r in rs if row_assisted(r)),
                          "mastery": m, "status": status, "last": last,
                          "last_f": fr(last["score"]) / fr(last["max"]), "last_level": last["level"],
                          "last_date": parse_date(last["date"])}
    return stats, unknown


def grade_figures(bp, stats):
    cov = F(0)
    s = F(0)
    for a in bp["archetypes"]:
        m = stats[a["id"]]["mastery"]
        if m is not None:
            cov += a["w"]
            s += a["w"] * m
    return {"coverage": cov, "grade_on_measured": (10 * s / cov) if cov > 0 else None, "grade_banked": 10 * s}


def slow_last(st):
    """The slowness rule fired: the latest row scored f >= 0.8 but took more than 1.5 x its budget."""
    return st["mastery"] is not None and st["last_f"] >= F(4, 5) and row_slow(st["last"])


def next_level(st):
    if st["mastery"] is None:
        return 2
    f, lv = st["last_f"], st["last_level"]
    if f >= F(4, 5):
        new = min(3, lv + 1)
    elif f >= F(1, 2):
        new = lv
    else:
        new = max(1, lv - 1)
    # help and slowness never raise the level: correct with a hint, or correct but too slow,
    # is not yet exam level
    if row_assisted(st["last"]) or slow_last(st):
        new = min(new, lv)
    # help, then the rest done well: the gap was the way in, not the working, so the re-test stays
    # at this level instead of dropping to a scaffolded one
    hf = row_help_f(st["last"])
    if hf is not None and hf >= HELD_LEVEL_F:
        new = lv
    return new


def hint_retest(st):
    """The archetype's latest attempt needed a logged hint: the next training set re-tests it."""
    return st["mastery"] is not None and row_hint(st["last"]) is not None


def set_summaries(rows, bp=None):
    """One summary per recorded set, in chronological order."""
    order, info = [], {}
    for i, r in sorted(enumerate(rows), key=lambda t: (t[1]["date"], t[0])):
        sid = r["set"]
        if sid not in info:
            info[sid] = {"set": sid, "kind": r["kind"], "date": r["date"], "score": F(0), "max": F(0),
                         "items": 0, "skipped": 0, "first_index": i,
                         "assisted": 0, "time_used": F(0), "time_budget": F(0)}
            order.append(sid)
        s = info[sid]
        if r["status"] == "skipped_not_covered":
            s["skipped"] += 1
            continue
        s["items"] += 1
        s["score"] += fr(r["score"])
        s["max"] += fr(r["max"])
        if row_assisted(r):
            s["assisted"] += 1
        if row_minutes(r) is not None and row_budget(r) is not None:   # only items with both numbers
            s["time_used"] += fr(row_minutes(r))
            s["time_budget"] += fr(row_budget(r))
    out = [info[s] for s in order]
    for s in out:
        s["pct"] = (s["score"] / s["max"]) if s["max"] > 0 else None
        s["time_ratio"] = (s["time_used"] / s["time_budget"]) if s["time_budget"] > 0 else None
        s["grade_eq"] = None
        if bp is not None and s["pct"] is not None:
            s["grade_eq"] = s["pct"] * fr(bp["total_points"]) / fr(bp["grade_divisor"])
    return out


def days_left(course, on_date):
    return (course.exam_date - on_date).days


def study_days_left(cfg, course, on_date):
    n, d = 0, on_date
    while d < course.exam_date:
        if d.weekday() in cfg.study_weekdays:
            n += 1
        d += timedelta(days=1)
    return n


class CourseState:
    """Everything derived from blueprint + ledger for one course."""

    def __init__(self, cfg, course, on_date):
        self.cfg, self.course, self.date = cfg, course, on_date
        self.bp, self.problem = try_blueprint(course)
        self.rows, self.ledger_problem = [], None
        try:
            self.rows = read_ledger(course)
        except DataError as e:
            self.ledger_problem = "; ".join(e.msgs)
        self.stats, self.unknown, self.grades, self.sets = {}, {}, None, []
        self.warnings = []
        if self.bp is not None:
            if self.ledger_problem is None:
                self.stats, self.unknown = compute_stats(self.bp, self.rows)
                self.grades = grade_figures(self.bp, self.stats)
                self.sets = set_summaries(self.rows, self.bp)
                if self.unknown:
                    self.warnings.append("ledger rows for archetypes missing from blueprint.json: " +
                                         ", ".join(f"{k} ({v})" for k, v in self.unknown.items()))
        elif self.ledger_problem is None:
            self.sets = set_summaries(self.rows)

    def summary(self):
        c = self.course
        s = {"course": c.key, "name": c.name, "exam_date": c.exam_date.isoformat(),
             "days_left": days_left(c, self.date), "study_days_left": study_days_left(self.cfg, c, self.date),
             "blueprint": self.bp is not None, "problem": self.problem if self.bp is None else self.ledger_problem,
             "sets_done": len(self.sets), "last_set": None, "holdout": None,
             "coverage": None, "grade_on_measured": None, "grade_banked": None,
             "archetypes_measured": None, "archetypes_total": None}
        if self.sets:
            ls = self.sets[-1]
            s["last_set"] = {"set": ls["set"], "kind": ls["kind"], "date": ls["date"], "score": jm(ls["score"]),
                             "max": jm(ls["max"]), "pct": None if ls["pct"] is None else jf(ls["pct"], 3)}
            ho = [x for x in self.sets if x["kind"] == "holdout"]
            if ho:
                h = ho[-1]
                s["holdout"] = {"set": h["set"], "date": h["date"], "score": jm(h["score"]), "max": jm(h["max"]),
                                "pct": None if h["pct"] is None else jf(h["pct"], 3),
                                "grade_eq": None if h["grade_eq"] is None else jf(h["grade_eq"], 2)}
        if self.grades is not None:
            g = self.grades
            s["coverage"] = jf(g["coverage"], 3)
            s["grade_on_measured"] = None if g["grade_on_measured"] is None else jf(g["grade_on_measured"], 2)
            s["grade_banked"] = jf(g["grade_banked"], 2)
            s["archetypes_total"] = len(self.bp["archetypes"])
            s["archetypes_measured"] = sum(1 for v in self.stats.values() if v["mastery"] is not None)
        return s


# --------------------------------------------------------------------------- next-set plan

def mastery_json(st):
    return None if st["mastery"] is None else jf(st["mastery"], 3)


def plan_next(cfg, course, bp, rows, kind, minutes, on_date, state=None):
    warnings = []
    stats, unknown = compute_stats(bp, rows)
    if unknown:
        warnings.append("ledger rows for archetypes missing from blueprint.json: " +
                        ", ".join(f"{k} ({v})" for k, v in unknown.items()))
    sets = sets_lenient(course, warnings)
    recorded = {r["set"] for r in rows}
    pending = [s for s in list_set_ids(course) if s not in recorded]
    if pending:
        warnings.append("sets without recorded feedback: " + ", ".join(pending))
    variations = {}
    for sid, d in sets.items():
        for it in d["items"]:
            if isinstance(it, dict) and isinstance(it.get("variation"), str) and it["variation"].strip():
                lst = variations.setdefault(it.get("archetype"), [])
                if it["variation"] not in lst:
                    lst.append(it["variation"])
    chron = chrono(rows)

    def recent_errors(aid):
        out = []
        for r in reversed(chron):
            if r["archetype"] != aid or r["status"] == "skipped_not_covered":
                continue
            asst = row_assisted(r)
            if r["errors"] or fr(r["score"]) < fr(r["max"]) or asst or row_hint(r):
                swh = r.get("score_with_help")
                out.append({"set": r["set"], "item": r["item"], "errors": r["errors"], "takeaway": r["takeaway"],
                            "assisted": asst, "minutes": row_minutes(r), "budget_minutes": row_budget(r),
                            "score_with_help": swh if asst and is_num(swh) else None, "max": r["max"],
                            "hint": row_hint(r)})
            if len(out) == 3:
                break
        return out

    def covered(a):
        return a["covered_from"] is None or a["covered_from"] <= on_date

    def item_minutes(a, level):
        return a["typical_minutes"] * LEVEL_MIN[level]

    def reason(a, st, extra=""):
        w = pct_str(a["w"], 1)
        if st["mastery"] is None:
            base = f"weight {w}%, not attempted yet"
        else:
            r = st["last"]
            base = (f"weight {w}%, mastery {float(st['mastery']):.2f}, last attempt "
                    f"{fmt_num(r['score'])}/{fmt_num(r['max'])} at level {r['level']}")
        return extra + base

    def make_item(a, level, extra="", priority=None):
        st = stats[a["id"]]
        it = {"archetype": a["id"], "name": a["name"], "level": level, "minutes": jm(item_minutes(a, level)),
              "points": jm(a["typical_points"]), "mastery": mastery_json(st), "status": st["status"],
              "slow_last": slow_last(st), "hint_retest": hint_retest(st),
              "not_yet_covered": not covered(a), "reason": reason(a, st, extra),
              "recent_errors": recent_errors(a["id"]), "avoid_variations": variations.get(a["id"], [])}
        if priority is not None:
            it["priority"] = jf(priority, 4)
        return it

    items = []
    if kind in ("diagnostic", "full"):
        for a in bp["archetypes"]:
            st = stats[a["id"]]
            level = 2 if kind == "diagnostic" else next_level(st)
            extra = ""
            if not covered(a):
                extra = f"not lectured yet (covered_from {a['covered_from'].isoformat()}); "
            items.append(make_item(a, level, extra))
        budget = F(str(minutes)) if minutes is not None else fr(bp["duration_min"])
        structure = bp["full_exam_structure"]
    else:
        budget = F(str(minutes)) if minutes is not None else F(DEFAULT_TRAIN_MINUTES)
        structure = None
        cand = []
        for idx, a in enumerate(bp["archetypes"]):
            if not covered(a):
                continue
            st = stats[a["id"]]
            if st["mastery"] is None:
                m, factor, days = F(3, 10), F(1), 0
            else:
                m = st["mastery"]
                factor = F(3, 2) if st["last_f"] < F(1, 2) else F(1)
                days = max(0, (on_date - st["last_date"]).days)
            p = a["w"] * (1 - m) * factor + F(1, 100) * a["w"] * days
            cand.append({"a": a, "st": st, "p": p, "idx": idx, "days": days, "level": next_level(st)})
        if not cand:
            warnings.append(f"no archetype has covered_from <= {on_date.isoformat()}; nothing to practise yet")
        cand.sort(key=lambda c: (-c["p"], c["idx"]))
        ready = [c for c in cand if c["st"]["status"] == "exam-ready" and c["days"] >= RETENTION_DAYS]
        retention = max(ready, key=lambda c: (c["days"], -c["idx"])) if ready else None
        chosen, total = [], F(0)
        if retention is not None:
            chosen.append(retention)
            total += item_minutes(retention["a"], retention["level"])
        # whatever needed a logged hint last time comes back first: the proof that the hint stuck
        retests = [c for c in cand if hint_retest(c["st"])]
        for c in retests + [c for c in cand if not hint_retest(c["st"])]:
            if c is retention:
                continue
            m = item_minutes(c["a"], c["level"])
            if not chosen or total + m <= budget:
                chosen.append(c)
                total += m
        chosen.sort(key=lambda c: (-c["p"], c["idx"]))
        for c in chosen:
            extra = ""
            if c is retention:
                extra = f"retention check (exam-ready, last attempted {c['days']} days ago); "
            elif hint_retest(c["st"]):
                r = c["st"]["last"]
                extra = f"re-test after a hint in {r['set']} {r['item']} ({row_hint(r)['learned']}); "
            items.append(make_item(c["a"], c["level"], extra, c["p"]))
    planned = sum((F(str(it["minutes"])) for it in items), F(0))
    spec = {"course": course.key, "kind": kind, "set": next_set_id(course, kind), "date": on_date.isoformat(),
            "minutes": jm(budget), "planned_minutes": jm(planned),
            "planned_points": jm(sum((F(str(it["points"])) for it in items), F(0))),
            "items": items, "full_exam_structure": structure, "warnings": warnings}
    return spec


# --------------------------------------------------------------------------- commands

def cmd_newid(cfg, args):
    course = get_course(cfg, args.course)
    if args.kind not in KIND_LETTER:
        return fail(f"unknown kind {args.kind!r}: use one of {', '.join(KIND_LETTER)} "
                    f"(the word, not the id letter)", 2)
    print(next_set_id(course, args.kind))
    return 0


def cmd_checkset(cfg, args):
    course = get_course(cfg, args.course)
    sid = check_set_arg(course, args.set)
    problems, n, points = checkset(course, sid)
    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        return 1
    print(f"OK {sid}: {n} items, {fmt_num(points)} points")
    return 0


def cmd_record(cfg, args):
    course = get_course(cfg, args.course)
    sid = check_set_arg(course, args.set)
    arch_ids, _ = blueprint_ids_lenient(course)
    bp, _ = try_blueprint(course)
    setdata = load_set(course, sid, arch_ids)
    fb_path = course.path / "feedback" / f"{sid}.json"
    fb = load_json(fb_path)
    hints, problems = load_hints(course, sid, {it["item"] for it in setdata["items"]})
    rows, more = build_rows(course, sid, setdata, fb, rel(fb_path), hints)
    problems += more
    if problems:
        raise DataError(problems + [f"nothing was recorded; {rel(course.path / 'ledger.jsonl')} is unchanged"])
    old = read_ledger(course)
    idxs = [i for i, r in enumerate(old) if r["set"] == sid]
    kept = [r for r in old if r["set"] != sid]
    pos = idxs[0] if idxs else len(kept)
    new = kept[:pos] + rows + kept[pos:]
    before = after = None
    if bp is not None:
        before, _ = compute_stats(bp, old)
        after, _ = compute_stats(bp, new)
    write_ledger(course, new)
    counted = [r for r in rows if r["status"] != "skipped_not_covered"]
    sc = sum((fr(r["score"]) for r in counted), F(0))
    mx = sum((fr(r["max"]) for r in counted), F(0))
    nb = sum(1 for r in rows if r["status"] == "blank")
    ns = sum(1 for r in rows if r["status"] == "skipped_not_covered")
    msg = f"recorded {sid} ({setdata['kind']}, {rows[0]['date'] if rows else fb.get('graded_on')}): {len(rows)} rows"
    if idxs:
        olddates = sorted({old[i]["date"] for i in idxs})
        msg += f" (replaced {len(idxs)} earlier rows, previously dated {', '.join(olddates)})"
    pc = f" ({float(sc / mx) * 100:.0f}%)" if mx > 0 else ""
    msg += f", score {fmt_num(sc)}/{fmt_num(mx)}{pc}, {nb} blank, {ns} skipped"
    nh = sum(1 for r in rows if r["hint"])
    if nh:
        msg += f", {nh} with a logged hint"
    print(msg)
    if before is not None:
        ch = []
        for aid in dict.fromkeys(r["archetype"] for r in rows):
            if aid in before and aid in after:
                b, a_ = before[aid]["mastery"], after[aid]["mastery"]
                if b != a_:
                    ch.append(f"{aid} {format(float(a_), '.2f')} (new)" if b is None else
                              f"{aid} {format(float(b), '.2f')}->{format(float(a_), '.2f')}")
        if ch:
            print("mastery: " + ", ".join(ch))
    return 0


def require_blueprint(state):
    if state.bp is None:
        raise DataError(state.problem)
    if state.ledger_problem:
        raise DataError(state.ledger_problem)


def cmd_mastery(cfg, args):
    course = get_course(cfg, args.course)
    st = CourseState(cfg, course, today())
    require_blueprint(st)
    for w in st.warnings:
        print(f"WARN {w}", file=sys.stderr)
    g = st.grades
    rows = []
    for a in st.bp["archetypes"]:
        s = st.stats[a["id"]]
        last = s["last"]
        rows.append({"id": a["id"], "name": a["name"], "group": a["group"], "weight": jf(a["w"], 4),
                     "attempts": s["attempts"], "assisted": s["assisted"], "last_level": s["last_level"],
                     "last_score": None if last is None else last["score"],
                     "last_max": None if last is None else last["max"],
                     "last_date": None if last is None else last["date"],
                     "mastery": mastery_json(s), "status": s["status"]})
    summ = {"course": course.key, "sets_done": len(st.sets), "coverage": jf(g["coverage"], 3),
            "grade_on_measured": None if g["grade_on_measured"] is None else jf(g["grade_on_measured"], 2),
            "grade_banked": jf(g["grade_banked"], 2)}
    if args.json:
        print(dumps_compact({**summ, "archetypes": rows}))
        return 0
    measured = sum(1 for r in rows if r["attempts"])
    gm = "-" if summ["grade_on_measured"] is None else f"{summ['grade_on_measured']:.2f}"
    print(f"{course.key} mastery: {measured}/{len(rows)} archetypes measured, {len(st.sets)} sets, "
          f"coverage {float(g['coverage']) * 100:.0f}%, grade_on_measured {gm}, grade_banked {summ['grade_banked']:.2f}")
    wid = max(len(r["id"]) for r in rows)
    print(f"{'id'.ljust(wid)}  {'w%':>5}  {'n':>2}  L  {'mast':>5}  {'status':<10}  last")
    for r in rows:
        if r["attempts"]:
            last = f"{fmt_num(r['last_score'])}/{fmt_num(r['last_max'])} on {r['last_date']}"
            line = (f"{r['id'].ljust(wid)}  {r['weight'] * 100:5.1f}  {r['attempts']:>2}  {r['last_level']}  "
                    f"{r['mastery']:5.2f}  {r['status']:<10}  {last}")
        else:
            line = f"{r['id'].ljust(wid)}  {r['weight'] * 100:5.1f}  {0:>2}  -  {'-':>5}  {'unmeasured':<10}  -"
        print(line)
    return 0


def cmd_next(cfg, args):
    course = get_course(cfg, args.course)
    on_date = parse_date(args.date) if args.date else today()
    if on_date is None:
        return fail(f"--date {args.date!r} is not a YYYY-MM-DD date", 2)
    if args.minutes is not None and not (args.minutes > 0):
        return fail(f"--minutes must be > 0, got {args.minutes}", 2)
    st = CourseState(cfg, course, on_date)
    require_blueprint(st)
    minutes = None if args.minutes is None else (int(args.minutes) if args.minutes == int(args.minutes) else args.minutes)
    spec = plan_next(cfg, course, st.bp, st.rows, args.kind, minutes, on_date, st)
    print(dumps_compact(spec))
    return 0


def cmd_status(cfg, args):
    on_date = today()
    out, errors = [], []
    for course in cfg.courses.values():
        st = CourseState(cfg, course, on_date)
        s = st.summary()
        out.append(s)
        if st.ledger_problem:
            errors.append(st.ledger_problem)
        elif st.bp is None and st.problem and "file not found" not in st.problem:
            errors.append(st.problem)
    if args.json:
        print(dumps_compact({"date": on_date.isoformat(), "courses": out}))
    else:
        for s in out:
            head = (f"{s['course']:<5} exam {s['exam_date']} ({s['days_left']}d, {s['study_days_left']} study days left)"
                    f"  sets {s['sets_done']}")
            if s["last_set"]:
                ls = s["last_set"]
                pc = "" if ls["pct"] is None else f" ({ls['pct'] * 100:.0f}%)"
                head += f"  last {ls['set']} {fmt_num(ls['score'])}/{fmt_num(ls['max'])}{pc}"
            if s["holdout"]:
                ho = s["holdout"]
                head += f"  holdout {ho['set']} {fmt_num(ho['score'])}/{fmt_num(ho['max'])}"
            if not s["blueprint"]:
                head += "  no blueprint yet" if "file not found" in (s["problem"] or "") else "  BLUEPRINT INVALID"
            elif s["problem"]:
                head += "  LEDGER INVALID"
            else:
                gm = "-" if s["grade_on_measured"] is None else f"{s['grade_on_measured']:.2f}"
                head += (f"  grade measured {gm}  banked {s['grade_banked']:.2f}  "
                         f"coverage {s['coverage'] * 100:.0f}% ({s['archetypes_measured']}/{s['archetypes_total']} archetypes)")
            print(head)
    if errors:
        return fail(errors)
    return 0


# --------------------------------------------------------------------------- main

def build_parser():
    ap = argparse.ArgumentParser(prog="ledger.py", description="Exam-prep ledger, mastery and next-set planner.")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="COMMAND")
    p = sub.add_parser("newid", help="print the next free set id for a kind")
    p.add_argument("course")
    p.add_argument("kind", help="diagnostic | train | full | holdout")
    p.set_defaults(fn=cmd_newid)
    p = sub.add_parser("checkset", help="validate sets/<SET>/set.json before handing the set out")
    p.add_argument("course")
    p.add_argument("set")
    p.set_defaults(fn=cmd_checkset)
    p = sub.add_parser("record", help="validate feedback/<SET>.json and (re)write its ledger rows")
    p.add_argument("course")
    p.add_argument("set")
    p.set_defaults(fn=cmd_record)
    p = sub.add_parser("mastery", help="mastery table for a course")
    p.add_argument("course")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_mastery)
    p = sub.add_parser("next", help="JSON spec for the next set")
    p.add_argument("course")
    p.add_argument("--kind", required=True, choices=["diagnostic", "train", "full"])
    p.add_argument("--minutes", type=float, default=None, help="time budget (train default 90, "
                   "diagnostic/full default: the blueprint's duration_min)")
    p.add_argument("--date", default=None, help="YYYY-MM-DD, default today")
    p.set_defaults(fn=cmd_next)
    p = sub.add_parser("status", help="one line per course")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config()
        return args.fn(cfg, args)
    except DataError as e:
        return fail(e.msgs)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
