# Exam prep with Claude

A study loop for university finals, run by Claude Code. You give it your course files
(past exams with answers, the study guide, the formula sheet, notes). It writes practice
sets in the style of your real exams; you work them on paper, timed; you hand in photos
of your pages; it grades them, tracks your mastery per question type, and aims the next
set at what went wrong.

```
/mock MATH    a checked practice set (PDF), in the style of the real exam
   you        work it on paper, timed and closed-book; photos into the course folder
/grade MATH   feedback PDF, key, progress report
/review SET ITEM   go through a mistake in chat, optionally as a short video
/hint SET ITEM     stuck mid-set: the smallest hint, never the answer
/status       where you stand, what to do today
```

Behind it: an Opus agent writes each set from an analysis of your past exams, a Sonnet
agent solves it blind to check the key before you ever see it, and another grades your
handwriting against the key. Scripts keep the scores, decide what the next set
practises, and build the progress report. One real past final per course is kept
unseen, for you to sit in the last week as an honest benchmark.

## Getting started

1. Install the software: **[SETUP.md](SETUP.md)** (Windows: through WSL; about 20
   minutes, mostly waiting). Or open the folder in Claude and ask it to set things up.
2. Open this folder in the **Claude desktop app** (Code tab; on Windows choose the WSL
   environment), and allow **Bypass permissions** mode (SETUP.md, "Permissions").
3. Type **`/start`**. It checks the installation, explains the project, asks about your
   courses and exam dates, tells you where to put your files, builds each course, and
   writes a day plan.

You need a Claude Pro or Max plan. Setting up a course uses roughly one 5-hour usage
window on Pro; a practice set about a quarter of one. The guide has the numbers.

## What is where

- `guide/usage.pdf`: the user guide (commands, conventions, how it adapts, what it costs).
- `courses.md`: your courses, exam dates, plan (written by `/start`).
- `<course>/materials/`: the files you drop in. `<course>/sets/`, `submissions/`,
  `feedback/`: the practice sets, your photos, the grading.
- `prompts/`, `tools/`, `.claude/skills/`: how it works. `CLAUDE.md` is what Claude reads
  first.

Your course files, work and grades stay on your computer. `.gitignore` keeps them out of
git, so the project can be shared or updated without them.

## A new quarter

`/start new-quarter` moves the old courses to `archive/` and sets up the new ones. Or
start again from a fresh copy of this folder.
