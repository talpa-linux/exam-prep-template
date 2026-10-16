# Writing a course blueprint

You are analysing a course's past exams to produce its **blueprint**: the document every
later practice set is written from. A student has a final in a few weeks and
prepares almost entirely by working exam-style questions. Writers will read your
blueprint instead of re-analysing the exams each time, and a script will use your
archetype list to track the student's mastery and to decide what they practise next. If
the blueprint misjudges what the final will ask, weeks of practice go to the wrong
things, so base every claim on the bank and the syllabus, and say where you are inferring.

## What you have

In the course directory (given in your task):

- `bank/*.md` — full transcriptions of the past exams, with official answers where they
  exist; `bank/*.index.tsv` — one line per item. Format: `prompts/bank_format.md`.
  For some courses `bank/exercises/` holds the lecturer's exercise sets with solutions.
- `syllabus.md` — what this year's course covers, its conventions and notation, and the
  lecture schedule.
- `seeds.md` (if present) — verbatim course exercises for topics the past exams may not cover.
- `equation_sheet.md` or `formula_sheet.md` — what the student may consult in the exam.

Read all of the bank. Do not open any PDF, and never anything in `holdout/`: one past
exam per course is deliberately kept out of the bank as an unseen benchmark, and the
blueprint must not be informed by it.

## What to work out

**The exam format this year.** Duration, points, parts, aids, how the grade is computed,
grading conventions that cost students points (for example "no points without
motivation"). Separate what this year's course material states from what you infer from
predecessor exams.

**The archetypes.** An archetype is a recurring kind of question: the thing a student
recognises as "ah, one of those". Cut them so that each one is a skill that can be
practised and measured on its own: fine enough that scoring well on one says something
specific, coarse enough that it comes back several times before the final. Usually 10–18
per course. For each archetype:

- the invariant core: what is always asked, and the steps a full-marks answer contains;
- every past occurrence (exam id and item), with points;
- the variation axes: what differed between occurrences (the function, the system, the
  geometry, the coordinate system, the physical setting, what is given versus asked),
  listing the values seen and plausible values not yet seen;
- a difficulty ladder: what a level 1 (below exam level, scaffolded), level 2 (exam
  level) and level 3 (hardest seen, or slightly beyond) instance looks like;
- pitfalls: where points are actually lost. Take these from official solutions and
  grading schemes where they exist and from the mathematics of the problem otherwise.
  Be specific ("forgets the Jacobian $h_u h_v$ in the surface element"), since writers
  design questions around these and graders use them to classify mistakes;
- typical points and minutes, and the equation-sheet entries it normally needs.

**Weights.** Each archetype's expected share of the final's points. Start from point
shares over the past exams with recent sittings counting more, then correct for this
year's syllabus: lecture time given to a topic, topics that are new this year, topics
that have left the course. Weights sum to 1. State the reasoning for any weight that
departs noticeably from the historical share.

**Syllabus gaps.** Topics taught this year that the bank covers thinly or not at all.
Create archetypes for the ones that could realistically be examined, built from the
syllabus and the seed exercises, and mark them as syllabus-derived. Conversely, list
bank content that is no longer in the course so writers leave it out.

**How much exams differ from one another.** The student wants practice sets that are as
different from each other and from past exams as past exams are from each other. Measure
that: compare consecutive sittings and say what stayed (structure, archetypes), what
changed (which axes moved), and how often a sitting contained something with no
precedent at all. Turn this into concrete guidance for writers.

**House style.** How this lecturer writes: how a problem is introduced, how sub-questions
chain (does 1.3 use the result of 1.2? are intermediate results given as "show that"?),
how much guidance is given, typical phrasings, notation, how numbers are chosen.

## What to write

`blueprint.md` in the course directory, with these sections: Exam format · Archetypes
(one subsection each, id in the heading) · Structure of a full exam · Syllabus gaps and
dropped content · Variation between sittings and guidance for writers · House style ·
Open questions (things you could not determine and that the student or the course page
could settle).

`blueprint.json` in the course directory, following the schema in `tools/SPEC.md`
(section "`<dir>/blueprint.json`"). Archetype ids are short kebab-case with a group
prefix. `covered_from` comes from the lecture schedule in `syllabus.md`.
`full_exam_structure` describes the slots of a realistic full exam and which archetypes
can fill each. Validate that it parses and that the weights sum to 1.

`bank/index.tsv`: the per-exam index files concatenated, with one extra last column
holding the archetype id of each item (`none` if an item fits no archetype, which should
be rare; `dropped` if the topic has left the course).

## Reply

Under 300 words, for the orchestrating agent: the exam format in two lines; the archetype
table (id, weight, number of past occurrences, syllabus-derived or not); the three
judgement calls you are least sure of; the open questions.
