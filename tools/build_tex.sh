#!/usr/bin/env bash
# build_tex.sh FILE.tex
#
# Compile FILE.tex to FILE.pdf with latexmk, in the file's own directory, so that
# \usepackage{prep} finds tools/tex/prep.sty.  The build happens in a scratch output
# directory: no auxiliary files are ever left next to the source, and a failed build
# leaves an existing PDF untouched.  On failure the first LaTeX error is printed with a
# few lines of context to stderr and the exit status is 1.
set -u

die() { echo "build_tex: $*" >&2; exit 1; }

[ $# -eq 1 ] || die "usage: build_tex.sh FILE.tex"
src=$1
[ -f "$src" ] || die "file not found: $src"
case $src in *.tex) ;; *) die "not a .tex file: $src" ;; esac
command -v latexmk >/dev/null 2>&1 || die "latexmk not found (install TeX Live)"

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || die "cannot locate tools directory"
texdir=$here/tex
dir=$(cd "$(dirname "$src")" && pwd) || die "cannot enter directory of $src"
base=$(basename "$src" .tex)

out=$(mktemp -d "${TMPDIR:-/tmp}/build_tex.XXXXXX") || die "cannot create scratch directory"
trap 'rm -rf "$out"' EXIT

# Search order: the document's directory, tools/tex, then TeX's defaults (trailing colon).
tin=${TEXINPUTS:-}
case $tin in "" | *:) ;; *) tin=$tin: ;; esac
export TEXINPUTS=".:$texdir:$tin"

log=$out/build.out
( cd "$dir" && latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error \
      -outdir="$out" "$base.tex" ) >"$log" 2>&1
status=$?

if [ $status -ne 0 ] || [ ! -f "$out/$base.pdf" ]; then
    echo "build_tex: LaTeX failed for $dir/$base.tex" >&2
    texlog=$out/$base.log
    n=
    [ -f "$texlog" ] && n=$(grep -n -m1 -E '^(! |[^ ]+:[0-9]+: )' "$texlog" | cut -d: -f1)
    if [ -n "$n" ]; then
        sed -n "${n},$((n + 7))p" "$texlog" | sed '/^Here is how much/,$d' >&2
    else
        echo "(no LaTeX error line found; last lines of latexmk output follow)" >&2
        tail -n 15 "$log" >&2
    fi
    exit 1
fi

tmp=$dir/.$base.pdf.$$
cp "$out/$base.pdf" "$tmp" && mv -f "$tmp" "$dir/$base.pdf" || { rm -f "$tmp"; die "cannot write $dir/$base.pdf"; }

pages=
command -v pdfinfo >/dev/null 2>&1 && pages=$(pdfinfo "$dir/$base.pdf" 2>/dev/null | awk '/^Pages:/ {print $2}')
echo "built $dir/$base.pdf${pages:+ ($pages pages)}"
