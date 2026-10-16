# Maintaining the template

This folder is the clean, shareable version of a study project that is in daily use
elsewhere. Improvements are made in the live project and carried over here from time to
time. Instructions for the agent doing that:

## Porting changes from a live project

1. Compare the shared parts only: `CLAUDE.md`, `.claude/skills/`, `prompts/`, `tools/`
   (without `tools/config.json`) and `guide/usage.tex`. Never look at or copy course
   folders, `courses.md`, `progress/`, photos, bank files or anything else with the
   user's material.

   ```bash
   diff -ru --exclude=__pycache__ --exclude=config.json "<live>/tools" tools
   diff -ru "<live>/prompts" prompts
   diff -ru "<live>/.claude/skills" .claude/skills
   ```

2. Port each improvement by hand, keeping what makes this copy generic:
   - course keys, names and dates come from `tools/config.json` and `courses.md`; the
     examples use the made-up course `MATH`, Multivariable Calculus (MATH201);
   - the held-out exam is wherever `<dir>/holdout/` is, never a named file;
   - no absolute paths, no user names, no plan-specific calibration presented as fact;
   - files that exist only here: `README.md`, `SETUP.md`, this file, `/start`,
     `prompts/intake.md`, `transcribe.md`, `syllabus.md`, `seeds.md`, `toolkit.md`,
     `tools/course.py`, `tools/doctor.py`.
3. If a skill changed, update `guide/usage.tex` and rebuild it:
   `tools/build_tex.sh guide/usage.tex` (the guide needs no `prep.sty`, but the script
   handles it).
4. Check:

   ```bash
   bash tools/tests/run.sh
   python3 tools/doctor.py --quick
   git grep -nIiE '/home/|C:\\Users|<personal names, course codes of the live project>'
   ```

   The grep must come back empty (fill in the live project's course keys and codes).
5. Commit with a message that lists what was ported.
