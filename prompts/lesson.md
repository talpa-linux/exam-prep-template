# Writing a lesson for one question type

A student preparing for a university final has just failed a type of exam question
(an "archetype") not through a slip, but because they did not understand the idea or
did not know how to start. Practising more questions will not fix that; they need to be
taught. You write that teaching: a short, self-contained mini-course on one archetype
that takes them from "no idea how to attack this" to "I can do the exam version", and
that they will reread before the exam.

Your task message names the course directory and the archetype id(s), and may quote
what the student got wrong.

## Sources

In the course directory:

- `blueprint.md`, the section for the archetype: what is always asked, the difficulty
  ladder, the pitfalls, the past occurrences.
- `bank/` (past exams with official answers; `bank/index.tsv` maps items to archetypes)
  and, if present, `bank/exercises/` (the lecturer's exercises with solutions).
- `syllabus.md` for the course's definitions, conventions and notation, and the
  equation or formula sheet the student may use in the exam.
- `mathematica_toolkit.md`, if the archetype is solved in Mathematica.
- `tools/tex/README.md` in the project root for the LaTeX style.

Do not open any PDF in the course directory, and do not use anything from
`sets/*/key.tex` of a set the student has not yet handed in.

## What the lesson must do

Teach at the level of a student who could not start the problem. Do not assume the idea
is known because it was lectured. Build it up, in the course's own notation and
conventions, so that what they read matches what they see on the exam.

1. **What this question looks like.** How it appears on the exam, the phrases and
   givens that signal it, typical points. One short paragraph.
2. **The idea.** The concept explained from the ground up: what the objects mean
   physically or geometrically, why the method works, the formulas that matter (cite the
   equation-sheet entry where there is one). Intuition first, then the formal statement.
3. **The recipe.** The solution method as numbered steps, each saying what to do and
   how to know it is done right.
4. **Worked example, simple.** A fully worked instance below exam level, with the
   reasoning behind every step written out ("we integrate by parts here because…").
5. **Worked example, exam level.** A real past exam item of this archetype from the
   bank, fully worked in the same style, with its points breakdown so the student sees
   what earns marks.
6. **Traps.** The pitfalls from the blueprint and any others you know, each with how the
   student can catch it during the exam (a check on units, a limit case, a symmetry,
   a sanity bound).
7. **Practice.** Three problems of increasing difficulty, ending at exam level, new
   rather than copied from the bank. Short solutions at the end of the document, after
   a page break, so the student can try first.
8. **Exam card.** A boxed half-page summary: when to use it, the recipe, the traps. This
   is what they will reread the night before.

Length: whatever the idea needs, typically 3 to 6 pages. Clarity over completeness:
leave out side topics that do not serve this archetype.

Verify every result you state, in examples and practice solutions, with
`wolframscript -code '...'` or Python/sympy. A lesson that teaches a wrong result does
more harm than no lesson.

## Deliver

`lessons/<archetype-id>.tex` in the course directory (create `lessons/`), using
`\usepackage{prep}`, compiled with `tools/build_tex.sh`. Put `\preptoc` (a clickable
contents list) right after `\prepheader`, and use `\section` for the eight parts so they
appear in it. One file per archetype.

## Reply

For the orchestrating agent, under 100 words per lesson: what the lesson covers, which
past exam item you worked, what you verified by computation, anything you were unsure of.
