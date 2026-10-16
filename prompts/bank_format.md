# Question bank format

The bank is the only form in which later agents (exam writers, checkers, graders) see the
past exams. They never open the PDFs. So a bank file must let someone reproduce the exam
question exactly, and the mathematics has to be right.

Per past exam, two files in `<CourseDir>/bank/`:

- `<EXAM_ID>.md` — the full transcription
- `<EXAM_ID>.index.tsv` — one line per gradable item

`EXAM_ID` is given to you in your task (e.g. `MATH-2024-04`, `MATH-2019-09-V1`).

## `<EXAM_ID>.md`

```markdown
---
exam_id: MATH-2024-04
source: MATH/materials/exams/2024-04-16 final.pdf
course_code: MATH201
sitting: final            # final | resit | midterm
date: 2024-04-16
duration_min: null        # only if the exam states it
total_points: 100
grade_formula: "points / 10"
aids: "equation sheet; no calculator, books or notes"
answers_available: final-answers-only   # full | final-answers-only | partial | none
---

## Rules
- 2–5 bullets with the cover-page rules that affect how to answer or how it is graded
  (aids, whether motivation is required, how the grade is computed). No other boilerplate.

## Problem 1 — Work Along a Helix (20 p)

Shared context of the problem, complete, with all math in LaTeX.

### 1.1 (5 p) · open

The question, complete and faithful.

- **Answer (official):** the official answer or solution as given in the source; `not provided` if absent
- **Grading (official):** only if the source gives a points breakdown or grading scheme
- **Topic:** 2–5 words
- **Skill:** one line: what the student must know or do to solve it
- **Figure:** only if the question relies on a figure: a description precise enough to redraw it
```

Multiple-choice items list every option on its own line as `- (a) ...`, and the correct
one ends with ` ✔` when the source reveals it. The format tag after the points is one of
`open`, `mc`, `mathematica-mc`, `proof`.

## `<EXAM_ID>.index.tsv`

Tab-separated, no header, one line per gradable item:

```
exam_id	item	points	format	topic	skill	answer_known
MATH-2024-04	1.1	5	open	line integral of a vector field	parametrise a curve and compute the work done by a vector field	y
```

`skill` is at most 15 words. `answer_known` is `y` or `n`.

## Fidelity rules

- Transcribe, do not paraphrase. Keep the original wording, symbols and numbering.
- All mathematics in LaTeX: `$...$` inline, `$$...$$` display.
- The PDF text layer scrambles formulas (fraction bars, integral limits, exponents and
  indices end up on separate lines). Use it for prose and structure; read the page image
  for every formula.
- Invent nothing. If something is illegible or cut off write `[[unclear: what you see]]`.
- If the source has an evident typo, transcribe it as printed and add `[[sic: ...]]`.
- Do not solve questions yourself. If the source has no answer, say `not provided`.
- If a question is restricted to certain study programmes, say so on the item's first line.
