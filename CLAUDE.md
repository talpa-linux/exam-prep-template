# Exam prep

The user is preparing for university finals by working exam-style practice sets, handing
in photos of handwritten work, and getting it graded. This project automates that loop:
write a set → the user works it → grade it → update mastery → write the next set aimed
at what went wrong.

The user's own courses, exam dates, study days, banked grades and day plan are in
`courses.md`, imported here:

@courses.md

If `courses.md` does not exist or `tools/config.json` has no courses, the project is not
set up yet: say so and suggest `/start`, which installs and checks what is needed,
explains the project, and sets up the user's courses.

## How the loop runs

Six skills drive everything: `/start` once per course, then `/mock`, `/grade`, `/review`,
`/status`, and `/hint` while a set is being worked. They spawn helper agents with the
prompts in `prompts/` and call the scripts in `tools/`. The session that runs a skill is
the orchestrator: it reads short agent replies and script output, and passes files
along. It does not do the reading, writing or grading itself.

| Job | Who | Prompt |
|---|---|---|
| Sort a course's materials, transcribe past exams, write syllabus, seeds, formula sheet | Sonnet agents | `prompts/intake.md`, `transcribe.md`, `syllabus.md`, `seeds.md`, `toolkit.md` |
| Analyse the past exams into a blueprint | Opus agent | `prompts/blueprint.md` |
| Write a practice set and its key | Opus agent | `prompts/writer.md` |
| Solve the set blind and check the key | Sonnet agent | `prompts/checker.md` |
| Transcribe and grade a submission | Sonnet agent | `prompts/grader.md` |
| Hint on one item of a set still being worked, on request | `/hint` session; `tools/hints.py` logs it | `.claude/skills/hint/SKILL.md` |
| Lesson (mini-course) on one question type, on request | Sonnet agent | `prompts/lesson.md` |
| Video of one item: the user's lines, the error, the fix, on request | `/review` session writes a storyboard, `tools/animate.sh` renders it | `prompts/storyboard.md` |
| Prepare a held-out real exam | Sonnet agent | `prompts/holdout.md` |
| Mastery, next-set spec, progress PDF, course set-up, install check | scripts in `tools/` | `tools/SPEC.md` |

Why this split: expensive models plan and write questions, cheaper ones do the volume
work, and scripts do everything that needs no judgement. The main session is the
expensive one, so it stays an orchestrator: it never reads past-exam PDFs or photos
itself, and hands reading, writing and grading to agents with a cheaper `model`.

## Rules that protect the user

- **Keep source material out of the orchestrator's context.** Do not Read exam PDFs,
  course materials, submission photos, bank files or keys in the main session; agents do
  that and report back in a few lines. It keeps every session cheap and long-lived. The
  exceptions are `/review` and `/hint`, which load one item through a script and nothing
  more. If the user pastes photos of their work into the chat, ask them to put the files
  in the submission folder instead next time (see `/grade`).
- **Held-out exams stay unseen.** One real final per course is reserved as a benchmark
  the user sits in the last week. It lives in `<dir>/holdout/`. Only the holdout
  procedure (`/mock COURSE holdout`) may open anything there. Intake, transcribers,
  blueprint writers, writers and checkers never do, and nothing from it goes into
  `bank/` or a blueprint.
- **No set reaches the user unchecked.** A set is handed over only after the checker has
  passed it. A wrong key teaches something false.
- **Never show a key before the submission is graded.** `/hint` reads one item's key
  only to aim its hint. It gives at most the first step (the set-up), never a result, and
  logs every hint in `<dir>/submissions/<SET>/hints.json`. The grader scores only the
  work done without the hint, `ledger.py record` refuses feedback that credits it, and the
  next training set re-tests that question type first. No hints on a held-out exam.
- **Sets are written only on the user's command.** Only an explicit `/mock` (or a direct
  request for a set) starts a writer. No other skill or step does it on its own: after
  grading, stop at the report and name the next planned set and its day.
- **Scores come from the grader's JSON through `tools/ledger.py record`.** Do not edit
  `ledger.jsonl` by hand or restate scores from memory.
- **Few agents at a time.** Claude plans have a usage limit per 5-hour window, and
  hitting it stalls a study day (a fan-out of many agents reading PDFs in parallel can
  burn a whole window in minutes). Run one agent at a time, two at most, the earliest
  exam's work first. Tell agents to write their output files as they go, and resume an
  interrupted agent with SendMessage rather than starting a fresh one.
- **Installing software.** Follow `SETUP.md`. Never type a password: a command that
  needs `sudo` is given to the user to run in their own terminal.

## Maths in chat

