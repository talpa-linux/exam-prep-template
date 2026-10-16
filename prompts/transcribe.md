# Transcribing past exams into the bank

The bank is the only form in which the later agents see a course's past exams: the
blueprint writer analyses it, exam writers match its form and level, checkers search it
for repeats. They never open the PDFs. A transcription error here quietly propagates
into every practice set, so fidelity matters more than speed.

Your task message names the course directory and a list of exams, each with its
`exam_id`, the exam file and the answers (a separate file, `same` if they are in the exam
PDF, or `none`). Follow `prompts/bank_format.md` (project root) exactly: it defines the
two files per exam and the fidelity rules.

## How to work

- One exam at a time, in the order given. Write both files of an exam before you start
  the next, so that an interruption keeps the finished ones. If both files of an exam
  already exist and look complete, skip it and say so.
- Read the pages themselves: open the PDF with the Read tool a few pages at a time (the
  `pages` parameter). Use `pdftotext -layout` only for long prose; it scrambles formulas.
  A scanned exam has no text layer at all.
- Separate answers file: put each item's official answer or solution under that item.
  Where the answers give a points breakdown, copy it into **Grading (official)**.
- Keep the exam's own language for the questions and answers. Write **Topic** and
  **Skill** (and the index columns) in English, so the bank can be searched across years.
- Figures: describe them precisely enough to redraw (axes, labels, the curve's shape,
  given values). Tables: as Markdown tables.
- Do not open anything in the course's `holdout/` folder, and no exam not in your list.
- Check each finished file once: every item of the paper is present, the points add up
  to the stated total, and the index has one line per gradable item.

## Reply

For the orchestrating agent, under 150 words: one line per exam (id, items, total
points, answers full/partial/none, number of `[[unclear]]` spots), and anything a later
agent should know (a predecessor format, a study-programme split, an exam that seems to
belong to another course).
