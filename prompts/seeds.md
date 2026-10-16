# Collecting seed exercises

Past exams are the main model for practice questions, but courses change: a topic
taught this year may never have been examined, or only once. For those topics, exam
writers need the lecturer's own way of asking about them. Seeds are that: course
exercises and worked examples, transcribed verbatim, for the topics the bank covers
thinly.

Your task message names the course key and directory. Read `<dir>/syllabus.md` (scope
and schedule), `bank/*.index.tsv` (what past exams ask) and `<dir>/intake.json` (which
files in `materials/` are exercises and notes). Do not open past-exam PDFs or anything in
`holdout/`.

## What to do

1. Find the gaps: topics in this year's scope that appear in no past exam or in only
   one. List them, with the lectures they belong to.
2. For each gap, pick two to four exercises or worked examples from the exercise sets
   and notes that show how the course asks about it, at about exam level, with
   solutions where the source has them. Prefer exercises the lecturer marks as exam
   preparation, and ones whose solution is given.
3. Transcribe them verbatim, following the fidelity rules in `prompts/bank_format.md`:
   original wording and numbering, all mathematics in LaTeX, formulas read from the page
   images, nothing invented, `[[unclear: ...]]` where illegible.

## What to write

`<dir>/seeds.md`:

```markdown
# KEY seed exercises (verbatim from the course materials)

## How to read this file
One or two lines: what the gaps are and where the exercises come from.

# A. Topics past exams do not cover
## A1. Topic name (lectures 7-8; source file, pages)
### Exercise 7.3
The exercise, verbatim.

**Solution (source):** the solution as given, or `not provided`.

# B. Topics past exams cover only once
...
```

Write it as you go, topic by topic.

## Reply

For the orchestrating agent, under 150 words: the gap topics (with A or B), the number
of exercises per topic, and any gap you found no exercise for.
