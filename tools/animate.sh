#!/usr/bin/env bash
# animate.sh STORYBOARD.json [--out OUT.mp4] [--sheet] [--draft]
#
# Render a /review storyboard to an MP4 with tools/animate.py. Manim lives in its own
# virtualenv outside the project (it is large); the first run creates it.
set -euo pipefail
venv=${EXAM_PREP_ANIM_VENV:-$HOME/.local/share/exam-prep-anim/venv}
if ! "$venv/bin/python" -c 'import manim' 2>/dev/null; then
  echo "animate: setting up Manim in $venv (one time, a few minutes)" >&2
  python3 -m venv "$venv"
  "$venv/bin/pip" install -q --upgrade pip
  "$venv/bin/pip" install -q manim
fi
exec "$venv/bin/python" "$(dirname "${BASH_SOURCE[0]}")/animate.py" "$@"
