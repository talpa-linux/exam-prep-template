---
name: grade
description: Grade a handed-in practice set for one of the user's exam-prep courses (the keys in courses.md) from photos of handwritten work and update the ledger and the progress PDF. It never writes the next set; that waits for /mock. Use when the user says they finished a set, uploaded photos or answers, asks for feedback or a grade, or disputes a grading.
---

# /grade COURSE [SET]

Turns a submission into feedback and updates the user's mastery record and progress
report. It does not write the next set. Read `CLAUDE.md` first if you have not.

You are the orchestrator. The grader agent reads the photos and does the grading; you
run scripts and relay results. Do not open the photos, the key or the transcript in this
session, and do not restate or adjust scores yourself: the grader's JSON, recorded by
the ledger script, is the only source of scores.

## Find the submission

The set id is given, or else it is the newest set in `<dir>/sets/` without a
`<dir>/feedback/<SET>.json`. The work is expected in `<dir>/submissions/<SET>/`.

- If the user gave answers or notes in chat (multiple-choice letters, time spent, items
  skipped, what a hint was about), write them verbatim to
  `<dir>/submissions/<SET>/answers.txt`.
- The user marks lines written with outside help (a hint from an AI tutor) with a thick
  black bar in the margin and writes elapsed-time stamps under problems. The grader
  handles both. If the user mentions using help, ask for a few words per item on what
  the hint was about and add them to `answers.txt`: it lets the grader name what was
  missing. Hints from `/hint` need none of this: they are logged in
  `<dir>/submissions/<SET>/hints.json`, and the user only writes a circled H where they
  continued after one.
- If the user says the photos are somewhere else (Downloads, a phone-sync folder; under
  WSL the Windows drive is `/mnt/c/Users/<name>/...`), copy them into
  `<dir>/submissions/<SET>/` with `cp`, without opening them. If they pasted photos into
  the chat, the grader cannot see those: ask them to save the files into that folder.
- If the directory has no pages and no answers, say where the photos need to go and stop.
  Under WSL, give the Windows Explorer path too: `\\wsl.localhost\<distro>` followed by
  the project path with backslashes (`echo $WSL_DISTRO_NAME` gives the distro).

Then normalise the photos:

```bash
tools/prep_photos.sh "<dir>/submissions/<SET>"
```

Tell the user how many pages were found. If that number looks short for the set, ask
before grading: a missing page would be graded as blank.

Then `python3 tools/hints.py show <SET>`. If hints were logged, name the items in one
line, so the user can say if one is on the wrong item (`hints.py drop`, only on their
word). The grader reads the log itself, and `record` refuses feedback that credits work
done after a logged hint as unaided.

## Grade

Spawn one agent with `model: "sonnet"`, in the foreground:

> Read `prompts/grader.md` in the project root `<root>` and follow it. Course directory:
> `<dir>`. Set id: `<SET>`. Today is `<date>`.

Then record and rebuild:

```bash
python3 tools/ledger.py record COURSE <SET>
python3 tools/build_report.py
```

If `record` rejects the feedback file, send the error text to the grader agent with
SendMessage and have it correct the file; do not patch the JSON yourself.

If the grader reports a **key error**, tell the user plainly which item's key was wrong
and that they were graded against the corrected answer.

## Report to the user

Send `<dir>/feedback/<SET>.pdf`, `<dir>/sets/<SET>/key.pdf` and `progress/progress.pdf`
with SendUserFile. In chat, keep it short: the score and grade equivalent, the two or
three fixes the grader ranked highest, and any items graded with low reading confidence
so the user can check the transcription. For items with a logged hint, give the
unaided score next to the score with the hint allowed, and say that the next training
set brings those question types back first. Then name the items most worth going over
(`python3 tools/select_review.py COURSE <SET>`, its `full` list) and say that
`/review <SET> <item>` goes through any of them in chat: their transcribed work, what
went wrong and why, and how to do it right.

## Disputes

If the user says a reading or a deduction is wrong, continue the grader agent with
SendMessage (or spawn a new one with the same prompt plus the user's objection and the
item), have it re-examine that item and rewrite both feedback files, then run `record`
and `build_report.py` again. `record` replaces the set's earlier rows.

## Next set

Do not write or start the next set. The user decides when a set is made and asks for it
with `/mock`. Writing one unasked spends their session budget on a set they may not
want yet. Close the report with one line naming the next set the plan has for this
course and its day, and that `/mock COURSE` makes it.

After a held-out exam, also give the user the comparison the benchmark exists for: the
real-exam grade next to the grade the progress report predicted before it.
