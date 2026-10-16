# Tooling spec

Deterministic scripts behind the exam-prep loop. No model calls anywhere in here: the
point of these scripts is that bookkeeping, adaptivity and the progress report cost zero
tokens and always behave the same.

Python 3 standard library only. External programs available: `latexmk`/`pdflatex`
(TeX Live), ImageMagick (`magick`, with HEIC support), poppler (`pdftoppm`, `pdftotext`).

The project root is the parent of `tools/`. Scripts must work from any working directory.
The root path contains spaces.

## The loop these scripts serve

A student prepares for their finals. Per course, agents write practice sets (`sets/`),
the student hands in photos of handwritten work (`submissions/`), a grader agent writes
feedback (`feedback/`), and these scripts turn the feedback into a ledger, a mastery
estimate per question type ("archetype"), a spec for the next set, and one progress PDF.

## `tools/config.json`

```json
{
  "courses": {
    "MATH": {"dir": "MATH",          "name": "Multivariable Calculus (MATH201)", "exam_date": "2026-10-30"},
    "MECH": {"dir": "Mechanics",     "name": "Classical Mechanics (PHYS102)",    "exam_date": "2026-11-05"}
  },
  "study_days": ["Tue", "Wed", "Thu"]
}
```

## Input files (written by agents; validate them, never trust them)

### `<dir>/blueprint.json`

```json
{
  "course": "MATH",
  "duration_min": 180,
  "total_points": 100,
  "grade_divisor": 10,
  "pass_grade": 5.5,
  "pass_grade_note": "optional, written by course.py pass-mark: why the final needs this grade",
  "archetypes": [
    {
      "id": "vec-line-integrals",
      "name": "Line integrals of vector fields (parametrisation, work, conservative fields)",
      "group": "Vector calculus",
      "weight": 0.10,
      "typical_points": 10,
      "typical_minutes": 15,
      "format": "open",
      "covered_from": "2026-09-01"
    }
  ],
  "full_exam_structure": [
    {"slot": "Problem 1", "points": 20, "archetypes": ["vec-line-integrals"], "note": "free text for the writer"}
  ]
}
```

`weight` is the archetype's expected share of the final's points; normalise so they sum
to 1. `covered_from` is the date the topic has been lectured (may be absent = always
covered). `full_exam_structure` is opaque to the scripts and passed through to the writer.

### `<dir>/sets/<SET>/set.json`

```json
{
  "course": "MATH",
  "set": "MATH-D01",
  "kind": "diagnostic",
  "created": "2026-10-13",
  "duration_min": 180,
  "total_points": 100,
  "items": [
    {"item": "1.1", "archetype": "vec-line-integrals", "level": 2, "max": 5, "minutes": 8,
     "format": "open", "mc_answer": null, "not_yet_covered": false,
     "variation": "plain-text note on what makes this instance different from earlier ones"}
  ]
}
```

Set ids are `<COURSE>-<K><NN>`, K one of `D` diagnostic, `T` training, `F` full mock,
`H` held-out real exam. `kind` is `diagnostic | train | full | holdout`. `level` is
1 (below exam level, scaffolded), 2 (exam level), 3 (hardest seen on past exams or a
little above). `format` is `open | mc | mathematica-mc | proof`.

### `<dir>/feedback/<SET>.json`

```json
{
  "course": "MATH",
  "set": "MATH-D01",
  "graded_on": "2026-10-13",
  "time_spent_min": 175,
  "items": [
    {"item": "1.1", "score": 3, "max": 5, "status": "graded",
     "errors": ["justification"], "confidence": "high",
     "takeaway": "Plain text, at most 25 words. May contain $inline math$."}
  ]
}
```

`status`: `graded | blank | skipped_not_covered`. `confidence`: `high | medium | low`
(how sure the grader is that it read the handwriting correctly). `time_spent_min` may be
null. `errors` uses this fixed vocabulary; reject anything else:

