# Preparing a held-out real exam

One real past final per course has been kept away from everyone: the student has not
seen it, and the agents that write practice sets were never shown it. The student now
sits it under exam conditions as a benchmark: it is the one score in this project that
is measured on a real exam, and it calibrates all the practice scores.

Your job is to turn that exam into a set the normal grading pipeline can handle,
without changing it.

Your task message names the course directory, the set id, and the PDF(s): the exam and,
if separate, its official answers.

## What to produce, in `sets/<SET>/` of the course directory

- `exam.pdf` — a copy of the original exam PDF, untouched. If the official answers are
  in the same PDF, copy only the exam pages (`pdfseparate`/`pdfunite` or `qpdf`), so the
  student does not scroll into the answers.
- `key.tex`, compiled with `tools/build_tex.sh` — per item: the question transcribed
  faithfully (format rules in `prompts/bank_format.md`: read page images for formulas,
  the text layer scrambles them), the official answer or solution, and
  `\rubric{points}{criterion}` lines summing to the item's points. Use the official
  grading scheme where the source has one. Where the source gives only a final answer,
  write out the worked solution yourself, verify the result against the official answer
  by computation (`wolframscript` or sympy), and say in the key that the points
  breakdown is yours. If your result disagrees with the official answer, say so
  prominently rather than choosing silently. Macros: `tools/tex/README.md`.
- `set.json` — schema in `tools/SPEC.md`. `kind` is `holdout`, every `level` is 2. Map
  each item to an archetype id from `blueprint.json`; use the closest one and mention in
  `variation` when the fit is loose. Item ids follow the exam's own numbering.

Do not copy anything from this exam into `bank/`, and do not edit the blueprint.

## Reply

For the orchestrating agent, under 150 words: number of items and total points, the
exam's stated duration and aids, how complete the official answers were, any
disagreement between your results and the official ones.
