#!/usr/bin/env bash
# tools/tests/run.sh -- end-to-end tests for the exam-prep tooling.
#
#   tools/tests/run.sh [-v] [--keep]
#
# Everything happens in a throw-away copy of the project structure under $TMPDIR (the path
# contains spaces, so does the made-up course directory).  The project's own course
# directories are never written to; the real tools are copied, not run in place.
# -v prints every passing check, --keep keeps the temp directory (kept anyway on failure).
set -u

VERBOSE=0
KEEP=0
for a in "$@"; do
    case $a in
        -v) VERBOSE=1 ;;
        --keep) KEEP=1 ;;
        *) echo "usage: run.sh [-v] [--keep]" >&2; exit 2 ;;
    esac
done

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TOOLS=$(dirname "$HERE")
REAL_ROOT=$(dirname "$TOOLS")
FIX=$HERE/fixtures

TMP=$(mktemp -d "${TMPDIR:-/tmp}/prep tests.XXXXXX") || { echo "cannot create temp dir" >&2; exit 2; }
ROOT=$TMP/Exam\ prep\ Q1
OUT=$TMP/.out
ERR=$TMP/.err
pass=0
fail=0
export PREP_TODAY=2026-10-13

finish() {
    if [ $fail -eq 0 ] && [ $KEEP -eq 0 ]; then rm -rf "$TMP"; else echo "temp dir kept: $TMP"; fi
}
trap finish EXIT

# ------------------------------------------------------------------------------ helpers
ok()  { pass=$((pass + 1)); [ $VERBOSE -eq 1 ] && echo "  ok    $1"; return 0; }
bad() { fail=$((fail + 1)); echo "  FAIL  $1"; shift; for l in "$@"; do echo "          $l"; done; return 0; }

section() { echo "== $1"; }

# run CMD... : stdout -> $OUT, stderr -> $ERR, status -> $rc
run() { "$@" >"$OUT" 2>"$ERR"; rc=$?; }
lg()  { python3 "$ROOT/tools/ledger.py" "$@"; }
hn()  { python3 "$ROOT/tools/hints.py" "$@"; }

assert_rc() {   # name want
    if [ "$rc" -eq "$2" ]; then ok "$1"; else bad "$1" "exit status $rc, wanted $2" "stdout: $(head -c 300 "$OUT")" "stderr: $(head -c 500 "$ERR")"; fi
}
assert_rc_nonzero() {
    if [ "$rc" -ne 0 ]; then ok "$1"; else bad "$1" "exit status 0, wanted non-zero" "stdout: $(head -c 300 "$OUT")"; fi
}
assert_has() {  # name file text
    if grep -qF -- "$3" "$2"; then ok "$1"; else bad "$1" "'$3' not found in $(basename "$2"):" "$(head -c 600 "$2")"; fi
}
assert_lacks() {  # name file text
    if grep -qF -- "$3" "$2"; then bad "$1" "'$3' unexpectedly found in $(basename "$2")"; else ok "$1"; fi
}
assert_empty() {  # name file
    if [ ! -s "$2" ]; then ok "$1"; else bad "$1" "expected empty $(basename "$2"), got: $(head -c 300 "$2")"; fi
}
assert_eq() {   # name got want
    if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "got:    $2" "wanted: $3"; fi
}
assert_file() { if [ -f "$2" ]; then ok "$1"; else bad "$1" "missing file: $2"; fi; }
assert_same_sum() { # name file sumbefore
    local now; now=$(md5sum "$2" 2>/dev/null | cut -d' ' -f1)
    if [ "$now" = "$3" ]; then ok "$1"; else bad "$1" "$(basename "$2") changed"; fi
}

# jcheck NAME FILE 'python expression' : d = parsed JSON, A = archetypes by id, I = items by archetype,
# close(a, b) compares within 6e-4.  The expression must evaluate to True.
jcheck() {
    local res
    res=$(python3 - "$2" "$3" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
def close(a, b, tol=6e-4):
    return a is not None and abs(a - b) <= tol
ns = {"d": d, "close": close}
if isinstance(d, dict):
    ns["A"] = {a["id"]: a for a in d.get("archetypes", []) if isinstance(a, dict) and "id" in a}
    ns["I"] = {i["archetype"]: i for i in d.get("items", []) if isinstance(i, dict) and "archetype" in i}
try:
    r = eval(sys.argv[2], ns)
except Exception as e:
    print("exception: %r" % (e,)); sys.exit(1)
if r is not True:
    print("expression is %r" % (r,)); sys.exit(1)
PY
    ) && ok "$1" || bad "$1" "$res" "expr: $3"
}

# mutate_fb SRC DEST 'python statements' : write DEST as a copy of the feedback JSON SRC, changed by the
# statements (d = the parsed feedback)
mutate_fb() {
    python3 - "$1" "$2" "$3" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
exec(sys.argv[3])
json.dump(d, open(sys.argv[2], "w"), indent=1)
PY
}

# rcheck NAME 'python expression' : rows = ledger rows of the HLP course, R[(set, item)] = one row; must be True
rcheck() {
    local res
    res=$(python3 - "$ROOT/Help Course/ledger.jsonl" "$2" <<'PY'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
R = {(r["set"], r["item"]): r for r in rows}
try:
    r = eval(sys.argv[2], {"rows": rows, "R": R})
except Exception as e:
    print("exception: %r" % (e,)); sys.exit(1)
if r is not True:
    print("expression is %r" % (r,)); sys.exit(1)
PY
    ) && ok "$1" || bad "$1" "$res" "expr: $2"
}

# ------------------------------------------------------------------------------ setup
section "setup"
mkdir -p "$ROOT/tools/tex"
cp "$TOOLS"/ledger.py "$TOOLS"/build_report.py "$TOOLS"/build_tex.sh "$TOOLS"/prep_photos.sh \
   "$TOOLS"/hints.py "$TOOLS"/item_context.py "$TOOLS"/course.py "$TOOLS"/doctor.py "$ROOT/tools/"
cp "$TOOLS"/tex/prep.sty "$ROOT/tools/tex/"
cp "$FIX/config.json" "$ROOT/tools/config.json"
cp -r "$FIX/X" "$ROOT/Test Course"
cp -r "$FIX/CK" "$ROOT/Check Course"
cp -r "$FIX/RPT" "$ROOT/Report Demo"
cp -r "$FIX/EMP" "$ROOT/Empty Course"
cd "$TMP" || exit 2

for f in build_tex.sh prep_photos.sh ledger.py build_report.py hints.py course.py doctor.py tests/run.sh; do
    if [ -x "$TOOLS/$f" ]; then ok "executable: tools/$f"; else bad "executable: tools/$f"; fi
done
if [ -f "$TOOLS/config.json" ]; then
    run python3 "$TOOLS/ledger.py" status
    assert_rc "this project's own config.json is valid (ledger status)" 0
else
    ok "no config.json in this project yet (written by /start)"
fi

# ------------------------------------------------------------------------------ newid
section "ledger newid"
run lg newid X train;      assert_rc "newid X train rc" 0;      assert_eq "newid X train -> X-T03" "$(cat "$OUT")" "X-T03"
run lg newid X diagnostic; assert_eq "newid X diagnostic -> X-D02" "$(cat "$OUT")" "X-D02"
run lg newid X full;       assert_eq "newid X full -> X-F01" "$(cat "$OUT")" "X-F01"
run lg newid X holdout;    assert_eq "newid X holdout -> X-H01" "$(cat "$OUT")" "X-H01"
run lg newid EMP train;    assert_eq "newid on a course without sets -> EMP-T01" "$(cat "$OUT")" "EMP-T01"
run lg newid x train;      assert_eq "course key is case-insensitive" "$(cat "$OUT")" "X-T03"
for k in T D nonsense Train ""; do
    run lg newid X "$k"
    assert_rc_nonzero "newid X '$k' fails"
    assert_empty "newid X '$k' prints nothing to stdout" "$OUT"
done
run lg newid X T
assert_has "newid error lists the four words" "$ERR" "diagnostic, train, full, holdout"
run lg newid NOPE train
assert_rc_nonzero "newid unknown course fails"
assert_has "unknown course error lists configured courses" "$ERR" "configured courses: X, RPT"

# ------------------------------------------------------------------------------ checkset
section "ledger checkset"
run lg checkset CK CK-T01
assert_rc "checkset without exam.pdf/key.pdf fails" 1
assert_has "  names exam.pdf" "$ERR" "exam.pdf"
assert_has "  names key.pdf" "$ERR" "key.pdf"
touch "$ROOT/Check Course/sets/CK-T01/exam.pdf" "$ROOT/Check Course/sets/CK-T01/key.pdf"
run lg checkset CK CK-T01
assert_rc "valid set passes" 0
assert_eq "valid set prints exactly the OK line" "$(cat "$OUT")" "OK CK-T01: 3 items, 20 points"
assert_empty "valid set prints nothing on stderr" "$ERR"

touch "$ROOT/Check Course/sets/CK-T02/exam.pdf"    # key.pdf stays missing
run lg checkset CK CK-T02
assert_rc "broken set fails" 1
assert_empty "broken set prints problems on stderr only" "$OUT"
assert_has "broken: wrong course"          "$ERR" "course: is 'OTHER', expected \"CK\""
assert_has "broken: bad kind"              "$ERR" "kind: 'practice' is not one of"
assert_has "broken: bad format"            "$ERR" "item \"1.1\": format 'oral'"
assert_has "broken: level 4"               "$ERR" "item \"1.2\": level 4 is not the integer 1, 2 or 3"
assert_has "broken: duplicate item id"     "$ERR" "item \"1.2\": item id is not unique"
assert_has "broken: unknown archetype"     "$ERR" "item \"1.3\": archetype \"gamma\" does not exist in blueprint.json"
assert_has "broken: max sum vs total"      "$ERR" "max values sum to 35 but total_points is 40"
assert_has "broken: mc_answer null"        "$ERR" "item \"1.4\": format mc needs mc_answer to be a single letter A-Z, got None"
assert_has "broken: mc_answer \"AB\""      "$ERR" "item \"1.5\": format mc needs mc_answer to be a single letter A-Z, got 'AB'"
assert_has "broken: missing key.pdf"       "$ERR" "key.pdf: file not found"
assert_eq  "broken: exactly one line per problem (10)" "$(wc -l <"$ERR")" "10"

run lg checkset CK CK-T03
assert_rc "unparseable set.json fails" 1
assert_has "  reports invalid JSON" "$ERR" "invalid JSON"
assert_eq "  and nothing else" "$(wc -l <"$ERR")" "1"
run lg checkset CK CK-T09
assert_rc "missing set.json fails" 1
assert_has "  says file not found" "$ERR" "set.json: file not found"
run lg checkset CK bogus
assert_rc_nonzero "malformed set id fails"

mv "$ROOT/Check Course/blueprint.json" "$ROOT/Check Course/blueprint.off"
run lg checkset CK CK-T01
assert_rc "missing blueprint is reported as a problem" 1
assert_has "  as one problem that skips the archetype check" "$ERR" "archetype check skipped"
assert_eq "  and only that one" "$(wc -l <"$ERR")" "1"
echo '{ broken' >"$ROOT/Check Course/blueprint.json"
run lg checkset CK CK-T01
assert_rc "unparseable blueprint is reported as a problem" 1
assert_has "  names invalid JSON" "$ERR" "invalid JSON"
mv "$ROOT/Check Course/blueprint.off" "$ROOT/Check Course/blueprint.json"

run lg record CK CK-T02
assert_rc "record refuses a set that fails the set checks" 1
assert_has "  names the unknown archetype" "$ERR" "archetype \"gamma\""

# ------------------------------------------------------------------------------ record
section "ledger record"
LEDGER="$ROOT/Test Course/ledger.jsonl"
run lg record X X-D01; assert_rc "record X-D01" 0
assert_has "  summary line" "$OUT" "recorded X-D01 (diagnostic, 2026-10-05): 5 rows, score 7/19 (37%), 1 blank, 2 skipped"
run lg record X X-T01; assert_rc "record X-T01" 0
assert_has "  summary line" "$OUT" "score 35/39 (90%)"
sum_before=$(md5sum "$LEDGER" | cut -d' ' -f1)
run lg record X X-T01; assert_rc "re-recording the same feedback" 0
assert_has "  says it replaced rows" "$OUT" "replaced 5 earlier rows"
assert_same_sum "  is idempotent (ledger byte-identical)" "$LEDGER" "$sum_before"

