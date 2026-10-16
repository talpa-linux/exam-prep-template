#!/usr/bin/env bash
# prep_photos.sh SUBMISSION_DIR
#
# Normalise phone photos for the grader.  Every image (jpg, jpeg, png, heic, heif, webp,
# any case) and PDF directly inside SUBMISSION_DIR becomes one or more pages
# SUBMISSION_DIR/pages/page-01.jpg, page-02.jpg, ...: auto-oriented, long edge at most
# 1800 px (never enlarged), metadata stripped, JPEG quality 85.  PDF pages are rendered
# with pdftoppm at 150 dpi.
#
# Order: by EXIF capture time if every input file has one, otherwise by natural file
# name order (case-insensitive, IMG_2 before IMG_10).  PDFs carry no EXIF time, so a
# directory with a PDF is ordered by name.
#
# pages/ is rebuilt from scratch on every run, in a scratch directory that replaces the
# old pages/ only when everything converted.  The originals are never touched.
# Other files found (.nb, .txt, ...) are listed, not converted.
set -u

die() { echo "prep_photos: $*" >&2; exit 1; }

[ $# -eq 1 ] || die "usage: prep_photos.sh SUBMISSION_DIR"
[ -d "$1" ] || die "not a directory: $1"
dir=$(cd "$1" && pwd) || die "cannot enter $1"

if command -v magick >/dev/null 2>&1; then
    IM=(magick)
    ID=(magick identify)
elif command -v convert >/dev/null 2>&1; then
    IM=(convert)
    ID=(identify)
else
    die "ImageMagick not found (need 'magick' with HEIC support)"
fi

ext_re='\.(jpe?g|png|heic|heif|webp|pdf)$'
shopt -s nocasematch

# ---- collect inputs (direct children only, no dotfiles) and other files ----------------
images=()
others=()
while IFS= read -r -d '' rec; do
    name=${rec#*$'\x1f'}
    if [[ $name =~ $ext_re ]]; then images+=("$name"); else others+=("$name"); fi
done < <(
    find -L "$dir" -maxdepth 1 -type f ! -name '.*' -printf '%f\0' |
    while IFS= read -r -d '' n; do lc=${n,,}; printf '%s\x1f%s\0' "$lc" "$n"; done |
    LC_ALL=C sort -z -V
)
shopt -u nocasematch

[ ${#images[@]} -gt 0 ] || die "no images or PDFs found directly in $dir (pages/ left as it was)"

has_pdf=0
for n in "${images[@]}"; do [[ ${n,,} == *.pdf ]] && has_pdf=1; done
if [ $has_pdf -eq 1 ] && ! command -v pdftoppm >/dev/null 2>&1; then
    die "pdftoppm not found (install poppler-utils) but the directory contains a PDF"
fi

# ---- EXIF capture time ------------------------------------------------------------------
# prints "YYYY:MM:DD HH:MM:SS.sss" or nothing
exif_time() {
    local f=$1 t sub
    [[ ${f,,} == *.pdf ]] && return 0
    for tag in DateTimeOriginal DateTimeDigitized DateTime; do
        t=$("${ID[@]}" -format "%[EXIF:$tag]" "$dir/$f[0]" 2>/dev/null | head -n 1)
        if [[ $t =~ ^[0-9]{4}:[0-9]{2}:[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}$ && ${t:0:4} != 0000 ]]; then
            sub=$("${ID[@]}" -format "%[EXIF:SubSecTimeOriginal]" "$dir/$f[0]" 2>/dev/null | head -n 1)
            [[ $sub =~ ^[0-9]+$ ]] || sub=0
            printf '%s.%s' "$t" "$sub"
            return 0
        fi
    done
}

ordered=("${images[@]}")
rule="file name (natural order)"
missing=()
declare -A etime
for n in "${images[@]}"; do
    t=$(exif_time "$n")
    etime["$n"]=$t
    [ -n "$t" ] || missing+=("$n")
done
if [ ${#missing[@]} -eq 0 ]; then
    rule="EXIF capture time"
    ordered=()
    rank=0
    while IFS= read -r -d '' rec; do ordered+=("${rec#*$'\x1f'*$'\x1f'}"); done < <(
        for n in "${images[@]}"; do
            rank=$((rank + 1))
            printf '%s\x1f%06d\x1f%s\0' "${etime[$n]}" "$rank" "$n"
        done | LC_ALL=C sort -z
    )
elif [ ${#missing[@]} -lt ${#images[@]} ]; then
    rule="file name (natural order; no EXIF capture time on: ${missing[*]})"
else
    rule="file name (natural order; no EXIF capture times)"
fi

# ---- convert -----------------------------------------------------------------------------
work=$(mktemp -d "$dir/.pages.XXXXXX") || die "cannot create a scratch directory in $dir"
trap 'rm -rf "$work"' EXIT
count=0
src_of=()

to_jpeg() {  # to_jpeg SOURCE DEST
    "${IM[@]}" "$1" -auto-orient -background white -alpha remove -alpha off \
        -colorspace sRGB -resize '1800x1800>' -strip -quality 85 "$2"
}

for n in "${ordered[@]}"; do
    if [[ ${n,,} == *.pdf ]]; then
        pdir=$(mktemp -d "$work/pdf.XXXXXX")
        pdftoppm -r 150 -png "$dir/$n" "$pdir/p" 2>"$work/err.txt" \
            || die "pdftoppm failed on $n: $(head -n 3 "$work/err.txt")"
        k=0
        for png in "$pdir"/p-*.png; do
            [ -f "$png" ] || die "pdftoppm produced no pages for $n"
            k=$((k + 1))
            count=$((count + 1))
            to_jpeg "$png" "$work/$(printf '%05d' $count).jpg" 2>"$work/err.txt" \
                || die "cannot convert page $k of $n: $(head -n 3 "$work/err.txt")"
            src_of[$count]="$n page $k"
        done
        rm -rf "$pdir"
    else
        count=$((count + 1))
        to_jpeg "$dir/$n[0]" "$work/$(printf '%05d' $count).jpg" 2>"$work/err.txt" \
            || die "cannot convert $n: $(head -n 3 "$work/err.txt")"
        src_of[$count]=$n
    fi
done
rm -f "$work/err.txt"

width=${#count}
[ $width -lt 2 ] && width=2
for ((i = 1; i <= count; i++)); do
    mv "$work/$(printf '%05d' $i).jpg" "$work/page-$(printf '%0*d' $width $i).jpg"
done

rm -rf "$dir/pages"
mv "$work" "$dir/pages" || die "cannot create $dir/pages"
trap - EXIT

# ---- report -------------------------------------------------------------------------------
echo "prep_photos: $count pages in $dir/pages (order: $rule)"
for ((i = 1; i <= count; i++)); do
    p="pages/page-$(printf '%0*d' $width $i).jpg"
    dims=$("${ID[@]}" -format '%wx%h' "$dir/$p" 2>/dev/null)
    kb=$(( ($(stat -c %s "$dir/$p") + 1023) / 1024 ))
    echo "  $p  <-  ${src_of[$i]}  ($dims, ${kb} KB)"
done
if [ ${#others[@]} -gt 0 ]; then
    echo "other files (not converted):"
    for n in "${others[@]}"; do echo "  $n"; done
else
    echo "other files (not converted): none"
fi
