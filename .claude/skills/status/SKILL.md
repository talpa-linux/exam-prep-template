---
name: status
description: Show where the user stands in exam prep (all their courses) - rebuild the progress PDF, summarise mastery and predicted grades, and say what to work on today. Use when the user asks how they are doing, what to do next or today, or wants the progress report.
---

# /status

Read `CLAUDE.md` first if you have not.

```bash
python3 tools/ledger.py status
python3 tools/build_report.py
```

Send `progress/progress.pdf` with SendUserFile, then tell the user in a few lines:

- per course: days and study days left, sets done, the grade figures from `status`
  (say what share of the exam they are measured on; a grade measured on a third of the
  exam is not a prediction yet);
- any set that was handed out but not yet graded;
- what the plan table in `courses.md` has for today, adjusted for reality: if they are
  behind, say which sets to prioritise. The earliest exam comes first, and within a
  course the weakest heavy archetypes (`python3 tools/ledger.py mastery COURSE`).

Do not open feedback files, keys or bank files to answer; the script output is enough.
If the user wants to go through a specific mistake, that is a tutoring question: answer
it from `<dir>/feedback/<SET>.tex` for that one item only.
