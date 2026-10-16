---
name: start
description: Set up this exam-prep project for a new user, a new course or a new quarter - check and install the software, explain how the project works and which app settings it needs, add the user's courses, and build each one from the user's files (sort the materials, transcribe past exams, syllabus, blueprint, day plan). Use when the user says /start, is new here, asks how to begin or what this project does, wants to add a course, or starts a new quarter or semester. Running it again continues where it stopped.
---

# /start [add | new-quarter]

Gets a new user from an empty project to their first practice set, and later adds a
course or clears the slate for a new quarter. Read `CLAUDE.md` first if you have not.

You are the orchestrator here as everywhere: scripts check and record, agents read the
course files, and you do neither yourself. Do not open the user's PDFs, notes or
exams; the intake agent says what they are. Keep messages short and ask one thing at a
time unless the questions belong together.

## Where are we?

```bash
python3 tools/doctor.py --quick
python3 tools/course.py list
```

- No courses yet: the full onboarding, sections 1 to 6 in order.
- Courses with set-up steps still to do: say where things stand in two lines, then
  continue at section 5 with the course whose final is earliest.
- Everything set up and no argument: one line per course from `list`, then ask what
  they want: add a course (`add`), start a new quarter (`new-quarter`), or go on with
  `/mock`.
- `add`: sections 4 to 6 for the new course. `new-quarter`: section 7, then 4 to 6.

## 1. What this is

