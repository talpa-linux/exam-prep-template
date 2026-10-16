---
name: review
description: Go through one question of a graded exam-prep set with the user in chat - what they wrote, where and why it went wrong, how to do it right - and keep tutoring on follow-up questions. Use when the user says /review, wants to go over a question or mistake, asks why something was marked wrong, or does not understand a solution.
---

# /review SET ITEM

A tutoring conversation about one question the user has handed in and had graded. The
user wants to understand it properly and be able to ask follow-ups, so this happens in
chat, not in a document.

If the set has not been graded yet, the user is still working it: do not open the key
or review it. A review before grading is a hint, so follow the `hint` skill instead,
which gives only the start and logs it.

Arguments: `SET ITEM` (e.g. `MATH-D01 3.2`). With only `SET`, or with nothing (`latest`
is the most recently graded set), list the items first and ask which one; suggest the ones
that lost the most points. The user may also name the item loosely ("the scattering
one", "question 13"); match it from the list.

## Load the item

```bash
python3 tools/item_context.py SET            # the set's items: score, tags, archetype
python3 tools/item_context.py SET ITEM       # everything about one item
```

The second command prints, for that item only: the question, any hint given before the
attempt (from `/hint`: the rung, what was said, the cue and what they had to learn), the
user's transcribed work (by the grader, from the photos; lines marked `[assisted]` were
written with a hint), the
grading (score, error tags, takeaway, the grader's comment), the worked solution and
rubric from the key, and the question type's notes from the blueprint (what is always
asked, the usual pitfalls). This is the one skill where that material belongs in this
session; load only the item being discussed. If the user disputes a reading of their
handwriting, look at the photo in `<dir>/submissions/<SET>/pages/` for that page.

## Tutor

- Open with a short diagnosis in the user's own terms: quote the line where their
  solution went wrong, say why it is wrong (the misunderstanding behind it, not only the
  correction), and say what the right first move would have been. If they left it blank
  or needed a hint, start from how to see the way in: what in the question tells you
  which method to use. If the item had a `/hint`, build on it: say whether the working
  after the hint was right (the score with help against the unaided score), and spend
  the time on the cue, so that they would start it unaided next time.
- Then ask how they want to continue: work it out themselves with hints, see the full
  solution explained, or watch a short video of their attempt and the fix (see
  "Video" below). Follow their choice.
  - Guided: one step at a time; let them write the step; check it and say plainly whether
    it is right; if not, find the exact point and the reason.
  - Explained: the solution step by step, with the reason for each step, in the course's
    notation (`<dir>/syllabus.md`, the equation or formula sheet), plus the checks they
    can use in the exam to catch mistakes (units, limiting cases, symmetry, estimates).
- Answer follow-up questions in the same thread; that is the point of doing it here.
  Pull in course material where it helps (`<dir>/syllabus.md`, `<dir>/bank/exercises/`
  for the lecturer's own worked exercises).
- Verify anything you compute with `wolframscript` or sympy before stating it.
- Keep messages short. Follow "Maths in chat" in `CLAUDE.md` for every formula: equations
  and anything with `_` or `*` as display maths on their own lines; inline `$...$` only
  for short fragments without them; Unicode (ψₙ, â₊, ψ*) for subscripted symbols in a
  sentence. Never the exam's own macros (`\vv`, `\pe{r}`, `\ex`): the item printed by
  `item_context.py` is raw LaTeX, so rewrite it in plain LaTeX.
- To finish: have them state the method in one or two sentences in their own words, then
  suggest they redo the item from a blank page, and offer a fresh variant of the
  question to try right away (write it yourself, at the same level, and check their
  answer if they send it).

## Video

When the user picks the video or asks for one ("animate it", `/review SET ITEM video`),
make a short animation (offer it especially for algebra-heavy derivations): the
question, their own lines one at a time, the wrong term boxed with the reason, a rewind
to the last good line, the correct continuation, the takeaway. Every line carries a
number in the margin so the user can ask about "line 12".

1. Read `prompts/storyboard.md` and write `<dir>/animations/<SET>_<ITEM>.json` from the
   item already loaded (their transcript lines, your diagnosis, the key's solution).
   Verify any line you write yourself with sympy or `wolframscript`.
2. Render in the background: `tools/animate.sh <dir>/animations/<SET>_<ITEM>.json`
   (about 1–2 minutes). Keep tutoring meanwhile if the user wants to.
3. If the render prints `warning:` lines, fix the storyboard and render again (unchanged
   steps are cached). Look at stills (`--sheet`, one image) only when a warning or an
   unusual line leaves you unsure about the layout: it is the costly part.
4. Send the `.mp4` with SendUserFile, then continue the thread.

One video per item. Follow-up questions, including "explain line 12", are answered in
chat: never re-render or make another video for them. `tools/animate.sh <json> --lines`
prints the numbered lines with their notes when the storyboard is not in this session
(a new chat about an existing video). Re-render only when the user asks for a change to
the video itself, or it contains an error. If a video for the item already exists, send
it again instead of making a new one.

## When the gap is a whole topic

If the conversation shows they lack the idea behind a whole question type, not just this
item, offer a lesson: a short mini-course PDF on that type. If they want it, spawn one
agent with `model: "sonnet"`:

> Read `prompts/lesson.md` in the project root `<root>` and follow it. Course directory:
> `<dir>`. Archetype: `<id>`. What the student got wrong: `<one or two lines from this
> conversation>`.

and send them the PDF with SendUserFile when it is done.

## Scores

Do not change scores here. If the user shows the grading was wrong (a misread line, a
valid method not credited), follow the dispute procedure in the `grade` skill.