# invalid feedback is rejected and changes nothing
for spec in \
    "score_over_max|item \"1.1\"|score 11 is outside 0..10" \
    "negative_score|item \"1.1\"|score -1 is outside 0..10" \
    "max_mismatch|item \"1.2\"|max 12 differs from the set's max 10" \
    "unknown_tag|item \"1.2\"|unknown error tag 'carelessness'" \
    "unknown_status|item \"1.2\"|status 'partial' is not one of" \
    "missing_item|item \"1.4\"|missing from feedback" \
    "duplicate_item|item \"1.1\"|each item must appear exactly once" \
    "extra_item|item \"9.9\"|is not an item of X-T02" \
    "blank_with_score|item \"1.2\"|needs score 0" \
    "long_takeaway|item \"1.2\"|takeaway has 26 words" \
    "bad_confidence|item \"1.2\"|confidence 'certain'" \
    "wrong_course|course|expected \"X\"" \
    "bad_date|graded_on|YYYY-MM-DD"; do
    IFS='|' read -r name where what <<<"$spec"
    cp "$FIX/X_extra/bad/$name.json" "$ROOT/Test Course/feedback/X-T02.json"
    sum_before=$(md5sum "$LEDGER" | cut -d' ' -f1)
    run lg record X X-T02
    assert_rc "rejects $name" 1
    assert_has "  $name: names $where" "$ERR" "$where"
    assert_has "  $name: says why" "$ERR" "$what"
    assert_same_sum "  $name: ledger unchanged" "$LEDGER" "$sum_before"
done

# the optional fields "assisted" and "minutes": invalid values (the valid ones are tested on the HLP course below)
for spec in \
    "assisted_text|d['items'][0]['assisted'] = 'yes'|item \"1.1\"|assisted must be true or false, got 'yes'" \
    "assisted_number|d['items'][0]['assisted'] = 1|item \"1.1\"|assisted must be true or false, got 1" \
    "assisted_null|d['items'][0]['assisted'] = None|item \"1.1\"|assisted must be true or false, got None" \
    "assisted_blank|d['items'][3].update(status='blank', score=0, assisted=True)|item \"1.4\"|assisted is true but status is \"blank\"" \
    "assisted_skipped|d['items'][3].update(status='skipped_not_covered', score=0, assisted=True)|item \"1.4\"|assisted is true but status is \"skipped_not_covered\"" \
    "minutes_zero|d['items'][0]['minutes'] = 0|item \"1.1\"|minutes must be null or a number > 0, got 0" \
    "minutes_negative|d['items'][2]['minutes'] = -5|item \"1.3\"|minutes must be null or a number > 0, got -5" \
    "minutes_text|d['items'][0]['minutes'] = '23'|item \"1.1\"|minutes must be null or a number > 0, got '23'" \
    "minutes_bool|d['items'][1]['minutes'] = True|item \"1.2\"|minutes must be null or a number > 0, got True"; do
    IFS='|' read -r name stmt where what <<<"$spec"
    mutate_fb "$FIX/X_extra/regrade/X-T02.json" "$ROOT/Test Course/feedback/X-T02.json" "$stmt"
    sum_before=$(md5sum "$LEDGER" | cut -d' ' -f1)
    run lg record X X-T02
    assert_rc "rejects $name" 1
    assert_has "  $name: names $where" "$ERR" "$where"
    assert_has "  $name: says why" "$ERR" "$what"
    assert_same_sum "  $name: ledger unchanged" "$LEDGER" "$sum_before"
done
# several problems at once are all reported
mutate_fb "$FIX/X_extra/regrade/X-T02.json" "$ROOT/Test Course/feedback/X-T02.json" \
    "d['items'][0]['assisted'] = 'maybe'; d['items'][0]['minutes'] = 0; d['items'][2]['minutes'] = 'a lot'"
run lg record X X-T02
assert_rc "bad assisted and bad minutes together" 1
assert_eq "  one line per problem (3)" "$(grep -c 'feedback/X-T02.json: item' "$ERR")" "3"
rm -f "$ROOT/Test Course/feedback/X-T02.json"
run lg record X X-T02
assert_rc "missing feedback file fails" 1
assert_has "  names the file" "$ERR" "feedback/X-T02.json: file not found"
echo '{"course": "X", "set": "X-T02", ' >"$ROOT/Test Course/feedback/X-T02.json"
run lg record X X-T02
assert_rc "unparseable feedback fails" 1
assert_has "  reports invalid JSON" "$ERR" "invalid JSON"

# first grading of T02, then the regrade
cp "$FIX/X/feedback/X-T02.json" "$ROOT/Test Course/feedback/X-T02.json"
run lg record X X-T02; assert_rc "record X-T02 (first grading)" 0
assert_eq "ledger has 14 rows (5 + 5 + 4)" "$(wc -l <"$LEDGER")" "14"
run lg mastery X --json
# hand value: chain rows D01 e=.6 (3/5, L2), T01 e=.88 (8/10, L3 -> .8*1.1), T02 e=.22 (2/10, L3 -> .2*1.1)
# mastery = (1*.22 + .5*.88 + .25*.6) / 1.75 = .81/1.75 = 0.462857
cp "$OUT" "$TMP/mastery_before.json"
jcheck "before regrade: chain = .81/1.75 = 0.4629, needs-work" "$TMP/mastery_before.json" \
    "close(A['chain']['mastery'], 0.462857) and A['chain']['status'] == 'needs-work'"

cp "$FIX/X_extra/regrade/X-T02.json" "$ROOT/Test Course/feedback/X-T02.json"
run lg record X X-T02; assert_rc "regrade: record X-T02 again" 0
assert_has "  replaced 4 earlier rows, previously dated 2026-10-10" "$OUT" "replaced 4 earlier rows, previously dated 2026-10-10"
assert_has "  reports the mastery change" "$OUT" "chain 0.46->0.59"
assert_eq "ledger still has 14 rows (no duplicates)" "$(wc -l <"$LEDGER")" "14"
assert_eq "exactly 4 rows for X-T02" "$(grep -c '"set":"X-T02"' "$LEDGER")" "4"
assert_eq "regraded rows carry the new date" "$(grep '"set":"X-T02"' "$LEDGER" | grep -c '"date":"2026-10-11"')" "4"
assert_eq "regraded row has the new tag" "$(grep '"set":"X-T02"' "$LEDGER" | grep '"item":"1.1"' | grep -c '"errors":\["sign"\]')" "1"
assert_eq "T02 rows keep their position (after T01's)" "$(cut -d'"' -f8 "$LEDGER" | uniq | tr '\n' ' ')" "X-D01 X-T01 X-T02 "

# feedback files without the optional fields still record; the rows get the defaults and the set's budget
assert_eq "old feedback: rows carry assisted=false, minutes=null and the budget from set.json" \
    "$(grep '"set":"X-D01"' "$LEDGER" | head -1 | grep -c '"assisted":false,"minutes":null,"budget_minutes":8,"score_with_help":null,"hint":null}')" "1"
assert_eq "old feedback: every ledger row has the five new keys" \
    "$(grep -c '"assisted":false,"minutes":null,"budget_minutes":[0-9.]*,"score_with_help":null,"hint":null}$' "$LEDGER")" "14"

# ------------------------------------------------------------------------------ mastery
section "ledger mastery (hand-computed)"
# Evidence e = min(1, (score/max) * c(level)), c = {1: .65, 2: 1, 3: 1.1}; weight 0.5^k, k = 0 newest.
#  chain  D01 3/5 L2 -> .6 | T01 8/10 L3 -> .88 | T02 4/10 L3 -> .44
#         (1*.44 + .5*.88 + .25*.6)/1.75 = 1.03/1.75 = 0.588571   close
#  integ  D01 BLANK L2 -> 0 | T01 10/10 L1 -> .65 (level-1 item) | T02 9/10 L2 -> .9
#         (1*.9 + .5*.65 + .25*0)/1.75 = 1.225/1.75 = 0.7        close
#  series D01 skipped (ignored) | T01 6/8 L2 -> .75 | T02 2/8 L2 -> .25
#         (1*.25 + .5*.75)/1.5 = 0.416667                         needs-work
#  limits T01 6/6 L3 -> min(1, 1.1) = 1 (cap)                     exam-ready (last level 3)
#  proof  D01 4/4 L2 -> 1 | T01 5/5 L3 -> 1 | T02 5/5 L1 -> .65
#         (.65 + .5*1 + .25*1)/1.75 = 1.4/1.75 = 0.8 exactly, but the last row is level 1 -> close, not exam-ready
#  ode (only a skipped row) and taylor: unmeasured
#  weights 0.5,0.5,0.4,0.2,0.2,0.1,0.1 sum 2.0 -> .25 .25 .2 .1 .1 .05 .05
#  coverage .25+.25+.2+.1+.05 = .85
#  sum w*m = .25*.588571 + .25*.7 + .2*.416667 + .1*1 + .05*.8 = .545476
#  grade_banked = 10*.545476 = 5.45476; grade_on_measured = 5.45476/.85 = 6.41737
run lg mastery X --json; assert_rc "mastery X --json" 0
cp "$OUT" "$TMP/mastery.json"
jcheck "chain: 1.03/1.75 = 0.5886, close"            "$TMP/mastery.json" "close(A['chain']['mastery'], 0.588571) and A['chain']['status'] == 'close'"
jcheck "integ: blank + level-1 item = 0.7, close"    "$TMP/mastery.json" "close(A['integ']['mastery'], 0.7) and A['integ']['status'] == 'close'"
jcheck "series: skipped ignored = 0.4167, needs-work" "$TMP/mastery.json" "close(A['series']['mastery'], 0.416667) and A['series']['status'] == 'needs-work'"
jcheck "limits: level-3 cap = 1.0, exam-ready"       "$TMP/mastery.json" "close(A['limits']['mastery'], 1.0) and A['limits']['status'] == 'exam-ready'"
jcheck "proof: exactly 0.8 but last level 1 -> close" "$TMP/mastery.json" "close(A['proof']['mastery'], 0.8) and A['proof']['status'] == 'close'"
jcheck "ode (only skipped rows) is unmeasured"       "$TMP/mastery.json" "A['ode']['mastery'] is None and A['ode']['status'] == 'unmeasured' and A['ode']['attempts'] == 0"
jcheck "taylor is unmeasured"                        "$TMP/mastery.json" "A['taylor']['mastery'] is None and A['taylor']['status'] == 'unmeasured'"
jcheck "attempts per archetype"                      "$TMP/mastery.json" "[A[k]['attempts'] for k in ('chain','integ','series','ode','limits','proof','taylor')] == [3,3,2,0,1,3,0]"
jcheck "last levels"                                 "$TMP/mastery.json" "[A[k]['last_level'] for k in ('chain','integ','series','limits','proof')] == [3,2,2,3,1]"
jcheck "last scores come from the regrade"           "$TMP/mastery.json" "A['chain']['last_score'] == 4 and A['chain']['last_date'] == '2026-10-11'"
jcheck "weights are normalised to 1"                 "$TMP/mastery.json" "[round(A[k]['weight'], 4) for k in ('chain','integ','series','ode','limits','proof','taylor')] == [.25,.25,.2,.1,.1,.05,.05]"
jcheck "coverage 0.85"                               "$TMP/mastery.json" "close(d['coverage'], 0.85)"
jcheck "grade_banked 5.45"                           "$TMP/mastery.json" "abs(d['grade_banked'] - 5.45476) < 0.006"
jcheck "grade_on_measured 6.42"                      "$TMP/mastery.json" "abs(d['grade_on_measured'] - 6.41737) < 0.006"
jcheck "sets_done 3"                                 "$TMP/mastery.json" "d['sets_done'] == 3"
run lg mastery X; assert_rc "mastery X (text)" 0
assert_has "  text table row for chain" "$OUT" "chain"
assert_has "  text header summary" "$OUT" "5/7 archetypes measured, 3 sets, coverage 85%"
run lg mastery NOBP; assert_rc "mastery on a course without blueprint fails" 1
assert_has "  says the blueprint is missing" "$ERR" "No Blueprint/blueprint.json: file not found"
assert_empty "  prints nothing to stdout" "$OUT"

# ------------------------------------------------------------------------------ next
section "ledger next (hand-computed)"
# Date 2026-10-13, last attempts dated 10-11 (chain, integ, series, proof) and 10-08 (limits).
# priority p = w*(1-m)*(1.5 if last f<.5) + .01*w*days
#  series .2*(1-.416667)*1.5 + .01*.2*2 = .179     level: last f = .25 -> max(1, 2-1) = 1, 20*.7 = 14 min
#  chain  .25*(1-.588571)*1.5 + .01*.25*2 = .15929 level: f = .4 -> 3-1 = 2,               15 min
#  integ  .25*.3 + .01*.25*2 = .08                  level: f = .9 -> min(3, 2+1) = 3, 20*1.3 = 26 min
#  taylor .05*(1-.3) = .035 (unmeasured)            level 2, 18 min
#  proof  .05*.2 + .01*.05*2 = .011                 level: f = 1, L1 -> 2, 12 min
#  limits .01*.1*5 = .005                           level: f = 1, L3 -> 3, 10*1.3 = 13 min; exam-ready, 5 days -> retention
#  ode: covered_from 2026-10-20 -> not in a training set yet.
#  Budget 90: retention check (limits) reserves 13; then series 14, chain 15, integ 26, taylor 18 = 86; proof (12) would make 98.
run lg next X --kind train --date 2026-10-13; assert_rc "next X --kind train" 0
cp "$OUT" "$TMP/next_train.json"
jcheck "set id, date, budget, totals" "$TMP/next_train.json" \
    "d['set'] == 'X-T03' and d['date'] == '2026-10-13' and d['kind'] == 'train' and d['minutes'] == 90 and d['planned_minutes'] == 86 and d['planned_points'] == 39"
