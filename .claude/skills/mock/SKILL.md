---
name: mock
description: Create the next practice set for one of the user's exam-prep courses (the keys in courses.md) - a diagnostic, a targeted training set, a full mock exam, or the held-out real exam. Use when the user asks for a mock, a practice set, "the next set", or more questions for a course.
---

# /mock COURSE [diagnostic|train|full|holdout] [minutes]

Produces a checked practice set and hands the user the exam PDF. Read `CLAUDE.md` first
if you have not: it explains the loop, who does what, and the rules that protect the user.

You are the orchestrator. You run scripts and spawn agents; you do not write or solve
questions yourself and you do not open bank files, keys or PDFs. That keeps this session
cheap, and it keeps question-writing with the model the user chose for it.

## Decide what to make

- Course key from the arguments (the keys in `courses.md`); directories are in
  `tools/config.json`. Run `python3 tools/course.py state COURSE` first: if it does not
  end with `set-up complete`, the course is not ready for sets. Say which step is next
  and that `/start` continues the set-up, and stop.
- Kind: as given. If none is given, use `diagnostic` when the course has no graded set
  yet, otherwise follow the plan table in `courses.md` for today, defaulting to `train`.
- Minutes (training sets only): as given, default 90.

Check `ls <dir>/sets` and `<dir>/submissions` first. If an earlier set was handed out and
never graded, tell the user and ask whether to grade or drop it before making another:
the next set is aimed at their latest results, so writing it blind wastes a set.

## Diagnostic, training set or full mock

1. Write the spec. `next` picks the set id itself, so generate the spec before creating
   the set directory (an existing empty directory would make it skip to the next id):
   ```bash
   python3 tools/ledger.py next COURSE --kind KIND --minutes N > /tmp/spec.json
   SET=$(python3 -c "import json;print(json.load(open('/tmp/spec.json'))['set'])")
   mkdir -p "<dir>/sets/$SET" && mv /tmp/spec.json "<dir>/sets/$SET/spec.json"
   ```
   Add `--date YYYY-MM-DD` when the user will sit the set on a later day than today, so
   that "not yet lectured" is judged for that day.
2. **Writer.** Spawn one agent with `model: "opus"`, in the foreground:
   > Read `prompts/writer.md` in the project root `<root>` and follow it. Course
   > directory: `<dir>`. Set id: `<SET>`. Kind: `<kind>`. Today is `<date>`; the final is
   > on `<exam date>`.

   The user decided that question-writing needs Opus; do not substitute a cheaper model.
3. **Checker.** Spawn one agent with `model: "sonnet"`:
   > Read `prompts/checker.md` in the project root `<root>` and follow it. Course
   > directory: `<dir>`. Set id: `<SET>`.
4. Save the checker's reply as `<dir>/sets/<SET>/check/verdict.md`.
   **Fix round, if the checker says `FIX NEEDED`.** Continue the writer agent with
   SendMessage: pass on the checker's fixes word for word, and tell it to apply them,
   recompile, and reply with the items it changed. Then spawn a fresh checker for the changed items
   only. At most two rounds. If an item still fails, have the writer remove it and
   rebalance the points, and tell the user the set is one item short and why. If the
   checker reports it could not settle who is right, do not guess: say so to the user
   and name the item.
5. Confirm the result is complete: `exam.pdf`, `key.pdf` and `set.json` exist in
   `<dir>/sets/<SET>/`, and `python3 tools/ledger.py checkset COURSE <SET>` passes.

## Held-out real exam

Only on the days the plan gives for it, or when the user asks. The files are in
`<dir>/holdout/`: list them with `ls`, open nothing. If it is empty, no exam was held out
for this course; say so and stop.

1. `SET=$(python3 tools/ledger.py newid COURSE holdout)`; `mkdir -p "<dir>/sets/$SET"`.
2. Spawn one agent with `model: "sonnet"`:
   > Read `prompts/holdout.md` in the project root `<root>` and follow it. Course
   > directory: `<dir>`. Set id: `<SET>`. Exam PDF: `<path>`. Official answers: `<path
   > or "in the same PDF">`.
3. Run the same completeness check as above.

## Hand over

Send the user `<dir>/sets/<SET>/exam.pdf` with SendUserFile and tell them, briefly:

- what this set is (kind, number of points, what it targets and why, from the spec);
- the time limit and the aids allowed, and that working it timed and closed-book is what
  makes the score mean something;
- that items marked "not yet lectured" can be answered with SKIP;
- for training sets: if they cannot see how to start an item, `/hint SET ITEM` gives
  the smallest hint that gets them going, never the solution. It is logged, scores as
  help, and brings that question type back in the next set. On paper: a circled H
  where they continue, and the timer paused while in chat. No hints on the held-out
  exam; on a full mock only after a warning;
- how to hand in: photos of every page, in order, into `<dir>/submissions/<SET>/`
  (under WSL give the Windows Explorer path too, as in the `grade` skill).
  Multiple-choice letters and the time they took can go in an `answers.txt` there, or in chat;
  Mathematica work as the `.nb` file. Then `/grade COURSE <SET>`.

Do not send or describe the key.