| tag | meaning |
|---|---|
| `concept` | wrong or missing idea |
| `method` | wrong approach, or did not know how to start |
| `setup` | right method, wrong set-up (limits, parametrisation, boundary conditions, coordinates) |
| `algebra` | slip in manipulation |
| `sign` | sign error |
| `arithmetic` | numeric slip |
| `notation` | notation that cost points |
| `justification` | result right, required motivation missing or insufficient |
| `misread` | answered a different question than the one asked |
| `incomplete` | stopped before the end / ran out of time |

## Output file: `<dir>/ledger.jsonl`

Written only by `ledger.py record`. One JSON object per graded item: everything from the
feedback item plus `course`, `set`, `kind`, `date` (= graded_on), `archetype`, `level`,
`format` (joined from set.json).

## `tools/ledger.py`

Subcommands (all take a course key from `config.json`, e.g. `MATH`):

- `newid COURSE KIND` — print the next free set id for that kind (`MATH-T03`), from the
  directories in `sets/`. `KIND` is the word used everywhere else (`diagnostic`, `train`,
  `full`, `holdout`) and is mapped to the id letter `D`, `T`, `F`, `H`; example:
  `newid MATH train` prints `MATH-T01` when `sets/` holds no training set yet. Any other
  value (including a bare letter) is an error: message listing the four allowed words,
  non-zero exit, nothing printed to stdout.