jcheck "items in priority order" "$TMP/next_train.json" \
    "[i['archetype'] for i in d['items']] == ['series','chain','integ','taylor','limits']"
jcheck "levels 1,2,3,2,3" "$TMP/next_train.json" "[i['level'] for i in d['items']] == [1,2,3,2,3]"
jcheck "minutes 14,15,26,18,13" "$TMP/next_train.json" "[i['minutes'] for i in d['items']] == [14,15,26,18,13]"
jcheck "priorities" "$TMP/next_train.json" \
    "all(abs(i['priority'] - p) < 6e-4 for i, p in zip(d['items'], [.179, .15929, .08, .035, .005]))"
jcheck "limits is the retention check" "$TMP/next_train.json" "'retention check' in I['limits']['reason'] and I['limits']['status'] == 'exam-ready'"
jcheck "ode (not lectured yet) is absent, proof does not fit" "$TMP/next_train.json" "'ode' not in I and 'proof' not in I"
jcheck "unmeasured taylor" "$TMP/next_train.json" "I['taylor']['mastery'] is None and I['taylor']['status'] == 'unmeasured' and 'not attempted' in I['taylor']['reason']"
jcheck "reason text" "$TMP/next_train.json" "I['series']['reason'] == 'weight 20%, mastery 0.42, last attempt 2/8 at level 2'"
jcheck "points are typical points" "$TMP/next_train.json" "[i['points'] for i in d['items']] == [8,10,10,5,6]"
jcheck "recent errors, newest first, at most 3" "$TMP/next_train.json" \
    "[(e['set'], e['item'], e['errors']) for e in I['chain']['recent_errors']] == [('X-T02','1.1',['sign']), ('X-T01','1.1',['algebra']), ('X-D01','1.1',['justification'])]"
jcheck "recent errors carry the takeaway" "$TMP/next_train.json" "I['integ']['recent_errors'][0]['takeaway'] == 'Slip in the final addition.'"
jcheck "avoid_variations from all set.json files" "$TMP/next_train.json" \
    "I['chain']['avoid_variations'] == ['plain chain rule on sin(x^2)', 'nested exp and sqrt composition', 'implicit differentiation of x^2 + y^3 = 1']"
jcheck "full_exam_structure is null for train" "$TMP/next_train.json" "d['full_exam_structure'] is None"
jcheck "old data: slow_last false everywhere; recent errors carry assisted/minutes defaults and the set's budget" "$TMP/next_train.json" \
    "all(i['slow_last'] is False for i in d['items']) and all(e['assisted'] is False and e['minutes'] is None for i in d['items'] for e in i['recent_errors']) and I['chain']['recent_errors'][0]['budget_minutes'] == 20 and I['integ']['recent_errors'][0]['budget_minutes'] == 20"
jcheck "items have every field of the spec" "$TMP/next_train.json" \
    "all({'archetype','name','level','minutes','points','mastery','status','not_yet_covered','reason','recent_errors','avoid_variations'} <= set(i) for i in d['items'])"

run lg next X --kind train --minutes 40 --date 2026-10-13; assert_rc "next --minutes 40" 0
cp "$OUT" "$TMP/next40.json"
jcheck "40 min: retention reserved first, then what fits (series 14, proof 12)" "$TMP/next40.json" \
    "[i['archetype'] for i in d['items']] == ['series','proof','limits'] and d['planned_minutes'] == 39 and d['minutes'] == 40"
run lg next X --kind train --date 2026-10-12; assert_rc "next on the day before (limits idle 4 days)" 0
cp "$OUT" "$TMP/next12.json"
jcheck "4 idle days: no retention check; proof now fits" "$TMP/next12.json" \
    "[i['archetype'] for i in d['items']] == ['series','chain','integ','taylor','proof'] and d['planned_minutes'] == 85 and all('retention' not in i['reason'] for i in d['items'])"
run lg next X --kind train --date 2026-10-21; assert_rc "next once ode has been lectured" 0
cp "$OUT" "$TMP/next21.json"
jcheck "ode is included, not flagged, unmeasured; limits is the retention check" "$TMP/next21.json" \
    "I['ode']['not_yet_covered'] is False and I['ode']['status'] == 'unmeasured' and 'retention check' in I['limits']['reason'] and [i['archetype'] for i in d['items']] == ['series','chain','integ','ode','limits']"

run lg next X --kind diagnostic --date 2026-10-13; assert_rc "next X --kind diagnostic" 0
cp "$OUT" "$TMP/next_diag.json"
jcheck "diagnostic: every archetype, all level 2, new set id" "$TMP/next_diag.json" \
    "d['set'] == 'X-D02' and len(d['items']) == 7 and all(i['level'] == 2 for i in d['items']) and d['minutes'] == 120"
jcheck "diagnostic: not_yet_covered only for ode" "$TMP/next_diag.json" \
    "[i['archetype'] for i in d['items'] if i['not_yet_covered']] == ['ode']"
jcheck "diagnostic passes full_exam_structure through" "$TMP/next_diag.json" \
    "[s['slot'] for s in d['full_exam_structure']] == ['Problem 1', 'Problem 2']"
run lg next X --kind full --date 2026-10-13; assert_rc "next X --kind full" 0
cp "$OUT" "$TMP/next_full.json"
jcheck "full: adaptive levels per archetype" "$TMP/next_full.json" \
    "d['set'] == 'X-F01' and [I[k]['level'] for k in ('chain','integ','series','ode','limits','proof','taylor')] == [2,3,1,2,3,2,2] and d['full_exam_structure'] is not None"
run lg next X --kind full --minutes 100 --date 2026-10-13
cp "$OUT" "$TMP/next_full100.json"
jcheck "full: --minutes overrides the blueprint duration" "$TMP/next_full100.json" "d['minutes'] == 100"
run lg next X --kind holdout; assert_rc "next --kind holdout is not allowed" 2
run lg next X --kind train --date 13-10-2026; assert_rc "next rejects a malformed --date" 2
run lg next NOBP --kind train; assert_rc "next on a course without blueprint fails" 1
assert_empty "  prints nothing to stdout" "$OUT"

# ------------------------------------------------------------------------------ status
section "ledger status"
for k in RPT-D01 RPT-T01 RPT-T02 RPT-T03 RPT-F01 RPT-H01; do
    run lg record RPT "$k"
    [ $rc -eq 0 ] || bad "record $k" "$(cat "$ERR")"
done
ok "recorded the six RPT sets"
run lg status; assert_rc "status" 0
assert_has "  X line: days and study days left" "$OUT" "exam 2026-11-10 (28d, 12 study days left)"
assert_has "  X line: last set and grades" "$OUT" "last X-T02 20/33 (61%)  grade measured 6.42  banked 5.45  coverage 85% (5/7 archetypes)"
assert_has "  NOBP line" "$OUT" "no blueprint yet"
assert_has "  RPT shows its held-out exam" "$OUT" "holdout RPT-H01"
run lg status --json; assert_rc "status --json" 0
cp "$OUT" "$TMP/status.json"
jcheck "status json: X" "$TMP/status.json" \
    "(lambda x: x['days_left'] == 28 and x['study_days_left'] == 12 and x['sets_done'] == 3 and x['last_set']['set'] == 'X-T02' and x['last_set']['score'] == 20 and x['last_set']['max'] == 33 and abs(x['grade_banked'] - 5.45) < .006 and abs(x['grade_on_measured'] - 6.42) < .006 and x['coverage'] == 0.85)([c for c in d['courses'] if c['course'] == 'X'][0])"
jcheck "status json: NOBP has no blueprint, EMP is unmeasured" "$TMP/status.json" \
    "[c['blueprint'] for c in d['courses'] if c['course'] in ('EMP','NOBP')] == [True, False] and [c for c in d['courses'] if c['course'] == 'EMP'][0]['grade_on_measured'] is None"
jcheck "status json: RPT has a held-out result" "$TMP/status.json" "[c for c in d['courses'] if c['course'] == 'RPT'][0]['holdout']['set'] == 'RPT-H01'"
# Tue 2026-11-10 is exam day: 0 days, 0 study days; the day after, the exam is past
PREP_TODAY=2026-11-10 run lg status --json
cp "$OUT" "$TMP/status_examday.json"
jcheck "exam day: 0 days and 0 study days left" "$TMP/status_examday.json" "(lambda x: x['days_left'] == 0 and x['study_days_left'] == 0)([c for c in d['courses'] if c['course'] == 'X'][0])"
PREP_TODAY=2026-11-07 run lg status --json   # Saturday, exam on Tuesday: Mon 9th is not a study day
cp "$OUT" "$TMP/status_weekend.json"
jcheck "weekend before the exam: 3 days, 0 study days" "$TMP/status_weekend.json" "(lambda x: x['days_left'] == 3 and x['study_days_left'] == 0)([c for c in d['courses'] if c['course'] == 'X'][0])"
PREP_TODAY=nonsense run lg status; assert_rc "bad PREP_TODAY is reported" 1

# ------------------------------------------------------------------------------ help marks and item time
section "help marks and per-item time (course HLP)"
# Course HLP is written here, not kept as fixtures, so each row's reason to exist sits next to its expected result.
# One row per line: set, item, archetype, level, max, budget (set.json minutes), score, assisted, minutes, errors, takeaway.
# HLP-T01 is "old style": its feedback has neither field.  Dates: D01 10-01, T01 10-04, T02 10-08, T03 10-12.
python3 - "$ROOT/Help Course" <<'PY'
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
arch = [("clean", "Basics", .2), ("helped", "Basics", .2), ("slow", "Speed", .2), ("edge", "Speed", .1),
        ("helplow", "Basics", .1), ("slowlow", "Speed", .1), ("slow3", "Speed", .1)]
bp = {"course": "HLP", "duration_min": 90, "total_points": 100, "grade_divisor": 10, "pass_grade": 5.5,
      "archetypes": [{"id": a, "name": "Type " + a, "group": g, "weight": w, "typical_points": 6,
                      "typical_minutes": 10, "format": "open", "covered_from": "2026-09-01"} for a, g, w in arch],
      "full_exam_structure": [{"slot": "Problem 1", "points": 100, "archetypes": [a for a, _, _ in arch], "note": "all"}]}
d.mkdir(exist_ok=True)
(d / "blueprint.json").write_text(json.dumps(bp))
N = None
SETS = {
    "HLP-D01": ("diagnostic", "2026-10-01", 60, True, [
        ("1.1", "clean",   2, 6, 10, 6, False, 8,   [], ""),
        ("1.2", "helped",  2, 6, 10, 3, True,  14,  ["method"], "Needed a hint to start; the substitution was not seen."),
        ("1.3", "slow",    2, 6, 10, 6, False, 20,  [], ""),
        ("1.4", "helplow", 2, 6, 10, 3, False, N,   ["concept"], "Mixed up the two conditions.")]),
    "HLP-T01": ("train", "2026-10-04", N, False, [
        ("1.1", "clean",   1, 6, 10, 5, False, N,   ["sign"], "Dropped a minus sign in the last line."),
        ("1.2", "slowlow", 2, 6, 10, 5, False, N,   [], "")]),
    "HLP-T02": ("train", "2026-10-08", 70, True, [
        ("1.1", "helped",  2, 6, 10, 6, True,  9,   [], "Hint on the first step; start from the boundary condition."),
        ("1.2", "slow",    2, 6, 15, 6, False, 25,  [], ""),
        ("1.3", "edge",    1, 6, 12, 6, False, 18,  [], ""),
        ("1.4", "slowlow", 2, 6, 10, 5, False, N,   ["arithmetic"], "Slip in the final addition.")]),
    "HLP-T03": ("train", "2026-10-12", 95, True, [
        ("1.1", "helplow", 2, 6, 10, 1, True,  30,  ["method"], "Hint needed to start; first write down the matrix."),
        ("1.2", "slowlow", 2, 6, 10, 4, False, 40,  ["setup"], "Limits of integration were set up wrongly."),
        ("1.3", "slow3",   3, 6, 12, 6, False, 20.5, [], "")]),
}
for sid, (kind, day, spent, new, rows) in SETS.items():
    sd = d / "sets" / sid
    sd.mkdir(parents=True)
    items = [{"item": i, "archetype": a, "level": lv, "max": mx, "minutes": bud, "format": "open", "mc_answer": None,
              "not_yet_covered": False, "variation": "%s %s" % (sid, i)} for i, a, lv, mx, bud, *_ in rows]
    (sd / "set.json").write_text(json.dumps({"course": "HLP", "set": sid, "kind": kind, "created": day,
        "duration_min": 60, "total_points": sum(r[3] for r in rows), "items": items}))
    fb = []
    for i, a, lv, mx, bud, sc, asst, mins, errs, tk in rows:
        it = {"item": i, "score": sc, "max": mx, "status": "graded", "errors": errs, "confidence": "high", "takeaway": tk}
        if new:
            it["assisted"] = asst
            it["minutes"] = mins
        fb.append(it)
    (d / "feedback").mkdir(exist_ok=True)
    (d / "feedback" / (sid + ".json")).write_text(json.dumps({"course": "HLP", "set": sid, "graded_on": day,
        "time_spent_min": spent, "items": fb}))
