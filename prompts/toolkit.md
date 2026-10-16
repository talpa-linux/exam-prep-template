# Writing a course's Mathematica toolkit

Some courses have a part of the exam done in Mathematica, often multiple choice
(`mathematica-mc` in this project): the student computes the answer in a notebook and
picks the option. Exam writers then have to solve their own questions in Mathematica,
using only what the course teaches, and graders read the student's `.nb` file. Both work
from your toolkit, so they know which functions and idioms the course uses and what an
idiomatic solution looks like.

Your task message names the course key and directory. `<dir>/intake.json` lists the
`software` files (notebooks, a Mathematica manual or overview) and `course_info`. The
bank (`bank/*.md`, items with format `mathematica-mc`) shows what past exams asked. Do not
open past-exam PDFs or anything in `holdout/`.

## How to read notebooks

A `.nb` file is plain text. The Input cells hold the code: search for
`Cell[BoxData[` ... `"Input"` and read those, not the whole file (output cells can be
huge). If `wolframscript` is installed, check every snippet you write by running it
(`wolframscript -code '...'`).

## What to write

`<dir>/mathematica_toolkit.md`:

- **Part A. The course's notebooks, one by one:** the functions and idioms each
  teaches, with a minimal working example of each.
- **Part B. The idiomatic pattern** for each kind of computer question in the bank or
  the course materials: the code a well-prepared student would write, step by step.
- **Part C. Files:** each notebook and what it covers.
- **Part D. Notes for exam writers and graders:** what the exam allows (own notebooks,
  documentation), version pitfalls, common mistakes, and how an answer is read from the
  output.

## Reply

For the orchestrating agent, under 150 words: the kinds of computer questions, the core
functions, whether you could run the snippets, and anything a writer must avoid.
