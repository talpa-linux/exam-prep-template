# Writing a course's syllabus and formula sheet

Every later agent works from what you write here instead of the course materials: the
blueprint writer takes this year's scope and exam rules from it, the script that picks
each practice set takes the lecture dates from it (so nothing is asked before it has
been taught), exam writers take the course's notation and conventions from it, and
graders take the grading rules. A convention you get wrong (a Fourier normalisation, a
sign, which basis vectors) trains the student wrong on every set.

Your task message names the course key and directory. `<dir>/intake.json` says what each
file in `materials/` is.

## What to read

- Files with role `course_info` and `schedule`: read them fully.
- `formula_sheet`: read every page as an image (the Read tool on the PDF, with `pages`);
  its text layer scrambles formulas.
- `notes` (lecture notes, slides, book chapters): do not read them cover to cover. Use
  `pdftotext` to get the table of contents and headings, then read the pages where
  definitions, conventions and notation are fixed, and enough of each chapter to say
  what it covers. Aim at well under 150 pages of actual reading.
- `exercises`: titles and the topics they cover, from their first page or headings.
- `bank/*.index.tsv`, if the past exams are already transcribed: which topics past
  exams ask, so you can say what this year adds or drops. Do not open the exam PDFs and
  never open anything in `holdout/`.

## What to write

**`<dir>/syllabus.md`**, with these sections:

1. **Sources.** Which files you used and what each is; what seems missing (no schedule,
   no formula sheet, notes for only part of the course).
2. **Exam facts this year.** Date, duration, format (open questions, multiple choice, a
   computer part), aids allowed, how the grade is computed (points to grade), the
   components and their weights (a midterm, a lab, homework), minimum grades, rules that
   cost points ("no points without motivation", "exact answers only"). Quote the source
   for each. Separate what is stated from what you infer.
3. **Schedule.** One line per lecture or week with its date (YYYY-MM-DD) and topics,
   including what is still to come. This is where `covered_from` dates come from, so
   give dates, not week numbers, wherever the material allows.
4. **Conventions and notation.** Exactly as the course uses them: symbols, sign and
   normalisation conventions, coordinate systems and basis vectors, units, how answers
   are expected (exact or decimal, which form). Give a formula wherever a convention is
   a formula.
5. **Scope, chapter by chapter.** Per chapter or block of the notes: what it covers,
   which sections are in or out of the exam, page ranges.
6. **The formula sheet.** What it gives and, just as useful, what it does not give and
   the student must know by heart.
7. **Notes for exam writers and graders.** Anything that changes how a question should
   be written or graded: no calculator so numbers must come out clean, a computer part,
   a language, typical lecturer phrasing.
8. **Open questions.** What you could not settle from the materials and the student
   could check on the course page.

**`<dir>/formula_sheet.md`**, if there is a formula sheet: a faithful transcription,
section by section, all mathematics in LaTeX (`$...$`, `$$...$$`), in the sheet's own
order and wording. Invent nothing; mark illegible spots `[[unclear: ...]]`. If the exam
allows no sheet, write no file and say so in the syllabus.

Write the syllabus as you go, section by section, so an interruption keeps what is done.

## Reply

For the orchestrating agent, under 200 words: the exam facts in three lines (duration,
format and aids, grading and components); how far the lectures are and when the last
topic is taught; the two or three conventions most likely to trip a writer; what is
missing and the open questions.