PY
HL="$ROOT/Help Course/ledger.jsonl"
for k in D01 T01 T02 T03; do
    run lg record HLP HLP-$k
    [ $rc -eq 0 ] || bad "record HLP-$k" "$(cat "$ERR")"
done
ok "recorded the four HLP sets"
assert_eq "ledger has 4 + 2 + 4 + 3 = 13 rows" "$(wc -l <"$HL")" "13"
rcheck "new fields are copied into the rows, budget from set.json" \
    "R[('HLP-T02','1.1')]['assisted'] is True and R[('HLP-T02','1.1')]['minutes'] == 9 and R[('HLP-T02','1.1')]['budget_minutes'] == 10 and R[('HLP-T03','1.3')]['minutes'] == 20.5 and R[('HLP-T02','1.2')]['budget_minutes'] == 15"
rcheck "old-style feedback (HLP-T01) gets the defaults plus the budget" \
    "all(R[('HLP-T01', i)]['assisted'] is False and R[('HLP-T01', i)]['minutes'] is None and R[('HLP-T01', i)]['budget_minutes'] == 10 for i in ('1.1', '1.2'))"
rcheck "a null minutes in new-style feedback stays null" \
    "R[('HLP-D01','1.4')]['minutes'] is None and R[('HLP-D01','1.4')]['assisted'] is False and R[('HLP-T02','1.4')]['minutes'] is None"
sum_before=$(md5sum "$HL" | cut -d' ' -f1)
run lg record HLP HLP-T03; assert_rc "re-recording a set with the new fields" 0
assert_same_sum "  is idempotent (ledger byte-identical)" "$HL" "$sum_before"

# mastery ignores the flags: helped = D01 3/6 (.5) then T02 6/6 (1.0), (1*1 + .5*.5)/1.5 = 0.8333, exam-ready at level 2
run lg mastery HLP --json; assert_rc "mastery HLP --json" 0
cp "$OUT" "$TMP/hlp_mastery.json"
jcheck "mastery of an assisted archetype is unchanged: score-based 0.8333, exam-ready" "$TMP/hlp_mastery.json" \
    "close(A['helped']['mastery'], 0.833333) and A['helped']['status'] == 'exam-ready' and A['helped']['attempts'] == 2"
jcheck "assisted count per archetype" "$TMP/hlp_mastery.json" \
    "[A[k]['assisted'] for k in ('clean','helped','slow','edge','helplow','slowlow','slow3')] == [0,2,0,0,1,0,0]"
jcheck "slow archetype: mastery from scores only (1.0)" "$TMP/hlp_mastery.json" "close(A['slow']['mastery'], 1.0)"
run lg mastery HLP; assert_rc "mastery HLP (text)" 0

# levels for the next full mock (full = every archetype at its adaptive level).  Without the new rules:
#  clean   T01 old-style 5/6 at L1 (f .83)              -> 2   (ordinary raise; old data behaves as before)
#  helped  T02 6/6 at L2 but assisted                    -> 2   (would be 3: help never raises the level)
#  slow    T02 6/6 at L2 in 25 min of 15 (> 1.5 x)       -> 2   (would be 3), slow_last
#  edge    T02 6/6 at L1 in 18 min of 12 (exactly 1.5 x) -> 2   (not slow: the rule needs strictly more), no slow_last
#  helplow T03 1/6 at L2, assisted, 30 min of 10         -> 1   (help does not stop a lowering; f < .8 so no slow_last)
#  slowlow T03 4/6 at L2, 40 min of 10                   -> 2   (f .67 keeps L; the slowness rule is for f >= .8 only)
#  slow3   T03 6/6 at L3 in 20.5 min of 12               -> 3   (cap; the rule fired, so slow_last)
run lg next HLP --kind full --date 2026-10-13; assert_rc "next HLP --kind full" 0
cp "$OUT" "$TMP/hlp_next.json"
jcheck "levels: 2 2 2 2 1 2 3" "$TMP/hlp_next.json" \
    "[I[k]['level'] for k in ('clean','helped','slow','edge','helplow','slowlow','slow3')] == [2,2,2,2,1,2,3]"
jcheck "slow_last only where the rule fired (f >= 0.8 and minutes > 1.5 x budget)" "$TMP/hlp_next.json" \
    "[I[k]['slow_last'] for k in ('clean','helped','slow','edge','helplow','slowlow','slow3')] == [False,False,True,False,False,False,True]"
jcheck "assisted full-marks row is a recent error; entries carry assisted, minutes, budget_minutes" "$TMP/hlp_next.json" \
    "I['helped']['recent_errors'][0] == {'set': 'HLP-T02', 'item': '1.1', 'errors': [], 'takeaway': 'Hint on the first step; start from the boundary condition.', 'assisted': True, 'minutes': 9, 'budget_minutes': 10, 'score_with_help': None, 'max': 6, 'hint': None}"
jcheck "recent errors, newest first, with the older assisted row behind it" "$TMP/hlp_next.json" \
    "[(e['set'], e['item'], e['assisted'], e['minutes'], e['budget_minutes']) for e in I['helped']['recent_errors']] == [('HLP-T02','1.1',True,9,10), ('HLP-D01','1.2',True,14,10)]"
jcheck "a slow row that lost no points is not a recent error" "$TMP/hlp_next.json" "I['slow']['recent_errors'] == [] and I['slow3']['recent_errors'] == [] and I['edge']['recent_errors'] == []"
jcheck "an old-style row that lost points: assisted false, minutes null, budget from set.json" "$TMP/hlp_next.json" \
    "I['clean']['recent_errors'][0]['assisted'] is False and I['clean']['recent_errors'][0]['minutes'] is None and I['clean']['recent_errors'][0]['budget_minutes'] == 10"
jcheck "minutes of a recent error are the row's own (20.5 stays 20.5, 40 stays 40)" "$TMP/hlp_next.json" \
    "I['slowlow']['recent_errors'][0]['minutes'] == 40 and I['helplow']['recent_errors'][0]['minutes'] == 30"
run lg next HLP --kind diagnostic --date 2026-10-13; assert_rc "next HLP --kind diagnostic" 0
cp "$OUT" "$TMP/hlp_diag.json"
jcheck "diagnostic: every level 2, slow_last still reported" "$TMP/hlp_diag.json" \
    "all(i['level'] == 2 for i in d['items']) and I['slow']['slow_last'] is True and I['clean']['slow_last'] is False"
run lg next HLP --kind train --date 2026-10-13; assert_rc "next HLP --kind train" 0
cp "$OUT" "$TMP/hlp_train.json"
jcheck "train: items carry slow_last (a boolean) and the levels follow the same rules" "$TMP/hlp_train.json" \
    "all(isinstance(i['slow_last'], bool) for i in d['items']) and all(i['level'] == {'clean':2,'helped':2,'slow':2,'edge':2,'helplow':1,'slowlow':2,'slow3':3}[i['archetype']] for i in d['items'])"

# the same rows without the flags would have raised the level: change the ledger copy and compare
cp "$HL" "$TMP/hlp_ledger.keep"
python3 - "$HL" <<'PY'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
for r in rows:
    r["assisted"], r["minutes"] = False, None