Send `guide/usage.pdf` with SendUserFile (the user's guide, five pages) and explain in
a few lines:

- the loop: `/mock` writes a checked practice set in the style of their real exams;
  they work it on paper, timed and closed-book; they put photos of the pages in the
  course folder; `/grade` grades it, records the scores and sends a feedback PDF and the
  progress report; `/review` goes through a mistake in chat; the next set is aimed at
  what went wrong. `/hint` gets them unstuck mid-set; `/status` says what to do today;
- what you need from them now: a few facts per course and the course files;
- what set-up costs: per course about a dozen agent runs that read their materials.
  On a Pro plan that is roughly one 5-hour usage window per course, so courses are
  built one at a time, earliest exam first, and the set-up can stop and resume.

## 2. Software

Read the doctor output.

- `operating system` failed (native Windows): the project runs inside WSL 2 on
  Windows. Point them to the Windows section of `SETUP.md` and stop here; they reopen
  the project in a WSL session afterwards.
- Something under `core` missing: give the `sudo apt ...` line the doctor printed, in
  a bash code block, for the user to run in their own terminal (on Windows: the Ubuntu
  app; WSL sessions of the desktop app have no terminal pane). Never run `sudo`
  yourself and never ask for or type a password. Non-root steps (a `pip install
  --user`, a check) you may run yourself. When they say it is done, run the doctor
  again, until `core` is complete.
- Optional parts: ask once whether they want the review **videos** (needs the `for
  videos` apt line; the Manim environment then installs itself on the first video,
  about 500 MB) and, only if a course has a Mathematica part, **Wolfram Engine** (free
  for personal use; they download it and activate it with their own Wolfram ID, see
  `SETUP.md`). Both can be added later.

## 3. App settings

Tell them what to set in the Claude desktop app, and why. Confirm each with them; you
cannot check them yourself.

- **Permission mode: Bypass permissions** in the mode selector of this folder (the
  desktop app remembers it per folder). Every skill runs scripts and agents; without
  it the user approves dozens of commands per set. It must first be allowed: Settings →
  Claude Code → "Allow bypass permissions mode" (Pro and Max; on Team and Enterprise
  plans the organisation decides). A project setting cannot switch it on. What it
  means: Claude runs commands in this session without asking, so use it for this
  project only. If they prefer prompts, Auto mode asks rarely, and Manual asks for
  every command.
- **Model**: Opus for the main session. It is the orchestrator; the skills choose the
  agents' models themselves (Opus writes sets, Sonnet checks and grades). A long
  `/review` thread on Sonnet costs about half per message.
- **Notifications** on: writing and checking a set takes 10 to 30 minutes, grading 5
  to 10, and the app can tell them when it is done.
- **Getting files in** (Windows): the project lives in Ubuntu, and Windows Explorer
  reaches it at `\\wsl.localhost\<distro>\...` (`echo $WSL_DISTRO_NAME` and `pwd` give
  the two parts; write the path with backslashes). Suggest pinning it to Quick access.
  Photos and course files go into folders, never pasted into the chat: pasted images
  are read by the expensive main session and the grader cannot see them.
- **One session per task**: a long thread re-reads its whole history on every
  message. A new session for each set, grading or review is cheaper.

## 4. Courses

Ask, in one message, for each course: the full name with its code; the date of the
final (and the time, if they know it); the other parts of the grade with their weights
and the grades already earned (a midterm, homework, a lab, a computer test), and the
pass rules (the overall pass grade, a minimum for the final itself). Also ask for their
study days per week and roughly how many hours a day, and which past exams they have
already worked through (those make poor benchmarks).

The project grades on a 0 to 10 scale. If their university uses another one, agree on
the conversion with them (a percentage divided by 10) and note it in `courses.md`.

Then, per course, propose a short key (2 to 8 capitals: `MATH`, `QM1`) and a folder
name, and run:

```bash
python3 tools/course.py add KEY --name "Full name (CODE)" --exam-date YYYY-MM-DD --dir "Folder"
python3 tools/course.py study-days Tue Wed Thu
```

Tell them where the files go, `<dir>/materials/` (on Windows also the Explorer path),
in any sub-folders and with any names, and what helps, most useful first:

1. **past exams**, as many as they can find, each with its answers or solutions;
2. the **study guide** or course manual with the exam rules, and the lecture
   **schedule** with dates;
3. the **formula sheet** allowed in the exam;
4. **lecture notes**, slides or the book chapters in scope;
5. **exercise sets** with solutions;
6. for a computer part: the course's notebooks or manual.

Three or more past exams make a good course. With fewer, the sets lean on the syllabus
and the exercises and match the real exam less well: say so plainly. Then wait until
they say the files are in.

## 5. Build each course

One course at a time, earliest final first, one agent at a time. Before starting a
course, say in one line that this is the expensive part (about a usage window on a
Pro plan) and that it resumes if interrupted. Then loop: run
`python3 tools/course.py state KEY` and do its `next` step, until it says `set-up
complete`. After every agent, run `state` again rather than trusting the reply. If an
agent is cut off (usage limit, closed app), continue it with SendMessage when the user
is back; finished files are on disk and are not redone.

- **materials**: wait for the files.
- **intake**: spawn one agent with `model: "sonnet"`:
  > Read `prompts/intake.md` in the project root `<root>` and follow it. Course key:
  > `KEY`. Course directory: `<dir>`. Past exams the student has already worked:
  > `<their answer, or "unknown">`.

  Show the user its summary: files per role, the exams (id, sitting, answers yes/no),
  what looks missing. Ask them to correct anything wrong; fix `intake.json` with the
  agent (SendMessage) and run `python3 tools/course.py check-intake KEY`. If something
  important is missing (no answers at all, no formula sheet), say what it costs and
  whether to wait for it.
- **holdout**: explain in two lines: one real final is set aside unseen; they sit it
  in the last week as `KEY-H01` under exam conditions, and it is the one honest
  measure of where they stand; the price is one exam less for practice. Propose the
  agent's candidate (not one they have already worked) and ask: that one, another, or
  none. Then `python3 tools/course.py holdout KEY "<exam file>" "<answers file>"`, or
  `python3 tools/course.py holdout KEY --none`.
- **bank**: `state` lists the exams still to transcribe. Spawn agents with `model:
  "sonnet"` one after another, two or three exams each (one for a long one, about 25
  pages per agent at most):
  > Read `prompts/transcribe.md` in the project root `<root>` and follow it. Course
  > directory: `<dir>`. Exams: `<id>`: exam `<path>`, answers `<path | same | none>`; ...

  Paths and ids come from `intake.json`.
- **syllabus** (also writes the formula sheet): one agent with `model: "sonnet"`:
  > Read `prompts/syllabus.md` in the project root `<root>` and follow it. Course key:
  > `KEY`. Course directory: `<dir>`.

  If `formula_sheet` is still open afterwards, ask the same agent for it with
  SendMessage.
- **toolkit** (only for a Mathematica course): the same with `prompts/toolkit.md`.
- **seeds**: the same with `prompts/seeds.md`.
- **blueprint**: one agent with `model: "opus"` (the blueprint decides what every set
  practises, so it gets the strongest model):
  > Read `prompts/blueprint.md` in the project root `<root>` and follow it. Course
  > directory: `<dir>`.

  Check with `state` and `python3 tools/ledger.py mastery KEY`. Show the user the
  archetype table in short (the question types and their weights) and its open
  questions; ask the ones only they can answer (this year's exam format, a topic the
  lecturer said will not be examined). If their answers change something, send them
  to the blueprint agent with SendMessage and check again.
- **pass_mark**: work out the grade the final itself must reach, from what they told
  you in section 4. With components of weight wᵢ and grades cᵢ, a final of weight w,
  an overall pass grade P and a minimum m for the final:

  $$
  \text{bar} = \max\left(m,\ \frac{P-\sum_i w_i c_i}{w}\right)
  $$

  For a component still to come, use the grade they expect and say so. Show them the
  numbers, then
  `python3 tools/course.py pass-mark KEY <bar> --why "<components and rule, one line>"`.

When a course is complete, run `python3 tools/build_report.py`, and go on to the next
course, or stop for today if the usage window is nearly spent (say how far it got).

## 6. The plan and `courses.md`

When the courses are built (or at least the first one), write `courses.md` in the
project root, in this form:

```markdown
# Courses

| Key | Folder | Course | Final | The final must reach |
|---|---|---|---|---|
| MATH | `MATH/` | Multivariable Calculus (MATH201) | Fri 30 Oct 2026 | 5.0 (homework 8.0 counts 20 %) |

Study days: Tue, Wed, Thu, about 8 hours a day. Grades on a 0-10 scale.

## Held-out exams

- MATH: `MATH/holdout/` (final of January 2025, with answers), sat as MATH-H01.

## Plan

| Day | MATH | MECH |
|---|---|---|
| Wed 14 Oct | D01 diagnostic | |
| Thu 15 Oct | T01 | D01 diagnostic |

## Notes

- What the user told you that matters for planning or grading.
```

The plan covers each study day from today to the last final. Rules of thumb:

- per course: the diagnostic `D01` first; training sets `T01, T02, ...` on most days; one
  full mock `F01` about two thirds of the way; the held-out exam `H01` two or three study
  days before the final, so the result can still be acted on; the last study day before
  the final for last fixes and the mistake book;
- the earliest final gets priority on shared days; at most two sets per course and three
  sets in total on one day (a set is 1.5 to 3 hours of work, plus grading and review);
- no course goes more than one study day without a set in its last two weeks.

Show the plan, adjust it to what they say, save it, then run
`python3 tools/build_report.py` and send `progress/progress.pdf`. End with the next
step: `/mock KEY` for the earliest final makes its diagnostic set.

## 7. A new quarter

The old courses move to `archive/`; nothing is deleted. Confirm which courses to
archive (by default all) and a label (for example `2026-Q1`), then per course:

```bash
python3 tools/course.py archive KEY --label 2026-Q1
```

and move `courses.md` and `progress/progress.pdf` into `archive/2026-Q1/` too. Then
carry on with section 4. Mention that a fresh copy of the template folder is an
alternative, if they want the new quarter's project completely separate.
