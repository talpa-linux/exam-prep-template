# Writing a review storyboard (video of one item)

A storyboard is a small JSON file that `tools/animate.sh` renders as a short video
(about 60–120 s) of one graded item. The video plays the question, then the student's
own lines one at a time, each line growing out of the previous one. It boxes the exact
term where the work went wrong, with a one-line caption explaining why. Then it rewinds
to the last good line, continues correctly from there, and ends on the takeaway.
The student asked for this because a feedback page with everything on it at once is
hard to take in. One line and one remark at a time is easier.

The `/review` session writes the storyboard itself: it already has the item loaded
(`tools/item_context.py`) and has just made the diagnosis, so a fresh agent would only
re-read the same material. Writing the storyboard takes a few minutes. Rendering is a
script and costs nothing.

## File

`<dir>/animations/<SET>_<ITEM>.json` (e.g. `MATH/animations/MATH-D01_3.2.json`); the video
is written next to it as `.mp4`. Example: `MATH/animations/MATH-D01_3.2.json`.

```json
{
  "set": "MATH-D01", "item": "3.2", "score": "0/5",
  "title": "Angle between $\\vx$ and $\\vx'$",
  "intro":   [ {"title": "The question", "text": "...", "tex": ["..."]} ],
  "attempt": [ {"tex": "...", "mark": "wrong", "note": "...", "how": "derive"} ],
  "fix":     {"from": 1, "lines": [ {"tex": "...", "note": "...", "box": true} ]},
  "outro":   [ {"title": "Remember", "text": "...", "tex": ["..."]} ]
}
```

| Field | Meaning |
|---|---|
| `title` | Short name of the question (LaTeX text, maths in `$…$`). |
| `intro`, `outro` | Cards shown full screen: optional `title`, `text` (LaTeX text; `\par` breaks lines), `tex` (list of display equations). Intro: the question in one or two sentences plus its key formula, and any results carried over from earlier sub-questions. Outro: two to four takeaways. |
| `attempt` | The student's lines, in order. Empty if the item was blank. |
| `fix.from` | Number of the last correct attempt line (1 = first). The video strikes everything after it and continues below it. `0` starts from an empty board. |
| `fix.title` | Optional section label, default "How to continue". |
| `fix.lines` | The correct continuation, from the key. |
| `pace` | Optional reading-speed factor, default 1 (0.8 is faster). |
| `preamble` | Optional extra LaTeX preamble (macros). |

Per line:

| Key | Meaning |
|---|---|
| `tex` | The line, as display maths (no `$`). One equation per line. |
| `mark` | `ok` ✓, `hint` (written with help), `slip` ! (amber, a small error that is not the main one), `wrong` ✗ (red, the first real error), `after` (dimmed: the student's lines that follow the error), `plain` (no mark; attempt default), `fix` ✓ (fix default). |
| `note` | The caption shown while the line is on screen. Optional. |
| `how` | `derive` (default): a copy of the previous line morphs into this one; use it when this line is a rewrite of the previous. `write`: written fresh; use it for a new equation. `replace`: morphs the previous line in place; use it for a correction or simplification of the same line. |
| `box` | `true` draws a green box around the line (final answers). |
| `pause` | Extra seconds to hold the line. |

## LaTeX

- `\bad{…}` around the exact wrong term: it is boxed red (amber on a `slip`) after the
  line appears. `\good{…}` around the corrected term in a fix line: green and boxed.
  Both also colour words in a note. Mark the smallest term that is wrong, not the line.
  Give the term room for its box with a thin space on each side inside a product:
  `a\,\bad{\sqrt{1+b^2}}\,e^{b\varphi}`.
- Available: amsmath, amssymb, mathtools, `\bm`, `\cancel`, and the course macros
  (`\vx`, `\ex`, `\norm`, `\abs`, `\ket`, `\bra`, `\braket`, `\expval`, `\dd`, `\ii`,
  `\R`, `\grad`, `\curl`, `\diverg`, `\pe`, `\rect`, `\sinc`, `\tri`). Anything else goes
  in `preamble`.
- Notes and card text are LaTeX text: maths in `$…$`, and escape `% & # _` outside maths.
- In JSON every backslash is doubled: `"\\frac{a}{b}"`.

## What makes a good storyboard

- **The attempt is the student's own work**, from the transcript, in their notation and
  order. Leave out pure copying and dead ends that teach nothing. Five to nine lines is
  typical. Split a long chain `A = B = C = D` into lines; a line much wider than the
  screen is shrunk and becomes hard to read.
- **One `wrong` line**: the first real error, with `\bad{}` on the term and a note that
  gives the reason (the misunderstanding), not only the correction. Check the diagnosis
  yourself: graders sometimes name a later symptom instead of the root cause.
- Credit what was right (`ok`, a note such as "you caught this yourself"). Mark help
  with `hint`.
- After the error, a few `after` lines are enough to show where it led. Use one note to
  give the check that would have caught it (units, a limit, a cosine above 1, a sign).
- **The fix** continues from the last good line in small steps, so each morph is
  readable. Put `\good{}` on the term that replaces the `\bad{}` one, box the answers, and
  add a note for every step that has a reason. Include the checks a grader rewards
  ("no $\varphi$ is left, so α is constant", "positive root since b>0").
- **Notes**: one idea, at most about 140 characters, plain words. Not every line needs
  one; a line without a note moves on quickly.
- Verify every line you write yourself with sympy or `wolframscript`.

## Line numbers

Each line gets a number in the margin so the student can refer to it in chat: the
attempt lines are 1…n in storyboard order, and the fix lines continue from n+1 (a
`replace` line takes the next number too). `tools/animate.sh <json> --lines` prints the
numbering with each line's note.

## Render and check

```bash
tools/animate.sh <dir>/animations/<SET>_<ITEM>.json            # 1080p, about 1–2 min
tools/animate.sh <...>.json --draft --out /tmp/x.mp4             # 480p draft, ~25 s
```

Run it in the background. A LaTeX error names the line it came from. Layout problems are
printed as `warning:` lines (a line shrunk to fit, a note or card too long); fix them and
render again. Re-renders are fast: unchanged steps are cached. `--sheet` also writes
`<…>.sheet.png`, one still per step, for a check by eye; reading it costs a few thousand
tokens, so use it only when a warning or an unusual layout leaves doubt. Send the `.mp4`
with SendUserFile.
