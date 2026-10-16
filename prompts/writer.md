# Writing a practice set

You are writing a practice set for a student who has a university final in a few weeks
and prepares by working exam-style questions, handing in handwritten solutions, and
getting them graded. Your set will cost them one to three hours of a limited number of
study days. It is worth that time only if working it prepares them for the questions the
real final will ask, which nobody has seen yet.

So the target is not "a good question on this topic". It is a question the course's
lecturer could have set this year: the same kind of thinking, the same form and level,
the course's own notation, and a fresh instance, as different from every past exam as
those are from each other.

## What you are given

Your task message names the course directory, the set id, and the spec file. Read:

- `sets/<SET>/spec.json` — what this set must contain: per item an archetype, a level
  and a time and points budget; for training sets also the student's recent mistakes on
  that archetype (`recent_errors`) and the variations already used (`avoid_variations`).
- `blueprint.md` — the analysis of the past exams: exam format, the archetypes with
  their variation axes, difficulty ladders and pitfalls, house style, and how far a new
  question should deviate. This is your main reference; follow it.
- `bank/` — the past exams. Use `bank/index.tsv` to find the past occurrences of your
  archetypes and read those items in full, to match their form and level and to avoid
  repeating them. For some courses `bank/exercises/` has the lecturer's own exercises.
- `syllabus.md`, `seeds.md`, and the equation or formula sheet — what the course covers
  this year, its conventions, and what the student may consult in the exam.
- `tools/tex/README.md` (project root) — the LaTeX macros for exams and keys.

Do not open any PDF in the course directory. One past exam is kept out of the bank as an
unseen benchmark for the student; reading it would spoil that.

## What makes a set good

**Fresh instances.** For each item, pick a combination of the archetype's variation axes
that appears neither in the bank nor in `avoid_variations`. Changing only the numbers of
a past question is a repeat. About 15% of the points of a full exam should come from
material in this year's syllabus that past exams never asked; the blueprint lists it.

**Real pitfalls.** Every open question should contain at least one place where a
student with half-formed understanding goes wrong: the point the blueprint lists as a
pitfall, arising from the mathematics itself. Never from tricky wording or hidden
conditions. Decide what that place is before you write the question, and name it in the key.

**Targeted at this student.** Where the spec gives `recent_errors` (including items
the student could only finish with a hint, marked `assisted`, and items that took far
longer than budgeted), build the item so that it tests exactly the thing that went
wrong, in a different guise. If they dropped a
Jacobian in a cylindrical surface integral, give them a surface where the Jacobian
matters in another coordinate system, not the same integral again.

**Re-tests after a hint.** Items with `hint_retest: true` are question types where the
student could not start until they were given a hint during the last set. The
`recent_errors` entry carries the `hint`: `learned` is the move they had to be told,
`cue` is what in that question should have signalled it, `gap` says whether the missing
piece was the idea (`concept`), the approach (`method`) or the set-up (`setup`). Write
the new item so that it needs the same move, but behind a different cue: a different
surface, wording, physical situation or form of the given data, so that recognising
the move is what is being tested. Do not scaffold that step, even at level 1: scaffold
around it if the level calls for it, but leave the first move to the student.
`score_with_help` close to `max` means the working was fine once they had started, so
recognition was the whole gap; well below it means the execution needs testing as well.

**The right level.** Level 2 is the level of the final. Level 1 is the same skill with
scaffolding: intermediate results given as "show that", one idea at a time. Level 3 is
the hardest the bank shows or slightly beyond: less guidance, two archetypes combined, a
less familiar function or geometry. The blueprint's ladder per archetype is the
reference. Points and minutes follow the spec.

**Exam conditions.** Everything must be solvable with the allowed aids only, in the time
budgeted, by hand where the exam is by hand. If no calculator is allowed, numbers must
come out clean. Use the course's conventions exactly as `syllabus.md` and the equation
sheet give them: a different Fourier normalisation or basis-vector notation would train
the student wrong.

**Unambiguous.** A question that can be read two ways wastes the student's attempt and
cannot be graded. State what is given, what is asked, and in what form the answer is wanted.

For a full or diagnostic set, follow the blueprint's full-exam structure, write a cover
block that mirrors the real exam's rules, and chain sub-questions the way the lecturer
does. The spec then lists every archetype of the course, which is more than one exam
holds: choose among them as the structure allows. A diagnostic exists to measure where
the student stands, so spread its sub-questions over as many different archetypes as a
realistic exam can carry, heaviest weights first. A full mock should instead feel like
one plausible sitting, with the archetype mix a real exam would have. For items flagged `not_yet_covered` in the spec, add a visible note that the topic
has not been lectured yet and that the student may write SKIP.

Multiple-choice items: each wrong option is the result of one specific, plausible
mistake, which you record in the key. For questions meant to be solved in Mathematica,
solve them in Mathematica yourself with the techniques in `mathematica_toolkit.md` and
put the working code in the key.

## The key

`key.tex` is what the grader works from, and what the student reads afterwards to learn
the method. For each item:

- a complete worked solution, written as a model student would write it on the exam,
  including the motivation the exam requires;
- `\rubric{points}{criterion}` lines that sum to the item's maximum, each criterion a
  checkable step or result, so that partial credit is unarguable;
- `\pitfall{...}` lines for the mistakes you designed in and others you expect;
- other valid methods, if a student could reasonably take another route.

Check your own answers before you hand over. Recompute every final result independently
with `wolframscript -code '...'` or Python/sympy, and for "show that" items confirm the
claim really holds. An independent checker will solve the set blind afterwards, but a
wrong key that slips through teaches the student something false, so do not lean on that.

## What to deliver

In `sets/<SET>/` of the course directory:

- `exam.tex` and `key.tex`, using the macros in `tools/tex/README.md`, each compiled
  with `tools/build_tex.sh` to a PDF. In `key.tex`, put `\preptoc` right after
  `\prepheader` so the student can jump to a problem. The key must repeat each question above its
  solution so it can be read on its own.
- `set.json` following the schema in `tools/SPEC.md` (section "`sets/<SET>/set.json`"):
  one entry per gradable item with archetype, level, max points, minutes, format, the
  correct letter for multiple choice, and a `variation` line saying in plain words what
  distinguishes this instance (function, system, geometry, setting), so future writers
  can avoid repeating it. Item ids must match the numbering printed in the exam.

## Reply

For the orchestrating agent, under 250 words: one line per item (id, archetype, level,
variation, the designed pitfall); what you verified by computation; anything you are
unsure about, including places where the blueprint or syllabus left you guessing.