The desktop app and the iOS app both render `$...$` and `$$...$$`; only the desktop app
renders `\(...\)` and `\[...\]`. The desktop app reads `_` and `*` as Markdown italics
before it sees the maths, so an inline formula with subscripts or complex conjugates can
break there (seen with `$\hat a_\pm$` in a paragraph with other subscripts). So, in every
chat reply:

- Equations, and any expression with a subscript `_`, a conjugate or other `*`, a
  fraction or more than a few symbols, go on their own lines as display maths, with a
  blank line before and after:

  $$
  \hat a_\pm=\frac{1}{\sqrt{2\hbar m\omega}}\left(\mp i\hat p+m\omega\hat x\right)
  $$

- Inline `$...$` only for short fragments without `_` or `*`: `$\hat x$`, `$\omega$`,
  `$x^2$`, `$\hbar$`, `$e^{-iEt/\hbar}$`. For short subscripted or starred symbols
  inside a sentence use Unicode instead: ψₙ, ψ*, â₊, â₋, E₁, V₀, ⟨x⟩.
- Never `\(...\)` or `\[...\]`, and never maths in backticks or code blocks unless the
  user asks for LaTeX source.
- Never paste or write the exam's own macros in chat. `exam.tex`, `key.tex` and the
  output of `tools/hints.py open` and `tools/item_context.py` are raw LaTeX with
  per-set macros (`\vv`, `\ex`, `\pe{r}`, `\bm{...}`, `\subq`, `\problem`, ...) that chat
  does not define, so they show as red errors. Translate to plain LaTeX when quoting:
  `\vv` → `\mathbf v`, `\ex` → `\mathbf e_x`, `\pe{r}` → `\mathbf e_{(r)}`,
  `\bm{x}` → `\mathbf x`. If unsure what a macro means, grep its `\newcommand` in the
  set's `exam.tex` preamble.

## Layout

```
README.md, SETUP.md   what this is; how to install it (also for agents)
courses.md            the user's courses, exam dates, held-out exams, plan (written by /start)
prompts/              agent prompts (intake, transcribe, bank_format, syllabus, seeds, toolkit,
                      blueprint, writer, checker, grader, holdout, lesson, storyboard)
tools/                config.json (courses; written by course.py), course.py (set-up and archive),
                      doctor.py (install check), ledger.py, build_report.py, usage_report.py,
                      build_tex.sh, prep_photos.sh, tex/prep.sty, hints.py (the /hint log),
                      item_context.py + select_review.py (for /review),
                      animate.sh + animate.py (Manim; venv in ~/.local/share/exam-prep-anim)
progress/progress.pdf the one progress report, rebuilt after every grading
guide/usage.pdf       the user guide: skills, inner workings, what each costs (from usage.tex;
                      update it when a skill changes)
archive/              courses of earlier quarters, moved here by `course.py archive`
<dir>/                one per course, named in tools/config.json
  materials/          what the user dropped in: past exams, answers, study guide, notes, sheets
  holdout/            the reserved real final (and its answers): unseen until the holdout
  intake.json         what each file in materials/ is (from the intake agent)
  bank/               past exams transcribed (index.tsv maps items to archetypes)
  blueprint.md|json   exam format, archetypes, weights, variation axes, pitfalls
  syllabus.md, seeds.md, formula_sheet.md (or equation_sheet.md), mathematica_toolkit.md
  sets/<SET>/         spec.json, exam.tex|pdf, key.tex|pdf, set.json, check/
  submissions/<SET>/  the user's photos, answers.txt, notebooks, hints.json (from /hint)
  feedback/<SET>.*    grader output
  lessons/<id>.*      mini-course per archetype, written on request
  animations/<SET>_<ITEM>.json|mp4  storyboard and video of one reviewed item
  ledger.jsonl        every graded item
```

Set ids: `<KEY>-D01` diagnostic, `-T01…` training, `-F01…` full mock, `-H01` held-out exam.

## How the user learns from a set

While working a training set, if they cannot see how to start an item: `/hint SET ITEM`
gives the smallest hint that gets them going (nudge, then method, then set-up) and logs
it. On paper they write a circled H where they continued and pause the timer.

After grading:

1. Feedback PDF: the overview of what scored and what did not.
2. `/review SET ITEM` in chat for the items worth going over: the session loads that one
   item (question, the user's transcribed work, grading, key, pitfalls) with
   `tools/item_context.py` and tutors, with follow-ups in the same thread.
3. On request, a short video of one item from `/review`: their own lines appear one at a
   time, the wrong term is boxed with the reason, then it rewinds and continues correctly.
4. A lesson PDF on a question type only when the user wants one.
5. The next training set re-tests the same types in a new guise: that is the proof.

## Plan

The day plan in `courses.md` is a guide, not a contract: `tools/ledger.py next` decides
the content of each set from the results so far.
