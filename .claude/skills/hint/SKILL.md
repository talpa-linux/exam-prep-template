---
name: hint
description: Get unstuck on one item of an exam-prep practice set that the user is still working and has not handed in - the smallest hint that lets them start, never the solution, logged so the grader does not credit it and the next set re-tests it. Use when the user says /hint, is stuck on a question of a set they are working on, does not know how to start an item, or asks for a hint or to "review" a question before the set is graded.
---

# /hint [SET] ITEM

The user is working a set on paper, timed, and cannot see how to start an item.
Skipping it teaches nothing until the set is graded, and guessing wastes the time. This
gives the least help that gets them moving and sends them back to the paper. Every hint
is logged: the grader then scores only what they did without it, and the next training
set brings back exactly the move they had to be told. Read `CLAUDE.md` first if you have
not.

## Load the item

- The set is as given. Otherwise run `python3 tools/hints.py pending`, which lists the
  sets handed out and not yet graded, newest first. If more than one could be meant, ask.
- Run `python3 tools/hints.py open SET ITEM`. It prints the question, the hints already
  given on this item, what the user needed before on this question type and, under
  `FOR THE TUTOR ONLY`, the key's worked solution and the blueprint notes. Like
  `/review`, this skill holds one item's key in the session. Here the key is only for
  aiming the hint. Never show, quote or paraphrase it beyond the rung you are giving.
- If it refuses because the set is graded, use `/review`. The held-out exam gets no
  hints. If the output has a `NOTE` (a diagnostic or a full mock), say in one line why
  a hint weakens that set's measurement, and ask once whether they still want it.

## Before the first hint

Unless they already told you, ask one neutral question: what have they written so far,
or what is their best guess at a first step? Saying it out loud often unblocks them. A
question that points at nothing is not a hint, and nothing is logged if they find the
way from their own words. Their answer goes into `--tried`. If they have no idea at all,
go to rung 1.

## The ladder

Give one rung per message, smallest first. Go up only when they ask again ("still
stuck", "more").

1. **Nudge.** A question that points at what in the problem signals the approach: a
   word, a symmetry, a given that has not been used ("The surface is closed. What does
   that let you trade the flux for?"). No method names.
2. **Method.** Name the method, theorem or idea and say why it applies here. If what is
   missing is a concept (what a curl measures, what an expectation value is), explain it
   briefly on a different, simpler example, not on this problem.
3. **Set-up.** The first concrete step on this problem: the coordinates,
   parametrisation, limits, or the integral or equation to solve, written down but not
   worked out.

Nothing goes beyond rung 3: no final answers, no intermediate results from the key, no
numbers, and no verdict on their work. If they ask "is this right?", say the grading
will tell them, because checking an answer is help too. If they are still stuck after
rung 3, tell them to leave the rest and move on. The log already records what they
needed, and the item gets a full `/review` after grading.

Hint only the item they asked about. Keep messages short: they are mid-set. Follow
"Maths in chat" in `CLAUDE.md`, including its ban on the exam's own macros (`\vv`, `\pe{r}`, `\ex`: the
question printed by `hints.py open` is raw LaTeX, so rewrite it in plain LaTeX). Verify anything you compute with sympy or
`wolframscript` before stating it.

## Log every hint as you give it

Run the log in the same turn as the hint, so that no hint goes unrecorded:

```bash
python3 tools/hints.py log SET ITEM --rung N --gap concept|method|setup \
  --said "what you told them, one or two sentences" \
  --cue "what in the question signals the move" \
  --learned "the move they had to be told, as a rule for next time" \
  --tried "what they had before asking"
```

- `--gap` is what was missing: `concept` (the idea itself), `method` (which approach) or
  `setup` (they knew the approach but could not set it up).
- `--cue` and `--learned` are required on an item's first hint. On a later rung, pass
  them again only if you have sharpened them. `learned` is what the next set's writer
  re-tests and what the progress report lists, so make it specific and transferable,
  for example "Flux through a closed surface with a simple divergence: use the
  divergence theorem instead of parametrising each face", not "use Gauss" (at most 30
  words; `cue` at most 25).
- If the hint also gives away the start of a later sub-question of the same problem,
  say so in `--said`. The grader then treats that sub-question as assisted too.
- If the user says a hint went on the wrong item, run `python3 tools/hints.py drop SET
  ITEM` and log it on the right one. Never drop a hint for any other reason.

The first time you give a hint in a set, end with the two paper conventions in one line
each:

- write a circled **H** on the page where you continue after the hint (lines above it
  count as your own; with no H, the whole item counts as after the hint);
- pause your timer while we talk.

## If they ask what it costs

- At grading, work above the H scores as usual. What the hint gave away, and the lines
  built on it, score nothing. The grader also gives the score with the hint allowed,
  which shows whether the working was right once they had started.
- The next training set brings this question type back first, with the same move
  behind a different cue. If the working after the hint was good, the level stays the
  same instead of dropping.
- After grading, `/review SET ITEM` starts from the hint and what they needed.

Do not change scores, write sets, or hint items the user did not ask about.