open(sys.argv[1], "w").write("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
PY
run lg next HLP --kind full --date 2026-10-13
cp "$OUT" "$TMP/hlp_next_plain.json"
jcheck "control: the same scores without help marks or times give 3 for helped and slow" "$TMP/hlp_next_plain.json" \
    "[I[k]['level'] for k in ('helped','slow','edge','helplow')] == [3,3,2,1]"
cp "$TMP/hlp_ledger.keep" "$HL"

# ------------------------------------------------------------------------------ hints before the attempt
section "hints before the attempt (course HNT, tools/hints.py)"
# HNT-T01 (train, graded 10-05): 1.1 flux, 1.2 curl, 1.3 line, 1.4 other, 1.5 big; all level 2 except line (1), 5 p each.
# Hints are logged on 1.1 (nudge, then method), 1.2 (set-up) and 1.3 (then left blank).
# HNT-F01 (full) and HNT-H01 (holdout) are never graded: they only test the warning and the refusal.
HN="$ROOT/Hint Course"
python3 - "$HN" <<'PY'
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
arch = [("flux", .1), ("curl", .1), ("line", .1), ("other", .1), ("big", .6)]
bp = {"course": "HNT", "duration_min": 90, "total_points": 100, "grade_divisor": 10, "pass_grade": 5.5,
      "archetypes": [{"id": a, "name": "Type " + a, "group": "All", "weight": w, "typical_points": 5,
                      "typical_minutes": 10, "format": "open", "covered_from": "2026-09-01"} for a, w in arch],
      "full_exam_structure": [{"slot": "Problem 1", "points": 100, "archetypes": [a for a, _ in arch], "note": "all"}]}
d.mkdir(exist_ok=True)
(d / "blueprint.json").write_text(json.dumps(bp))
(d / "blueprint.md").write_text("# HNT\n\n## Type flux (`flux`)\n\nPitfall: parametrising every face.\n\n## Type curl (`curl`)\n\nx\n")
def mkset(sid, kind, items):
    sd = d / "sets" / sid
    sd.mkdir(parents=True)
    its = [{"item": i, "archetype": a, "level": lv, "max": 5, "minutes": 10, "format": "open", "mc_answer": None,
            "not_yet_covered": False, "variation": sid + " " + i} for i, a, lv in items]
    (sd / "set.json").write_text(json.dumps({"course": "HNT", "set": sid, "kind": kind, "created": "2026-10-05",
        "duration_min": 60, "total_points": 5 * len(items), "items": its}))
    subs = "\n".join("\\subq{5} QUESTION-%s about %s." % (i, a) for i, a, _ in items)
    keys = "\n".join("\\subq{5} KEYSECRET-%s: the worked solution." % i for i, _, _ in items)
    (sd / "exam.tex").write_text("\\begin{document}\n\\problem{All}{%d}\nIntro text.\n\\begin{subqs}\n%s\n\\end{subqs}\n\\end{document}\n" % (5 * len(items), subs))
    (sd / "key.tex").write_text("\\begin{document}\n\\problem{All}{%d}\n\\begin{subqs}\n%s\n\\end{subqs}\n\\end{document}\n" % (5 * len(items), keys))
mkset("HNT-T01", "train", [("1.1", "flux", 2), ("1.2", "curl", 2), ("1.3", "line", 1), ("1.4", "other", 2), ("1.5", "big", 2)])
mkset("HNT-F01", "full", [("1.1", "flux", 2)])
mkset("HNT-H01", "holdout", [("1.1", "flux", 2)])
PY
HJ="$HN/submissions/HNT-T01/hints.json"

run hn pending; assert_rc "pending" 0
assert_has "  lists the ungraded training set" "$OUT" "HNT-T01  train"
run hn show HNT-T01; assert_rc "show before any hint" 0
assert_has "  says none" "$OUT" "HNT-T01: no hints logged"

run hn open HNT-T01 1.1; assert_rc "open an item of an ungraded set" 0
cp "$OUT" "$TMP/hnt_open.txt"
assert_has "  header names archetype, level, points, budget" "$OUT" "HNT-T01 item 1.1 (train, archetype \`flux\`, level 2, 5 p, budget 10 min)"
assert_has "  prints the question" "$OUT" "QUESTION-1.1 about flux"
assert_lacks "  not the other items' questions" "$OUT" "QUESTION-1.2"
assert_has "  no earlier hints" "$OUT" "(none)"
assert_has "  blueprint notes for the tutor" "$OUT" "Pitfall: parametrising every face."
python3 - "$TMP/hnt_open.txt" <<'PY' && ok "  the key comes only after the tutor-only marker" || bad "  key placement" "$(cat "$TMP/hnt_open.txt")"
import sys
t = open(sys.argv[1]).read()
m, k = t.find("FOR THE TUTOR ONLY"), t.find("KEYSECRET-1.1")
sys.exit(0 if 0 < m < k and "KEYSECRET-1.2" not in t else 1)
PY

run hn open HNT-F01 1.1; assert_rc "open on a full mock works" 0
assert_has "  with a note to ask first" "$OUT" "NOTE: HNT-F01 is a full: a full mock is the grade prediction"
run hn open HNT-H01 1.1; assert_rc "open on the held-out exam is refused" 1
assert_has "  says why" "$ERR" "HNT-H01 is the held-out real exam: no hints"
assert_lacks "  and prints nothing of it" "$OUT" "QUESTION"
run hn open HNT-T01 7.1; assert_rc "open an item that does not exist" 1
assert_has "  lists the items" "$ERR" "items: 1.1, 1.2, 1.3, 1.4, 1.5"

# the log: the first hint on an item needs cue and learned; texts are checked; bad input logs nothing
run hn log HNT-T01 1.1 --rung 1 --gap method --said "Pointed at the words closed surface."
assert_rc "first hint without cue and learned is refused" 1
assert_has "  names --cue" "$ERR" "--cue is required for the first hint on an item"
assert_has "  names --learned" "$ERR" "--learned is required for the first hint on an item"
[ ! -e "$HJ" ] && ok "  no log file written" || bad "  log file written after a refused log"
run hn log HNT-T01 1.1 --rung 1 --gap guess --said x --cue y --learned z
assert_rc "unknown gap is refused" 1
assert_has "  lists the gaps" "$ERR" "--gap must be one of concept, method, setup"
run hn log HNT-T01 1.1 --rung 4 --gap method --said x --cue y --learned z
assert_rc "rung 4 is refused (argparse)" 2
run hn log HNT-T01 1.1 --rung 1 --gap method --said x --cue y \
    --learned "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty twentyone twentytwo twentythree twentyfour twentyfive twentysix twentyseven twentyeight twentynine thirty thirtyone"
assert_rc "learned over 30 words is refused" 1
assert_has "  says the limit" "$ERR" "learned has 31 words; the limit is 30"
run hn log HNT-T01 1.1 --rung 1 --gap method --said "Asked what closed surface lets you use." \
    --cue "closed surface, simple divergence" --learned "Flux through a closed surface: think divergence theorem first." --tried "parametrised the top face"
assert_rc "first hint on 1.1 (nudge)" 0
assert_has "  confirms rung and gap" "$OUT" "logged HNT-T01 1.1: rung 1 nudge, gap method (1 hint on this item)"
run hn log HNT-T01 1.1 --rung 2 --gap method --said "Named the divergence theorem and why it applies." \
    --learned "Closed surface and an easy divergence: use the divergence theorem, not the faces."
assert_rc "second hint on 1.1 (method), cue kept" 0
run hn log HNT-T01 1.1 --rung 1 --gap method --said "Repeated the nudge."
assert_rc "a lower rung later does not lower the item's rung" 0
run hn log HNT-T01 1.2 --rung 3 --gap setup --said "Wrote the determinant to expand." --cue "a curl in Cartesian components" --learned 'Write $\nabla\times G$ as the determinant first.'
assert_rc "hint on 1.2 (set-up), maths counts as one word" 0
run hn log HNT-T01 1.3 --rung 2 --gap concept --said "Explained a line integral on a different curve." --cue "work along a path" --learned "A line integral sums F dot dr along the curve."
assert_rc "hint on 1.3 (concept)" 0
run hn log HNT-T01 1.4 --rung 1 --gap method --said x --cue y --learned z
run hn drop HNT-T01 1.4; assert_rc "drop a hint logged on the wrong item" 0
run hn drop HNT-T01 1.4; assert_rc "dropping it again is an error" 1
jcheck "log: three items in set order, 1.1 at rung 2 with three hints and the first cue kept" "$HJ" \
    "[h['item'] for h in d['items']] == ['1.1','1.2','1.3'] and d['items'][0]['rung'] == 2 and len(d['items'][0]['given']) == 3 and d['items'][0]['cue'] == 'closed surface, simple divergence' and d['items'][0]['learned'].startswith('Closed surface and an easy') and d['items'][0]['tried'] == 'parametrised the top face' and all('at' in g for g in d['items'][0]['given'])"
run hn show HNT-T01; assert_rc "show" 0
assert_has "  counts the items" "$OUT" "HNT-T01: hints logged on 3 items"
grep -E '1\.1  rung 2 method +gap method +learned: Closed surface' "$OUT" >/dev/null && ok "  one line per item" || bad "  show line for 1.1" "$(cat "$OUT")"
run hn open HNT-T01 1.1; assert_rc "open again" 0
assert_has "  shows the hints already given" "$OUT" "- rung 2 method at"
assert_has "  and what was tried" "$OUT" "tried before: parametrised the top face"
run hn pending
assert_has "pending counts the hints" "$OUT" "HNT-T01  train  final 2026-11-07  3 hints logged"

# grading: what record accepts and refuses for hinted items
FBH="$HN/feedback/HNT-T01.json"
mkdir -p "$HN/feedback"
python3 - "$FBH" <<'PY'
import json, sys
it = lambda i, sc, **k: dict({"item": i, "score": sc, "max": 5, "status": "graded", "errors": [], "confidence": "high",
                              "takeaway": "t " + i}, **k)
json.dump({"course": "HNT", "set": "HNT-T01", "graded_on": "2026-10-05", "time_spent_min": 50, "items": [
    it("1.1", 0, errors=["method"], assisted=True, score_with_help=5),
    it("1.2", 1, errors=["setup"], assisted=True, score_with_help=2),
    it("1.3", 0, status="blank", errors=["concept"]),
    it("1.4", 5),
    it("1.5", 0, errors=["concept"])]}, open(sys.argv[1], "w"))
PY
cp "$FBH" "$TMP/hnt_fb.json"
for spec in \
    "hint_not_assisted|d['items'][0]['assisted'] = False; del d['items'][0]['score_with_help']|has a hint logged in Hint Course/submissions/HNT-T01/hints.json (method:" \
    "hint_no_swh|del d['items'][1]['score_with_help']|item \"1.2\": has a logged hint, so score_with_help is required" \
    "swh_below_score|d['items'][1]['score_with_help'] = 0.5|score_with_help must be a number from the score (1) to max (5), got 0.5" \
    "swh_above_max|d['items'][0]['score_with_help'] = 6|score_with_help must be a number from the score (0) to max (5), got 6" \
    "swh_text|d['items'][0]['score_with_help'] = 'all'|got 'all'" \
    "swh_unassisted|d['items'][3]['score_with_help'] = 5|item \"1.4\": score_with_help is only for assisted items"; do
    name=${spec%%|*}; rest=${spec#*|}; code=${rest%%|*}; want=${rest#*|}
    mutate_fb "$TMP/hnt_fb.json" "$FBH" "$code"
    run lg record HNT HNT-T01
    assert_rc "record refuses: $name" 1
    assert_has "  message: $want" "$ERR" "$want"
done
[ ! -e "$HN/ledger.jsonl" ] && ok "  nothing was recorded by the refused attempts" || bad "  ledger written by a refused record"
cp "$HJ" "$TMP/hnt_hints.keep"
python3 -c "
import json,sys; d=json.load(open(sys.argv[1])); d['items'][0]['rung']=7; json.dump(d,open(sys.argv[1],'w'))" "$HJ"
cp "$TMP/hnt_fb.json" "$FBH"
run lg record HNT HNT-T01; assert_rc "record refuses a hand-edited hint log" 1
assert_has "  names the log and the item" "$ERR" "Hint Course/submissions/HNT-T01/hints.json: item \"1.1\": rung must be 1, 2 or 3, got 7"
cp "$TMP/hnt_hints.keep" "$HJ"
run lg record HNT HNT-T01; assert_rc "record the hinted set" 0
assert_has "  says how many items had a hint" "$OUT" "score 6/25 (24%), 1 blank, 0 skipped, 3 with a logged hint"
python3 - "$HN/ledger.jsonl" <<'PY' && ok "rows carry the hint (rung, gap, cue, learned) and score_with_help; the blank hinted item too" || bad "hint rows" "$(cat "$HN/ledger.jsonl")"
import json, sys
R = {r["item"]: r for r in map(json.loads, open(sys.argv[1]))}
assert R["1.1"]["hint"] == {"rung": 2, "gap": "method", "cue": "closed surface, simple divergence",
                           "learned": "Closed surface and an easy divergence: use the divergence theorem, not the faces."}
assert R["1.1"]["score_with_help"] == 5 and R["1.2"]["score_with_help"] == 2 and R["1.2"]["hint"]["rung"] == 3
assert R["1.3"]["status"] == "blank" and R["1.3"]["hint"]["gap"] == "concept" and R["1.3"]["assisted"] is False
assert R["1.4"]["hint"] is None and R["1.4"]["score_with_help"] is None and R["1.5"]["hint"] is None
PY
run hn open HNT-T01 1.1; assert_rc "open on a graded set is refused" 1
assert_has "  points to /review" "$ERR" "HNT-T01 is graded already, so there is nothing to hint: go over it with /review HNT-T01 1.1"
run hn log HNT-T01 1.4 --rung 1 --gap method --said x --cue y --learned z; assert_rc "log on a graded set is refused" 1
run python3 "$ROOT/tools/item_context.py" HNT-T01 1.1; assert_rc "item_context on a hinted item" 0
assert_has "  shows the hint given before the attempt" "$OUT" "## Hint given before the attempt (/hint)"
assert_has "  with what was learned" "$OUT" "learned: Closed surface and an easy divergence"
run python3 "$ROOT/tools/item_context.py" HNT-T01
grep -E '1\.2 .*assisted hint-setup' "$OUT" >/dev/null && ok "item_context list flags the hinted items" || bad "item_context list" "$(cat "$OUT")"

# next.  Levels: flux 0/5 at L2 but 5/5 with help -> held at 2 (would drop to 1); curl 1/5, 2/5 with help -> 1;
# line blank at L1 -> 1; other 5/5 at L2 -> 3; big 0/5 at L2 -> 1.
# Priorities on 10-13 (8 days on): flux .1*1*1.5+.008 = .158, curl .1*.8*1.5+.008 = .128, line .158, other .008,
# big .6*1*1.5+.048 = .948.  Minutes: flux 10, curl 7, line 7, big 7, other 13.
run lg next HNT --kind full --date 2026-10-13; assert_rc "next HNT --kind full" 0
cp "$OUT" "$TMP/hnt_full.json"
jcheck "levels: flux held at 2 after help done well, the others by the usual rules" "$TMP/hnt_full.json" \
    "[I[k]['level'] for k in ('flux','curl','line','other','big')] == [2,1,1,3,1]"
jcheck "hint_retest exactly where the latest row had a logged hint" "$TMP/hnt_full.json" \
    "[I[k]['hint_retest'] for k in ('flux','curl','line','other','big')] == [True,True,True,False,False]"
jcheck "recent errors carry the hint and score_with_help" "$TMP/hnt_full.json" \
    "I['flux']['recent_errors'][0]['hint']['learned'].startswith('Closed surface') and I['flux']['recent_errors'][0]['score_with_help'] == 5 and I['flux']['recent_errors'][0]['max'] == 5 and I['line']['recent_errors'][0]['hint']['gap'] == 'concept' and I['big']['recent_errors'][0]['hint'] is None"
# 34 minutes: other (exam-ready, 8 days old) is the retention check (13), then the three re-tests in priority
# order: flux (23), line (30), curl does not fit (37), so big, the top priority, is left out.
# Without the hints (flux then drops to level 1, 7 min) the set would be other, big, flux, line.
run lg next HNT --kind train --minutes 34 --date 2026-10-13; assert_rc "next HNT --kind train, tight budget" 0
cp "$OUT" "$TMP/hnt_train.json"
jcheck "train: the hinted types come back first" "$TMP/hnt_train.json" "[i['archetype'] for i in d['items']] == ['flux','line','other']"
jcheck "  the reason names the hint" "$TMP/hnt_train.json" \
    "I['flux']['reason'].startswith('re-test after a hint in HNT-T01 1.1 (Closed surface and an easy divergence') and I['line']['hint_retest'] is True"
run lg next HNT --kind train --date 2026-10-13
cp "$OUT" "$TMP/hnt_train90.json"
jcheck "train, 90 minutes: everything fits, highest priority first" "$TMP/hnt_train90.json" \
    "[i['archetype'] for i in d['items']] == ['big','flux','line','curl','other']"
# control: without score_with_help the flux level drops like any 0/5; without the hints there is no re-test
cp "$HN/ledger.jsonl" "$TMP/hnt_ledger.keep"
python3 - "$HN/ledger.jsonl" <<'PY'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
for r in rows:
    r["score_with_help"], r["hint"] = None, None
open(sys.argv[1], "w").write("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
PY
run lg next HNT --kind train --minutes 34 --date 2026-10-13
cp "$OUT" "$TMP/hnt_train_plain.json"
jcheck "control: same scores without hints -> big, flux, line, other; flux at level 1; no re-test flags" "$TMP/hnt_train_plain.json" \
    "[(i['archetype'], i['level'], i['hint_retest']) for i in d['items']] == [('big',1,False),('flux',1,False),('line',1,False),('other',3,False)]"
cp "$TMP/hnt_ledger.keep" "$HN/ledger.jsonl"

# HNT-T02 re-tests flux unaided (5/5): the report's Hints section shows it as the next attempt
python3 - "$HN" <<'PY'
import json, sys
from pathlib import Path
d = Path(sys.argv[1]); sd = d / "sets" / "HNT-T02"; sd.mkdir(parents=True)
(sd / "set.json").write_text(json.dumps({"course": "HNT", "set": "HNT-T02", "kind": "train", "created": "2026-10-08",
    "duration_min": 20, "total_points": 5, "items": [{"item": "1.1", "archetype": "flux", "level": 2, "max": 5,
    "minutes": 10, "format": "open", "mc_answer": None, "not_yet_covered": False, "variation": "T02"}]}))
(d / "feedback" / "HNT-T02.json").write_text(json.dumps({"course": "HNT", "set": "HNT-T02", "graded_on": "2026-10-08",
    "time_spent_min": 9, "items": [{"item": "1.1", "score": 5, "max": 5, "status": "graded", "errors": [],
    "confidence": "high", "takeaway": ""}]}))
PY
run lg record HNT HNT-T02; assert_rc "record HNT-T02 (no hint log at all)" 0
run lg next HNT --kind full --date 2026-10-13
cp "$OUT" "$TMP/hnt_full2.json"
jcheck "after an unaided re-test the flag is gone and the level moves up" "$TMP/hnt_full2.json" \
    "I['flux']['hint_retest'] is False and I['flux']['level'] == 3 and I['curl']['hint_retest'] is True"

# ------------------------------------------------------------------------------ hostile text + report
section "build_report"
# a set whose takeaways are hostile to LaTeX
python3 - "$ROOT/Empty Course" <<'PY'
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
take = [
    r"\input{/etc/hostname} and \end{document} must show as plain text",
    r"$\input{/etc/hostname}$ and $\end{document}$ inside math",
    r"Tilde ~ caret ^ underscore _ hash # percent % amp & braces {} and one lonely { brace and $",
    r"$$x^2$$ display math is not passed through",
    "Ends with a backslash \\",
    r"Real math $\frac{a}{b}+\sqrt{x}$ and costs $5 and $10 stay readable",
    "Unicode: \U0001F600 emoji, ✓ check, Ω ohm, é e-acute, ≈ approx",
    r"$a$b$c$ then $ $ then $x_{1}$",
]
(d / "sets" / "EMP-T01").mkdir(parents=True)
items = [{"item": str(i + 1), "archetype": "e1", "level": 2, "max": 4, "minutes": 5, "format": "open",
          "mc_answer": None, "not_yet_covered": False, "variation": "hostile %d" % i} for i in range(len(take))]
(d / "sets" / "EMP-T01" / "set.json").write_text(json.dumps(
    {"course": "EMP", "set": "EMP-T01", "kind": "train", "created": "2026-10-13", "duration_min": 40,
     "total_points": 4 * len(take), "items": items}))
fb = [{"item": str(i + 1), "score": 1, "max": 4, "status": "graded", "errors": ["notation"],
       "confidence": "low" if i == 0 else "high", "takeaway": t} for i, t in enumerate(take)]
(d / "feedback").mkdir(exist_ok=True)
(d / "feedback" / "EMP-T01.json").write_text(json.dumps(
    {"course": "EMP", "set": "EMP-T01", "graded_on": "2026-10-13", "time_spent_min": 31, "items": fb}))
PY
echo 'this is not json' >"$ROOT/Empty Course/ledger.jsonl"
run lg record EMP EMP-T01
assert_rc "record refuses to extend a corrupt ledger" 1
assert_has "  names the line" "$ERR" "ledger.jsonl: line 1: invalid JSON"
rm -f "$ROOT/Empty Course/ledger.jsonl"
run lg record EMP EMP-T01; assert_rc "record the hostile set" 0

run python3 "$ROOT/tools/build_report.py"
assert_rc "build_report.py" 0
cat "$OUT"
assert_file "progress.tex written" "$ROOT/progress/progress.tex"
assert_file "progress.pdf written" "$ROOT/progress/progress.pdf"
assert_has "math LaTeX cannot compile is reported as plain text" "$OUT" 'undefinedmacro'
assert_lacks "no fallback to all-plain-text math was needed" "$OUT" "rebuilt with all math as plain text"
PDF="$ROOT/progress/progress.pdf"
pdftotext -layout "$PDF" "$TMP/report.txt"
tr '\n' ' ' <"$TMP/report.txt" | tr -s ' ' >"$TMP/report.flat"
pages=$(pdfinfo "$PDF" | awk '/^Pages:/ {print $2}')
if [ "${pages:-0}" -ge 8 ]; then ok "report has $pages pages"; else bad "report page count" "pages=$pages"; fi
assert_has "overview present"                 "$TMP/report.txt" "What the three grade figures mean"
assert_has "all five courses listed"          "$TMP/report.txt" "Nothing Written Yet (NOBP)"
assert_has "X: grade on measured 6.4"         "$TMP/report.txt" "6.4"
assert_has "mastery section"                  "$TMP/report.txt" "Mastery per question type"
assert_has "unmeasured rows shown"            "$TMP/report.txt" "unmeasured"
assert_has "course without blueprint: nothing yet" "$TMP/report.flat" "no blueprint has been written for this course"
assert_has "no sets: nothing yet"             "$TMP/report.flat" "Nothing yet: no set has been graded"
grep -E 'X-D01.*7/19.*37.{0,3}%.*3\.7.*55 min' "$TMP/report.txt" >/dev/null && ok "set history X-D01: 7/19, 37%, grade 3.7, 55 min" || bad "set history X-D01 row" "$(grep 'X-D01' "$TMP/report.txt" | head -3)"
grep -E 'X-T01.*35/39.*90.{0,3}%.*9\.0' "$TMP/report.txt" >/dev/null && ok "set history X-T01: 35/39, 90%, grade 9.0" || bad "set history X-T01 row" "$(grep 'X-T01' "$TMP/report.txt" | head -3)"
grep -E 'X-T02.*20/33.*61.{0,3}%.*6\.1.*62 min' "$TMP/report.txt" >/dev/null && ok "set history X-T02: 20/33, 61%, grade 6.1, 62 min (regraded)" || bad "set history X-T02 row" "$(grep 'X-T02' "$TMP/report.txt" | head -3)"
assert_has "mistake book: ampersand and percent survive" "$TMP/report.flat" "Forgot the 50% factor & the minus sign"
assert_has "mistake book: _ # ^ ~ and backslash survive"  "$TMP/report.flat" 'x_1 # y^2'
assert_has "mistake book: unbalanced \$ stays plain"      "$TMP/report.flat" 'Costs $5 and $10 but an unbalanced $ stays plain'
assert_has "low-confidence takeaways are marked"          "$TMP/report.flat" "[check reading]"
assert_has "hostile \\input is shown, not executed"       "$TMP/report.flat" '\input{/etc/hostname}'
assert_has "hostile math with \\end{document} is plain text" "$TMP/report.flat" '$\end{document}$'
assert_has "text after the hostile entries still rendered" "$TMP/report.flat" "Real math"
assert_has "error tags table"                 "$TMP/report.txt" "Where the points go"
assert_has "next up table"                    "$TMP/report.txt" "Next training set X-T03"
assert_has "legend explains the banked grade" "$TMP/report.flat" "if every topic you have not practised yet"

# help marks and per-item time in the report (course HLP; the numbers are hand-computed in the HLP section above)
#  time vs budget = minutes over budgets of the items that have a time:  D01 42/30 = 140 %,  T01 none,
#  T02 (9+25+18)/(10+15+12) = 52/37 = 141 %,  T03 (30+40+20.5)/(10+10+12) = 90.5/32 = 283 %
grep -E 'HLP-D01.*18/24.*75.{0,3}%.*7\.5.*60 min.*140.{0,3}%[[:space:]]+1[[:space:]]*$' "$TMP/report.txt" >/dev/null && ok "history HLP-D01: 140 % of budget, 1 assisted item" || bad "history HLP-D01 row" "$(grep 'HLP-D01' "$TMP/report.txt" | head -3)"
grep -E 'HLP-T01.*10/12.*8\.3[[:space:]]+.{1,3}[[:space:]]+.{1,3}[[:space:]]+0[[:space:]]*$' "$TMP/report.txt" >/dev/null && ok "history HLP-T01 (old-style feedback): time columns blank, 0 assisted" || bad "history HLP-T01 row" "$(grep 'HLP-T01' "$TMP/report.txt" | head -3)"
grep -E 'HLP-T02.*23/24.*96.{0,3}%.*9\.6.*70 min.*141.{0,3}%[[:space:]]+1[[:space:]]*$' "$TMP/report.txt" >/dev/null && ok "history HLP-T02: 141 % (an item without time is left out), 1 assisted" || bad "history HLP-T02 row" "$(grep 'HLP-T02' "$TMP/report.txt" | head -3)"
grep -E 'HLP-T03.*11/18.*61.{0,3}%.*6\.1.*95 min.*283.{0,3}%[[:space:]]+1[[:space:]]*$' "$TMP/report.txt" >/dev/null && ok "history HLP-T03: 283 %, 1 assisted" || bad "history HLP-T03 row" "$(grep 'HLP-T03' "$TMP/report.txt" | head -3)"
assert_has "history header: time vs budget"   "$TMP/report.txt" "Time vs"
grep -E 'Type helped[[:space:]]+20.{0,3}%[[:space:]]+2[[:space:]]+2[[:space:]]+L2' "$TMP/report.txt" >/dev/null && ok "mastery table: attempts 2, assisted 2" || bad "mastery row for helped" "$(grep 'Type helped' "$TMP/report.txt" | head -3)"
grep -E 'Type helplow[[:space:]]+10.{0,3}%[[:space:]]+2[[:space:]]+1[[:space:]]+L2' "$TMP/report.txt" >/dev/null && ok "mastery table: attempts 2, assisted 1" || bad "mastery row for helplow" "$(grep 'Type helplow' "$TMP/report.txt" | head -3)"
grep -E 'Type clean[[:space:]]+20.{0,3}%[[:space:]]+2[[:space:]]+0[[:space:]]+L1' "$TMP/report.txt" >/dev/null && ok "mastery table: no help -> assisted 0" || bad "mastery row for clean" "$(grep 'Type clean' "$TMP/report.txt" | head -3)"
sed -n '/^HLP — Help Marks/,$p' "$TMP/report.txt" | sed -n '/^Time$/,/^Mistake book$/p' >"$TMP/hlp_time.txt"
assert_has "Time section: window is the last three sets"  "$TMP/hlp_time.txt" "last 3 sets (HLP-T01, HLP-T02, HLP-T03)"
grep -E 'HLP-T02.{1,4}1\.2[[:space:]]+Type slow[[:space:]]+25[[:space:]]+15[[:space:]]+1\.67' "$TMP/hlp_time.txt" >/dev/null && ok "Time: T02 1.2, 25 min of 15" || bad "Time row T02 1.2" "$(cat "$TMP/hlp_time.txt")"
grep -E 'HLP-T03.{1,4}1\.1[[:space:]]+Type helplow[[:space:]]+30[[:space:]]+10[[:space:]]+3\.00' "$TMP/hlp_time.txt" >/dev/null && ok "Time: T03 1.1, 30 min of 10" || bad "Time row T03 1.1" "$(cat "$TMP/hlp_time.txt")"
grep -E 'HLP-T03.{1,4}1\.2[[:space:]]+Type slowlow[[:space:]]+40[[:space:]]+10[[:space:]]+4\.00' "$TMP/hlp_time.txt" >/dev/null && ok "Time: T03 1.2, 40 min of 10 (low score, still listed)" || bad "Time row T03 1.2" "$(cat "$TMP/hlp_time.txt")"
grep -E 'HLP-T03.{1,4}1\.3[[:space:]]+Type slow3[[:space:]]+20\.5[[:space:]]+12[[:space:]]+1\.71' "$TMP/hlp_time.txt" >/dev/null && ok "Time: T03 1.3, 20.5 min of 12" || bad "Time row T03 1.3" "$(cat "$TMP/hlp_time.txt")"
assert_eq "Time: exactly those four items" "$(grep -c 'HLP-T0[0-9].\{1,4\}1\.[0-9] ' "$TMP/hlp_time.txt")" "4"
assert_eq "Time: not the item at exactly 1.5 x (T02 1.3), within budget (T02 1.1), or from an older set (D01 1.3)" \
    "$(grep -c -E 'HLP-T02.{1,4}1\.[13] |HLP-D01' "$TMP/hlp_time.txt")" "0"
assert_has "mistake book: assisted takeaway is marked"          "$TMP/report.flat" "[needed help] Hint needed to start; first write down the matrix."
assert_has "mistake book: assisted item that lost no points is listed" "$TMP/report.flat" "[needed help] Hint on the first step; start from the boundary condition."
assert_lacks "mistake book: unassisted takeaway is not marked"  "$TMP/report.flat" "[needed help] Slip in the final addition."
assert_has "next up: right but too slow is said"                "$TMP/report.flat" "right last time but too slow"
sed -n '/^HNT — Hints Before/,$p' "$TMP/report.txt" | sed -n '/^Hints$/,/^Next up$/p' >"$TMP/hnt_hints.txt"
grep -E 'HNT-T01.{1,4}1\.1 +method +Closed surface and an easy divergence.*HNT-T02.{1,4}1\.1: 5/5' "$TMP/hnt_hints.txt" >/dev/null && ok "Hints: T01 1.1, what was needed, re-tested 5/5 in T02" || bad "Hints row T01 1.1" "$(cat "$TMP/hnt_hints.txt")"
grep -E 'HNT-T01.{1,4}1\.2 +set-up .*not re-tested yet' "$TMP/hnt_hints.txt" >/dev/null && ok "Hints: T01 1.2 set-up, not re-tested yet" || bad "Hints row T01 1.2" "$(cat "$TMP/hnt_hints.txt")"
assert_eq "Hints: three rows" "$(grep -c '^HNT-T01' "$TMP/hnt_hints.txt")" "3"
assert_has "mistake book: hinted item is marked with the rung"  "$TMP/report.flat" "[hint: method] t 1.1"
assert_has "mistake book: blank hinted item is marked too"      "$TMP/report.flat" "[hint: method] t 1.3"
assert_has "Hints section for a course without hints"           "$TMP/report.flat" "None yet: no item needed a hint from /hint"
assert_has "next up: the re-test reason is shown"               "$TMP/report.flat" "re-test after a hint in HNT-T01 1.2"
assert_has "Time section without any item times (6 sets, no minutes)" "$TMP/report.flat" "Nothing yet: no item times were recorded in the last 3 sets"
assert_has "Time section with a single set and no item times"   "$TMP/report.flat" "no item times were recorded in the last set"
assert_has "Time section for a course without sets"             "$TMP/report.flat" "Nothing yet: no set has been graded"
assert_eq  "no stray LaTeX files next to progress.pdf" "$(ls -A "$ROOT/progress" | tr '\n' ' ')" "progress.pdf progress.tex "
pdftoppm -r 50 -png -f 1 -l 3 "$PDF" "$TMP/page" && ok "pages render to PNG (page-N.png in temp dir)" || bad "pdftoppm"

# the report is rebuilt from scratch and survives broken data
echo '{ "course": "EMP", broken' >"$ROOT/Empty Course/blueprint.json"
run python3 "$ROOT/tools/build_report.py"
assert_rc "report still builds when a blueprint is corrupt" 0
assert_has "  and says which file" "$OUT" "Empty Course/blueprint.json: invalid JSON"
cp "$FIX/EMP/blueprint.json" "$ROOT/Empty Course/blueprint.json"
printf '%s\n' '{"set":"X-T02","oops":1}' >>"$ROOT/Test Course/ledger.jsonl"
run python3 "$ROOT/tools/build_report.py"
assert_rc "report still builds when a ledger row is corrupt" 0
assert_has "  and names the ledger line" "$OUT" "ledger.jsonl: line 15"
head -n 14 "$ROOT/Test Course/ledger.jsonl" >"$TMP/ledger.fixed" && cp "$TMP/ledger.fixed" "$ROOT/Test Course/ledger.jsonl"

# the Time section when times exist but nothing ran over: EMP-T01 gets minutes below budget (4 of 5 each)
mutate_fb "$ROOT/Empty Course/feedback/EMP-T01.json" "$ROOT/Empty Course/feedback/EMP-T01.json" \
    "[it.update(minutes=4) for it in d['items']]"
run lg record EMP EMP-T01; assert_rc "re-record EMP-T01 with item minutes within budget" 0
run python3 "$ROOT/tools/build_report.py"
assert_rc "report builds with item times and no overrun" 0
pdftotext -layout "$ROOT/progress/progress.pdf" - | tr '\n' ' ' | tr -s ' ' >"$TMP/report2.flat"
assert_has "  says nothing ran over 1.5 x budget" "$TMP/report2.flat" "No item took more than 1.5 times its budget in the last set (EMP-T01)"

# no data at all: three course names, no blueprints, no sets, no feedback
EMPTY=$TMP/no\ data\ root
mkdir -p "$EMPTY/tools/tex" "$EMPTY/ALG/sets" "$EMPTY/ALG/feedback" "$EMPTY/Classical Mechanics/sets" "$EMPTY/STAT/feedback"
cp "$ROOT/tools/ledger.py" "$ROOT/tools/build_report.py" "$ROOT/tools/build_tex.sh" "$EMPTY/tools/"
cp "$ROOT/tools/tex/prep.sty" "$EMPTY/tools/tex/"
cat >"$EMPTY/tools/config.json" <<'JSON'
{"courses": {
  "ALG":  {"dir": "ALG", "name": "Linear Algebra (2ALG0)", "exam_date": "2026-10-30"},
  "MECH": {"dir": "Classical Mechanics", "name": "Classical Mechanics (3MECH0)", "exam_date": "2026-11-02"},
  "STAT": {"dir": "STAT", "name": "Statistics (2STAT0)", "exam_date": "2026-11-05"}},
 "study_days": ["Tue", "Wed", "Thu"]}
JSON
run python3 "$EMPTY/tools/build_report.py"
assert_rc "report builds with no data at all" 0
assert_file "  progress.pdf exists" "$EMPTY/progress/progress.pdf"
pdftotext -layout "$EMPTY/progress/progress.pdf" - | tr '\n' ' ' | tr -s ' ' >"$TMP/empty.flat"
assert_has "  says nothing yet" "$TMP/empty.flat" "Nothing yet: no blueprint has been written"
assert_has "  lists the configured courses" "$TMP/empty.flat" "Classical Mechanics (3MECH0)"
run python3 "$EMPTY/tools/ledger.py" status; assert_rc "status with no data at all" 0
assert_eq "  three 'no blueprint yet' lines" "$(grep -c 'no blueprint yet' "$OUT")" "3"

# ------------------------------------------------------------------------------ build_tex + README examples
section "build_tex.sh and tex/README.md"
EX=$TMP/tex\ examples
mkdir -p "$EX"
python3 - "$TOOLS/tex/README.md" "$EX" <<'PY'
import re, sys
txt = open(sys.argv[1], encoding="utf-8").read()
docs = [b for b in re.findall(r"```latex\n(.*?)```", txt, re.S) if "\\documentclass" in b]
for n, b in enumerate(docs, 1):
    open("%s/example%d.tex" % (sys.argv[2], n), "w", encoding="utf-8").write(b)
print(len(docs))
PY
n_ex=$(ls "$EX"/example*.tex 2>/dev/null | wc -l)
assert_eq "README has three complete example documents" "$n_ex" "3"
for i in 1 2 3; do
    run "$ROOT/tools/build_tex.sh" "$EX/example$i.tex"
    assert_rc "example$i.tex compiles" 0
    assert_file "  example$i.pdf" "$EX/example$i.pdf"
done
assert_has "  success line names the pdf and pages" "$OUT" "example3.pdf (1 pages)"
assert_eq "no auxiliary files left behind" "$(ls -A "$EX" | tr '\n' ' ')" "example1.pdf example1.tex example2.pdf example2.tex example3.pdf example3.tex "
pdftotext "$EX/example1.pdf" - | tr '\n' ' ' | tr -s ' ' >"$TMP/ex1.flat"
assert_has "exam: problem heading"       "$TMP/ex1.flat" "Problem 1 — Line integrals (25 p)"
assert_has "exam: sub-question numbering" "$TMP/ex1.flat" "1.1 Compute"
assert_has "exam: margin points"         "$TMP/ex1.flat" "10 p"
pdftotext -layout "$EX/example1.pdf" - | tr -s ' ' >"$TMP/ex1.layout"
grep -E '^ ?\(c\) It equals the enclosed area' "$TMP/ex1.layout" >/dev/null && ok "exam: lettered options (c) ..." || bad "exam: lettered options" "$(grep -n -i 'enclosed' "$TMP/ex1.layout")"
pdftotext "$EX/example2.pdf" - | tr '\n' ' ' | tr -s ' ' >"$TMP/ex2.flat"
assert_has "key: solution box"           "$TMP/ex2.flat" "Solution."
assert_has "key: rubric line"            "$TMP/ex2.flat" "[3 p] Parametrisation"
assert_has "key: pitfall"                "$TMP/ex2.flat" "Pitfall."
pdftotext "$EX/example3.pdf" - | tr '\n' ' ' | tr -s ' ' >"$TMP/ex3.flat"
assert_has "feedback: item heading"      "$TMP/ex3.flat" "Item 1.1 7 / 10"
assert_has "feedback: labelled fields"   "$TMP/ex3.flat" "First error:"

# failure path: first error with context, non-zero exit, existing PDF kept
sum_pdf=$(md5sum "$EX/example1.pdf" | cut -d' ' -f1)
sed 's/Compute/\\undefinedmacroxyz Compute/' "$EX/example1.tex" >"$EX/broken.tex"
cp "$EX/example1.pdf" "$EX/broken.pdf"
sum_broken=$(md5sum "$EX/broken.pdf" | cut -d' ' -f1)
run "$ROOT/tools/build_tex.sh" "$EX/broken.tex"
assert_rc "a LaTeX error makes build_tex.sh fail" 1
assert_has "  prints the LaTeX error" "$ERR" "Undefined control sequence"
assert_has "  with file and line" "$ERR" "broken.tex:"
assert_has "  and the offending source" "$ERR" "undefinedmacroxyz"
assert_same_sum "  the previous PDF is kept" "$EX/broken.pdf" "$sum_broken"
assert_eq "  no auxiliary files left behind" "$(ls -A "$EX" | grep -v -E '^(example[123]|broken)\.(tex|pdf)$' | tr '\n' ' ')" ""
# macros used outside their environment give a clear message
printf '%s\n' '\documentclass[a4paper]{article}' '\usepackage{prep}' '\begin{document}' '\subq{5} Oops' '\end{document}' >"$EX/misuse.tex"
run "$ROOT/tools/build_tex.sh" "$EX/misuse.tex"
assert_rc "misusing \\subq outside subqs fails" 1
assert_has "  with a clear message" "$ERR" 'used outside \begin{subqs}'
# relative path, other working directory
( cd "$EX/.." && run "$ROOT/tools/build_tex.sh" "tex examples/example2.tex"; exit $rc ) ; rc=$?
assert_rc "build_tex.sh works with a relative path containing a space" 0
run "$ROOT/tools/build_tex.sh" "$EX/does-not-exist.tex"; assert_rc "missing input file fails" 1
run "$ROOT/tools/build_tex.sh"; assert_rc "no argument fails" 1

# ------------------------------------------------------------------------------ prep_photos
section "prep_photos.sh"
PH=$TMP/photo\ test
mkdir -p "$PH"
if python3 "$HERE/make_photos.py" "$PH" 2>"$ERR"; then
    ok "generated test images"
else
    bad "generating test images" "$(cat "$ERR")"
fi
if command -v magick >/dev/null 2>&1; then IDENT=(magick identify); else IDENT=(identify); fi  # ImageMagick 7 or 6
identify_prop() { "${IDENT[@]}" -format "$1" "$2" 2>/dev/null; }
assert_eq "fixture: EXIF orientation 6 is readable" "$(identify_prop '%[orientation]' "$PH/exif/IMG_0002.JPG")" "RightTop"
sums_before=$(cd "$PH/exif" && md5sum -- * | md5sum)

run "$ROOT/tools/prep_photos.sh" "$PH/exif"
assert_rc "prep_photos on EXIF-ordered photos" 0
assert_has "  reports EXIF order" "$OUT" "order: EXIF capture time"
assert_eq "  three pages, EXIF order, not name order" "$(ls "$PH/exif/pages" | tr '\n' ' ')" "page-01.jpg page-02.jpg page-03.jpg "
assert_eq "  page-01 is the earliest capture (IMG_0010, 1200x900)" "$(identify_prop '%wx%h' "$PH/exif/pages/page-01.jpg")" "1200x900"
assert_eq "  page-02 is IMG_0001 (1600x1200)" "$(identify_prop '%wx%h' "$PH/exif/pages/page-02.jpg")" "1600x1200"
assert_eq "  page-03 is auto-oriented and shrunk: 2400x1800 rot6 -> 1350x1800" "$(identify_prop '%wx%h' "$PH/exif/pages/page-03.jpg")" "1350x1800"
assert_eq "  listing shows source file for page 1" "$(grep -c 'page-01.jpg  <-  IMG_0010.jpg' "$OUT")" "1"
for p in "$PH"/exif/pages/*.jpg; do
    assert_eq "  $(basename "$p"): JPEG quality 85" "$(identify_prop '%Q' "$p")" "85"
    assert_eq "  $(basename "$p"): metadata stripped" "$("${IDENT[@]}" -verbose "$p" 2>/dev/null | grep -c -i -E '^ *(exif:|orientation: (Right|Left|Bottom))')" "0"
done
assert_eq "  originals untouched" "$(cd "$PH/exif" && md5sum -- IMG_* | md5sum)" "$sums_before"

mkdir -p "$PH/natural/pages"
touch "$PH/natural/pages/page-99.jpg"    # stale output from an earlier run
sums_before=$(cd "$PH/natural" && md5sum -- a1.heic B2.webp 'c 3.PNG' d10.jpeg e.pdf notes.txt answer.nb | md5sum)
run "$ROOT/tools/prep_photos.sh" "$PH/natural"
assert_rc "prep_photos on mixed formats, PDF and other files" 0
assert_has "  falls back to file name order" "$OUT" "file name (natural order; no EXIF capture times)"
assert_eq "  6 pages: 4 images + 2 PDF pages; stale pages/ content is gone" "$(ls "$PH/natural/pages" | tr '\n' ' ')" "page-01.jpg page-02.jpg page-03.jpg page-04.jpg page-05.jpg page-06.jpg "
assert_has "  heic first" "$OUT" "page-01.jpg  <-  a1.heic"
assert_has "  webp second (case-insensitive: B2 after a1)" "$OUT" "page-02.jpg  <-  B2.webp"
assert_has "  PNG third (name with a space)" "$OUT" "page-03.jpg  <-  c 3.PNG"
assert_has "  then the jpeg" "$OUT" "page-04.jpg  <-  d10.jpeg"
assert_has "  PDF pages last" "$OUT" "page-06.jpg  <-  e.pdf page 2"
assert_eq "  long edge capped at 1800 (3000x2000 PNG -> 1800x1200)" "$(identify_prop '%wx%h' "$PH/natural/pages/page-03.jpg")" "1800x1200"
assert_eq "  small images are not enlarged (400x300)" "$(identify_prop '%wx%h' "$PH/natural/pages/page-04.jpg")" "400x300"
assert_eq "  PDF page rendered at 150 dpi (A4 letter-size article: 1275x1650)" "$(identify_prop '%wx%h' "$PH/natural/pages/page-05.jpg")" "1275x1650"
assert_has "  other files listed separately" "$OUT" "other files (not converted):"
assert_has "  .nb listed" "$OUT" "answer.nb"
assert_has "  .txt listed" "$OUT" "notes.txt"
assert_eq "  the other-files list holds exactly the two non-images" "$(sed -n '/^other files/,$p' "$OUT" | tr '\n' '|')" "other files (not converted):|  answer.nb|  notes.txt|"
assert_eq "  originals untouched" "$(cd "$PH/natural" && md5sum -- a1.heic B2.webp 'c 3.PNG' d10.jpeg e.pdf notes.txt answer.nb | md5sum)" "$sums_before"
assert_eq "  no scratch directory left in the submission dir" "$(ls -A "$PH/natural" | grep -c '^\.pages')" "0"
run "$ROOT/tools/prep_photos.sh" "$PH/natural"; assert_rc "running it again" 0
assert_eq "  rebuilt pages/ has the same 6 pages" "$(ls "$PH/natural/pages" | wc -l)" "6"
mkdir "$PH/empty"; echo hi >"$PH/empty/notes.txt"
run "$ROOT/tools/prep_photos.sh" "$PH/empty"; assert_rc "a directory without images fails" 1
assert_has "  says so" "$ERR" "no images or PDFs found"
run "$ROOT/tools/prep_photos.sh" "$PH/nope"; assert_rc "a missing directory fails" 1

# ------------------------------------------------------------------------------ course.py
section "course.py (course set-up)"
CR=$TMP/setup\ root
mkdir -p "$CR/tools"
cp "$ROOT/tools/course.py" "$ROOT/tools/ledger.py" "$CR/tools/"
cs() { python3 "$CR/tools/course.py" "$@"; }
run python3 "$CR/tools/ledger.py" status; assert_rc "ledger without config.json fails" 1
assert_has "  and points to /start" "$ERR" "Run /start"
run cs list; assert_rc "list with no config" 0; assert_has "  says no courses" "$OUT" "no courses yet"
run cs add mat --name "Calculus A" --exam-date 2026-11-20; assert_rc "add MAT (key upper-cased)" 0
[ -d "$CR/MAT/materials" ] && [ -d "$CR/MAT/holdout" ] && ok "  materials/ and holdout/ created" || bad "  materials/ and holdout/ created"
run cs add PHY --name "Physics 1" --exam-date 2026-11-12 --dir "Physics one"; assert_rc "add PHY with a folder name with a space" 0
run cs add X --name x --exam-date 2026-11-12; assert_rc "one-letter key refused" 1
run cs add MAT --name x --exam-date 2026-11-12; assert_rc "duplicate key refused" 1
run cs add ZZ --name x --exam-date 2026-11-12 --dir tools; assert_rc "a project folder as course dir refused" 1
run cs add ZZ --name x --exam-date 2026-02-30; assert_rc "impossible date refused" 1
run cs study-days mon,WED fri; assert_rc "study-days" 0; assert_has "  normalised" "$OUT" "study days: Mon Wed Fri"
run python3 "$CR/tools/ledger.py" status; assert_rc "ledger status after add" 0
run cs state MAT; assert_rc "state" 0; assert_has "  next is materials" "$OUT" "next: materials"
M=$CR/MAT/materials
mkdir -p "$M/old exams"
for f in "old exams/2023-01 final.pdf" "old exams/2023-01 answers.pdf" "old exams/2024-01 final.pdf" \
         "old exams/2025-01 final.pdf" "guide.pdf" "notes.pdf" "sheet.pdf"; do echo x >"$M/$f"; done
cat >"$CR/MAT/intake.json" <<'JSON'
{"course": "MAT", "software": null, "files": [
 {"path": "materials/old exams/2023-01 final.pdf", "role": "exam", "exam_id": "MAT-2023-01", "answers": "materials/old exams/2023-01 answers.pdf"},
 {"path": "materials/old exams/2023-01 answers.pdf", "role": "answers", "for": "MAT-2023-01"},
 {"path": "materials/old exams/2024-01 final.pdf", "role": "exam", "exam_id": "MAT-2024-01", "answers": null},
 {"path": "materials/old exams/2025-01 final.pdf", "role": "exam", "exam_id": "MAT-2025-01", "answers": "same"},
 {"path": "materials/guide.pdf", "role": "course_info"},
 {"path": "materials/notes.pdf", "role": "notes"},
 {"path": "materials/sheet.pdf", "role": "formula_sheet"}]}
JSON
run cs check-intake MAT; assert_rc "check-intake ok" 0; assert_has "  counts" "$OUT" "OK MAT: 7 files, 3 past exams, 2 with answers"
cp "$CR/MAT/intake.json" "$TMP/intake.good"
python3 - "$CR/MAT/intake.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); d["files"][2]["exam_id"] = "MAT-2023-01"; d["files"][4]["role"] = "manual"
json.dump(d, open(sys.argv[1], "w"))
PY
run cs check-intake MAT; assert_rc "check-intake: broken file fails" 1
assert_has "  duplicate exam id" "$OUT" "exam_id MAT-2023-01 used twice"
assert_has "  unknown role" "$OUT" "role must be one of"
cp "$TMP/intake.good" "$CR/MAT/intake.json"
run cs holdout MAT "old exams/2025-01 final.pdf"; assert_rc "holdout moves a file" 0
assert_file "  now in holdout/" "$CR/MAT/holdout/2025-01 final.pdf"
assert_eq "  intake.json follows the move" "$(python3 -c "import json,sys;f=json.load(open(sys.argv[1]))['files'][3];print(f['path'],f.get('holdout'))" "$CR/MAT/intake.json")" "holdout/2025-01 final.pdf True"
run cs holdout MAT notes.pdf; assert_rc "a second holdout without --replace refused" 1
run cs inventory MAT; assert_rc "inventory" 0; assert_lacks "  does not name held-out files" "$OUT" "2025-01"
run cs state MAT; assert_has "  bank step counts the two remaining exams" "$OUT" "0/2 past exams transcribed"
assert_has "  formula sheet step is due" "$OUT" "[ ] formula_sheet"
assert_has "  toolkit not applicable" "$OUT" "[-] toolkit"
mkdir -p "$CR/MAT/bank"; touch "$CR/MAT/bank/MAT-2023-01.md" "$CR/MAT/bank/MAT-2023-01.index.tsv" "$CR/MAT/bank/MAT-2024-01.md" "$CR/MAT/bank/MAT-2024-01.index.tsv"
touch "$CR/MAT/syllabus.md" "$CR/MAT/formula_sheet.md" "$CR/MAT/seeds.md" "$CR/MAT/blueprint.md" "$CR/MAT/bank/index.tsv"
run cs pass-mark MAT 5.6 --why "test"; assert_rc "pass-mark before the blueprint refused" 1
cp "$FIX/EMP/blueprint.json" "$CR/MAT/blueprint.json"
python3 - "$CR/MAT/blueprint.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); d["course"] = "MAT"; json.dump(d, open(sys.argv[1], "w"))
PY
run cs state MAT; assert_has "  next is the pass mark" "$OUT" "next: pass_mark"
run cs pass-mark MAT 11 --why x; assert_rc "pass-mark above 10 refused" 1
run cs pass-mark MAT 5.625 --why "interim 5.0 counts 20%"; assert_rc "pass-mark" 0
run cs state MAT; assert_has "  set-up complete" "$OUT" "set-up complete"
run python3 "$CR/tools/ledger.py" mastery MAT; assert_rc "ledger reads the blueprint with pass_grade_note" 0
run cs archive PHY --label "2026 Q1"; assert_rc "archive PHY" 0
[ -d "$CR/archive/2026 Q1/Physics one/materials" ] && [ ! -e "$CR/Physics one" ] && ok "  folder moved" || bad "  folder moved"
assert_has "  config entry kept in the archive" "$CR/archive/2026 Q1/config.json" '"Physics 1"'
run cs archive MAT --label "2026 Q1"; assert_rc "archive the last course" 0
run python3 "$CR/tools/ledger.py" status; assert_rc "ledger status with no courses left" 0
run cs archive MAT; assert_rc "archiving an unknown course fails" 1

section "doctor.py"
run python3 "$ROOT/tools/doctor.py" --quick
if [ "$rc" -le 1 ]; then ok "doctor runs (exit $rc)"; else bad "doctor exit $rc" "$(head -c 400 "$ERR")"; fi
assert_has "  reports the core group" "$OUT" "core"
run python3 "$ROOT/tools/doctor.py" --quick --json
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert {'group','name','ok'} <= set(d[0])" "$OUT" && ok "  --json parses" || bad "doctor --json" "$(head -c 300 "$OUT")"

# ------------------------------------------------------------------------------ hygiene
section "hygiene"
real_dirs=()
if [ -f "$REAL_ROOT/tools/config.json" ]; then
    while IFS= read -r d; do [ -d "$REAL_ROOT/$d" ] && real_dirs+=("$REAL_ROOT/$d"); done < <(
        python3 -c "import json,sys; [print(c['dir']) for c in json.load(open(sys.argv[1]))['courses'].values()]" "$REAL_ROOT/tools/config.json")
fi
leaked=""
[ ${#real_dirs[@]} -gt 0 ] && leaked=$(find "${real_dirs[@]}" \( -name 'X-*' -o -name 'RPT-*' -o -name 'EMP-*' -o -name 'CK-*' -o -name 'HLP-*' -o -name 'HNT-*' -o -name 'ledger.jsonl.*tmp' \) 2>/dev/null | head -3)
assert_eq "no test artefacts in the real course directories" "$leaked" ""
assert_eq "tests ran in a throw-away copy, not in the real tree" "$(case $ROOT in "$REAL_ROOT"*) echo real ;; *) echo temp ;; esac)" "temp"

echo
if [ $fail -eq 0 ]; then
    echo "tools tests: all $pass checks passed"
    exit 0
fi
echo "tools tests: $fail FAILED, $pass passed"
exit 1