- `checkset COURSE SET` — validate `sets/<SET>/set.json` before the set is handed to the
  student. Checks, all of them run and every problem reported (not just the first):
  1. the file exists and parses as JSON (if not, report that and stop; nothing else can
     be checked);
  2. `course` equals `COURSE` and `set` equals `SET`;
  3. `kind` is one of `diagnostic | train | full | holdout`, and every item's `format` is
     one of `open | mc | mathematica-mc | proof`;
  4. every item's `level` is the integer 1, 2 or 3;
  5. item ids (`item`) are unique;
  6. every item's `archetype` exists in `blueprint.json` (if the blueprint is missing or
     does not parse, report that as one problem and skip this check);
  7. the items' `max` values sum to `total_points`;
  8. every item with `format` `mc` or `mathematica-mc` has an `mc_answer` that is a
     single letter (`A`-`Z` or `a`-`z`);
  9. `exam.pdf` and `key.pdf` exist in the same directory as `set.json`.

  On success print exactly one line, `OK <SET>: <n> items, <points> points` (`<points>`
  is the sum of the items' `max`), and exit 0. On failure print one line per problem,
  each naming the item where one applies, and exit non-zero.
- `record COURSE SET` — validate `feedback/<SET>.json` against `sets/<SET>/set.json`
  (every item present exactly once, `0 <= score <= max`, max equal to the set's, known
  tags and statuses) and write the rows. Idempotent: recording a set again replaces its
  earlier rows (regrades happen). Clear error messages naming the offending item; exit
  non-zero and change nothing on any validation failure.
- `mastery COURSE [--json]` — the mastery table (see below).
- `next COURSE --kind diagnostic|train|full [--minutes N] [--date YYYY-MM-DD]` — print a
  JSON spec for the next set (see below). `--date` defaults to today.
- `status [--json]` — all courses: days and study days left until the exam, sets done,
  predicted grade figures, last set score.

### Mastery per archetype

Take the archetype's ledger rows in chronological order (by date, then file order),
ignoring `skipped_not_covered`. `blank` counts as score 0.

- fraction `f_i = score / max`
- evidence `e_i = min(1, f_i * c(level))` with `c = {1: 0.65, 2: 1.0, 3: 1.1}`
  (full marks on a below-exam-level item is not evidence of exam-level mastery)
- recency weight `w_i = 0.5 ** k`, `k = 0` for the most recent row, 1 for the one before…
- `mastery = sum(w_i e_i) / sum(w_i)`
- `status`: `unmeasured` (no rows); `exam-ready` (mastery >= 0.80 and the most recent row
  is level >= 2); `close` (mastery >= 0.55); otherwise `needs-work`

### Predicted grade per course

With weights normalised to 1 over all archetypes:

- `coverage` = sum of weights of measured archetypes
- `grade_on_measured` = 10 * sum(w_a m_a) / coverage over measured archetypes (null if none)
- `grade_banked` = 10 * sum(w_a m_a) with unmeasured archetypes counted as 0

### Next-set spec

Level for an archetype's next item, from its most recent row (fraction `f`, level `L`):
unmeasured -> 2; `f >= 0.8` -> `min(3, L + 1)`; `0.5 <= f < 0.8` -> `L`; `f < 0.5` ->
`max(1, L - 1)`. For `--kind diagnostic` every level is 2.

`train`: only archetypes with `covered_from <= date`. Priority
`p = weight * (1 - mastery) * (1.5 if last f < 0.5 else 1) + 0.01 * weight * days_since_last`
(unmeasured: mastery 0.3, days_since_last 0). Take archetypes in priority order until the
planned minutes reach the budget (`--minutes`, default 90); an item's minutes are
`typical_minutes * {1: 0.7, 2: 1.0, 3: 1.3}[level]`. If an `exam-ready` archetype has not
been attempted for 5 or more days, include the stalest one as a retention check.

`diagnostic` / `full`: include every archetype with its level and a `not_yet_covered`
flag (`covered_from > date`), and pass `full_exam_structure` through.

Output:

```json
{
  "course": "MATH", "kind": "train", "set": "MATH-T02", "date": "2026-10-15",
  "minutes": 90,
  "items": [
    {"archetype": "vec-line-integrals", "name": "...", "level": 2, "minutes": 15,
     "points": 10, "mastery": 0.42, "status": "needs-work", "not_yet_covered": false,
     "reason": "weight 10%, mastery 0.42, last attempt 2/5 at level 2",
     "recent_errors": [{"set": "MATH-D01", "item": "1.1", "errors": ["justification"], "takeaway": "..."}],
     "avoid_variations": ["variation strings of earlier items of this archetype, from all set.json files"]}
  ],
  "full_exam_structure": null
}
```

## `tools/build_report.py`

Writes `progress/progress.tex` and compiles it to `progress/progress.pdf`. One document
for all courses, rebuilt from scratch on every run. Must build cleanly with no data at
all (courses without a blueprint or without sets show "nothing yet").

Content:

1. **Overview** (first page): generation date; one row per course: exam date, days left,
   study days left, sets done, last set score, grade on measured part, coverage, banked
   grade, held-out exam result if any. A short legend explaining the three grade figures
   in plain words.
2. **Per course**:
   - Mastery table grouped by `group`: archetype name, weight %, attempts, last level,
     a mastery bar, status. Unmeasured rows visibly distinct.
   - Set history: id, date, kind, score, percentage, grade equivalent
     (`points / grade_divisor`, scaled to the full exam for partial sets), time spent.
     A small plot of percentage over time once there are two or more sets.
   - Where the points go: per error tag, how many items and how many points lost.
   - Mistake book: the takeaways, most recent first, at most 20, with set and item;
     takeaways from items the grader read with `low` confidence are marked "check reading".
   - Next up: the output of `next --kind train` as a short table.

Escape all plain-text fields for LaTeX, but pass `$...$` segments through unchanged.
Keep the layout sober and readable in print: A4, booktabs tables, bars drawn with rules
or TikZ, colour used only for status.

## `tools/build_tex.sh FILE.tex`

Compile with `latexmk -pdf -interaction=nonstopmode -halt-on-error` in the file's own
directory, with `TEXINPUTS` set so that `\usepackage{prep}` finds `tools/tex/prep.sty`.
Remove auxiliary files afterwards, keep the PDF. On failure print the first LaTeX error
with a few lines of context and exit non-zero.

## `tools/tex/prep.sty` and `tools/tex/README.md`

One style for the three kinds of documents agents write: practice exams, answer keys and
feedback. Agents write LaTeX bodies by hand, so the macros must be few and hard to misuse.

- Loads: amsmath, amssymb, mathtools, bm, siunitx, tikz, pgfplots, enumitem, booktabs,
  xcolor, graphicx, cancel, hyperref, geometry (A4, sensible margins).
- `\prepheader{course name}{set id}{kind label}{time}{points}{aids}` — title block.
- `\problem{Title}{points}` — auto-numbered "Problem N — Title (20 p)".
- `subqs` environment with `\subq{points}` — numbered `N.k`, points in the margin.
- `mc` environment with `\opt` — options lettered (a), (b), …
- Key: `solution` environment (visually set apart), `\rubric{points}{criterion}`,
  `\pitfall{text}`.
- Feedback: `fbitem` environment taking item id, score, max; inside it
  `\youwrote{...}` (what the grader read), `\firsterror{...}`, `\fix{...}`,
  `\takeaway{...}`.

`README.md`: the macro reference plus one minimal complete example each for an exam, a
key and a feedback document. Agents will be pointed at this file, so it must be exact.

## `tools/prep_photos.sh SUBMISSION_DIR`

Normalise phone photos for the grader. Take every image (jpg, jpeg, png, heic, heif,
webp; any case) and PDF directly inside the directory, order by EXIF capture time when
present and by natural filename order otherwise, and write `pages/page-01.jpg`, … :
auto-oriented, long edge at most 1800 px, metadata stripped, JPEG quality 85. PDF pages
are rendered with `pdftoppm` at 150 dpi. Rebuild `pages/` from scratch each run; never
touch the originals. Print the resulting list, and list separately the other files found
(`.nb`, `.txt`, …).

## Tests

`tools/tests/run.sh` builds a throwaway copy of the structure in a temp dir with a
made-up course (blueprint, three sets, feedback with a mix of statuses, levels and tags,
one regrade), runs every subcommand, checks the mastery numbers against hand-computed
values, builds the report PDF, compiles the three README examples, and runs
`prep_photos.sh` on a few generated images. Nothing made-up may end up in the real
course directories.

Tests for the two newer `ledger.py` subcommands:

- `newid`: with sets `X-D01`, `X-T01`, `X-T02` present, `newid X train` prints `X-T03`,
  `newid X diagnostic` prints `X-D02`, `newid X full` prints `X-F01`, `newid X holdout`
  prints `X-H01`; `newid X T` and `newid X nonsense` exit non-zero.
- `checkset`: one valid set (with `exam.pdf` and `key.pdf` present) prints
  `OK <SET>: <n> items, <points> points` and exits 0; one deliberately broken set that
  has several problems at once (wrong `course`, bad `kind`, bad `format`, `level` 4,
  duplicate item id, unknown archetype, `max` sum differing from `total_points`, an `mc`
  item with `mc_answer` null or `"AB"`, missing `key.pdf`) must list every one of them
  and exit non-zero; a set whose `set.json` does not parse reports that and exits
  non-zero.

## Addendum (2026-10-14): help marks and per-item time

The student sometimes asks an AI tutor for a hint when stuck and marks the lines written
with that help (a thick black bar in the margin), and writes elapsed-time stamps under
problems. Both now flow through the pipeline.

### Feedback items: two optional fields

```json
{"item": "14.1", "score": 2, "max": 6, "status": "graded", "errors": ["method"],
 "confidence": "high", "takeaway": "...",
 "assisted": true, "minutes": 23}
```

- `assisted` (bool, default false): part of the item was written with outside help.
  `score` is then the points earned by the unaided work only; the grader has already
  excluded the assisted part. An assisted item with status `blank` or
  `skipped_not_covered` is invalid.
- `minutes` (number or null, default null): time the student spent on the item, derived
  by the grader from the time stamps. Must be > 0 when present.

Old feedback files without these fields stay valid. `record` copies both into the ledger
rows (with defaults when absent), together with the item's budgeted minutes from
set.json as `budget_minutes`.

### Mastery and next-set rules

Mastery is unchanged (the score already reflects unaided work only).

Level rule additions, applied after the existing rule:
- an assisted most recent row never moves the level up;
- a most recent row with `f >= 0.8` but `minutes > 1.5 * budget_minutes` stays at level
  `L` instead of `L + 1` (correct but too slow is not yet exam level).

In the `next` output, each `recent_errors` entry also carries `assisted`, `minutes` and
`budget_minutes`, and each item carries `slow_last: true` when the slowness rule fired.
Rows that were assisted count as recent errors even when they lost no points.

### Report

- Set history: add "time vs budget" (sum of item minutes over sum of budgets for items
  with a time; blank when no times) and the number of assisted items.
- Mastery table: an "assisted" count per archetype next to attempts.
- New short section per course, "Time": the items of the last three sets that took more
  than 1.5 times their budget, with minutes and budget.
- Mistake book: mark takeaways from assisted items "needed help".

Tests: extend `tools/tests/run.sh` to cover both fields (valid and invalid values, old
files without them, the two level-rule additions, the report sections).

## Addendum (2026-10-16): hints before the attempt (`/hint`)

While working a set the student can ask the `/hint` session for help on one item. The
session gives the smallest hint that lets them start, on a ladder of three rungs, never
more: 1 nudge (a question pointing at what in the problem signals the approach), 2 method
(the method or idea named, and why it applies), 3 set-up (the first concrete step,
written down but not worked out). Every hint is logged by a script, the grader scores
only the work done without it, `record` enforces that, and the next training set
re-tests the question type first.

### `<dir>/submissions/<SET>/hints.json` (written only by `tools/hints.py`)

```json
{"course": "MATH", "set": "MATH-T01", "items": [
  {"item": "5.2", "rung": 2, "gap": "method",
   "cue": "flux through a closed surface, simple divergence",
   "learned": "Closed surface and an easy divergence: use the divergence theorem, not the faces.",
   "tried": "started parametrising the top face",
   "given": [{"rung": 1, "said": "Asked what a closed surface lets you use.", "at": "2026-10-20T10:42"},
             {"rung": 2, "said": "Named the divergence theorem and why it applies.", "at": "2026-10-20T10:49"}]}
]}
```

`rung` is the highest rung given; `gap` is `concept | method | setup` (what was
missing); `cue` at most 25 words, `learned` 30, `tried` 40 (may be null), each `said`
50 ($...$ counts as one word). Items appear in set order, at most once.

### `tools/hints.py`

- `pending`: sets with `set.json` and no feedback, newest first, with the number of
  hints logged.
- `open SET ITEM`: the question (from `exam.tex`), the hints already given on the item,
  the student's recent errors and earlier hints on the archetype (from the ledger), then
  under a `FOR THE TUTOR ONLY` heading the key's solution for the item and the
  archetype's blueprint notes. Refuses a graded set (pointing to `/review`), the
  held-out exam, and unknown items. Prints a `NOTE` first for a diagnostic or full mock.
- `log SET ITEM --rung N --gap G --said TEXT [--cue] [--learned] [--tried]`: upsert.
  The first hint on an item needs `--cue` and `--learned`; later ones append to `given`,
  keep the highest rung, and replace `gap` and any text given. Same refusals as `open`;
  invalid input logs nothing.
- `show SET [--json]`, and `drop SET ITEM` (a hint logged on the wrong item; refused once
  graded).

### Feedback and ledger

- New optional feedback field `score_with_help` (number): the points the whole answer
  earns if the help is allowed. Only for assisted items, `score <= score_with_help <=
  max`. Required for a graded item with a logged hint.
- `record` reads `hints.json` and rejects the feedback when the log does not parse or
  validate, or when a graded item with a logged hint has `assisted` false or no
  `score_with_help`. A hinted item may be `blank` (then `assisted` stays false).
- Rows gain `score_with_help` (null by default) and `hint` (null, or `{rung, gap, cue,
  learned}` from the log, also on blank rows). Mastery is unchanged.

### Next-set rules

- Level: if the latest row is assisted and `score_with_help / max >= 0.8`, the level
  stays at `L`, whatever the unaided score (the way in was missing, not the working).
- `train`: archetypes whose latest row has a `hint` are taken first (in priority order,
  after the retention check, within the budget), with the reason starting
  `re-test after a hint in <SET> <ITEM> (<learned>); `. Every item carries
  `hint_retest` (bool). `recent_errors` entries also carry `score_with_help`, `max` and
  `hint`, and rows with a hint count as recent errors.

### Report

- Mistake book: takeaways of hinted rows are marked `[hint: <rung name>]` instead of
  `[needed help]`.
- New section per course, "Hints", after the mistake book: the hinted items, newest
  first, at most 12, with the rung, what was learned, and the next attempt at that
  archetype (`set · item: score/max`, ", help again" when that one was helped too) or
  "not re-tested yet".

Tests: course HNT in `tools/tests/run.sh` covers `hints.py`, the `record` checks, the
level and re-test rules with controls, `item_context.py`, and the report.

## Addendum: course set-up (`course.py`, `doctor.py`, `intake.json`)

Used by `/start`. Same rules as the rest: standard library only, no model calls, changes
nothing it is not asked to change.

### `tools/doctor.py [--quick] [--json]`

Checks everything the project needs and prints, per missing item, the Debian/Ubuntu
package that provides it, plus one `sudo apt install` line per group. Groups:
`environment` and `core` (Python 3.9+, sympy, git, latexmk/pdflatex, the TeX packages
`prep.sty`, the report and the guide load, a test build of the first example in
`tools/tex/README.md`, ImageMagick with HEIC reading, poppler), `recommended` (qpdf,
wolframscript, Pillow for the tests; a project on `/mnt/` under WSL; macOS), `videos
(optional)` (the Manim venv or what is needed to build it, dvisvgm, Manim's TeX
packages). Exit 0 when `environment` and `core` are complete.

### `<dir>/intake.json` (written by the intake agent, `prompts/intake.md`)

```json
{"course": "MATH", "language": "en", "software": null,
 "files": [{"path": "materials/...", "role": "exam", "exam_id": "MATH-2024-01", "sitting": "final",
            "date": "2024-01-30", "answers": "materials/..." , "scanned": false, "note": ""}],
 "holdout_candidate": {"exam_id": "...", "files": ["materials/..."], "why": "..."},
 "holdout_none": false, "warnings": []}
```

`role` is one of `exam answers course_info schedule notes exercises formula_sheet
software other`. `exam_id` is `<KEY>-YYYY-MM` with an optional `-SUFFIX`, unique. `answers`
is a path, `"same"` or null. `course.py holdout` rewrites the paths of the files it moves
and marks them `"holdout": true`; `--none` sets `holdout_none`.

### `tools/course.py`

- `add KEY --name --exam-date [--dir]`: KEY is 2-8 capitals/digits starting with a
  letter; dir defaults to KEY, must be new and not one of the project's own folders.
  Creates `<dir>/materials/` and `<dir>/holdout/`, and `config.json` if needed.
- `study-days DAY...`: weekday names, any case, commas allowed.
- `list`; `state KEY [--json]`: the set-up steps in order, each `done`, `todo` or `n/a`:
  `materials` (files present), `intake` (valid), `holdout` (files in `holdout/` or
  `holdout_none`), `bank` (every non-held-out exam has `bank/<id>.md` and `.index.tsv`),
  `syllabus`, `formula_sheet` (n/a without a sheet), `toolkit` (n/a unless
  `software` is Mathematica), `seeds` (n/a without notes or exercises), `blueprint`
  (`blueprint.md`, a valid `blueprint.json`, `bank/index.tsv`), `pass_mark`
  (`pass_grade_note` present). `next` is the first `todo`.
- `inventory KEY`: files in `materials/` with size and PDF page count; `holdout/` only
  as a count.
- `check-intake KEY`: validate, and list files in `materials/` that intake.json misses.
- `holdout KEY FILE...` / `--none`: move files from `materials/` to `holdout/`.
- `pass-mark KEY GRADE --why TEXT`: set `pass_grade` and `pass_grade_note`.
- `archive KEY [--label]`: move `<dir>` to `archive/<label>/` (default `YYYY-MM`), keep
  its config entry in `archive/<label>/config.json`, drop it from `config.json`.

`ledger.py` accepts a `config.json` with no courses, and says to run `/start` when there
is no `config.json` at all.
