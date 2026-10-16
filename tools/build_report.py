#!/usr/bin/env python3
"""Rebuild progress/progress.tex and progress/progress.pdf from scratch.

One document for all courses in tools/config.json.  Reads blueprint.json, ledger.jsonl,
sets/ and feedback/ of every course (read-only), writes only <root>/progress/progress.tex
and progress.pdf.  Missing or broken data never stops the build: the affected course shows
"nothing yet" or a data-problem note, and a WARN line is printed.

  build_report.py [--no-pdf] [--today YYYY-MM-DD]

Text from agents is escaped for LaTeX.  Only well-formed $...$ pairs pass through as math,
and each distinct math snippet is test-compiled first; a snippet that LaTeX rejects (an
undefined macro, say) is shown as plain text instead of breaking the report.
Exit status: 0 if the PDF was built (possibly with WARN lines), 1 otherwise.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger as L  # noqa: E402

F = Fraction
TOOLS, ROOT = L.TOOLS, L.ROOT
TEXDIR = TOOLS / "tex"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
KIND_LABEL = {"diagnostic": "diagnostic", "train": "training", "full": "full mock", "holdout": "held-out"}
STATUS_MACRO = {"exam-ready": "\\sready", "close": "\\sclose", "needs-work": "\\sneeds", "unmeasured": "\\snone"}
STATUS_COLOR = {"exam-ready": "prepgreen", "close": "prepamber", "needs-work": "prepred", "unmeasured": "prepgrey"}
BAR_MM = 22
MISTAKE_LIMIT = 20
HINT_LIMIT = 12        # rows in the "Hints" section
TIME_SETS = 3          # the "Time" section looks at this many most recent sets


# --------------------------------------------------------------------------- escaping

SPECIAL = {
    "\\": "\\textbackslash{}", "{": "\\{", "}": "\\}", "$": "\\$", "&": "\\&", "#": "\\#", "%": "\\%",
    "_": "\\_\\allowbreak{}", "^": "\\textasciicircum{}", "~": "\\textasciitilde{}",
    "<": "\\textless{}", ">": "\\textgreater{}", "|": "\\textbar{}", "/": "/\\allowbreak{}",
}

_GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "varepsilon", "ϵ": "epsilon", "ζ": "zeta",
          "η": "eta", "θ": "theta", "ϑ": "vartheta", "ι": "iota", "κ": "kappa", "λ": "lambda", "μ": "mu",
          "ν": "nu", "ξ": "xi", "π": "pi", "ρ": "rho", "σ": "sigma", "ς": "varsigma", "τ": "tau",
          "υ": "upsilon", "φ": "varphi", "ϕ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega",
          "Γ": "Gamma", "Δ": "Delta", "Θ": "Theta", "Λ": "Lambda", "Ξ": "Xi", "Π": "Pi", "Σ": "Sigma",
          "Φ": "Phi", "Ψ": "Psi", "Ω": "Omega", "µ": "mu"}
_SYMBOLS = {"ħ": "hbar", "ℏ": "hbar", "≈": "approx", "≠": "neq", "≤": "leq", "≥": "geq", "≪": "ll", "≫": "gg",
            "→": "rightarrow", "←": "leftarrow", "↔": "leftrightarrow", "⇒": "Rightarrow", "⇐": "Leftarrow",
            "⇔": "Leftrightarrow", "↦": "mapsto", "∞": "infty", "±": "pm", "∓": "mp", "×": "times",
            "÷": "div", "·": "cdot", "⋅": "cdot", "∂": "partial", "∇": "nabla", "∫": "int", "∑": "sum",
            "∏": "prod", "√": "surd", "∈": "in", "∉": "notin", "⊂": "subset", "⊆": "subseteq", "∪": "cup",
            "∩": "cap", "∀": "forall", "∃": "exists", "∅": "emptyset", "∼": "sim", "∝": "propto",
            "≡": "equiv", "⟨": "langle", "⟩": "rangle", "∘": "circ", "⊗": "otimes", "⊕": "oplus",
            "†": "dagger", "∠": "angle", "∥": "parallel", "⊥": "perp", "≅": "cong", "≃": "simeq",
            "−": "minus", "′": "prime"}
UNI_MATH = {k: "\\" + v for k, v in {**_GREEK, **_SYMBOLS}.items()}
UNI_MATH["−"] = "-"
UNI_MATH["′"] = "'"
UNI_TEXT = {k: "\\ensuremath{" + v + "}" for k, v in UNI_MATH.items()}
UNI_TEXT.update({
    "–": "--", "—": "---", "‘": "`", "’": "'", "“": "``", "”": "''", "…": "\\ldots{}", "•": "\\textbullet{}",
    " ": "~", " ": "\\,", " ": "\\,", "−": "\\ensuremath{-}", "′": "'", "°": "\\textdegree{}",
    "²": "\\textsuperscript{2}", "³": "\\textsuperscript{3}", "¹": "\\textsuperscript{1}", "⁻": "\\textsuperscript{-}",
    "₀": "\\textsubscript{0}", "₁": "\\textsubscript{1}", "₂": "\\textsubscript{2}", "₃": "\\textsubscript{3}",
    "✓": "\\ensuremath{\\checkmark}", "✔": "\\ensuremath{\\checkmark}", "­": "\\-",
    "·": "\\textperiodcentered{}", "±": "\\ensuremath{\\pm}",
})
UNI_TEXT["√"] = "\\ensuremath{\\surd}"

MATH_DENY = set("""input include includeonly write openin openout read readline closein closeout def edef gdef
xdef let futurelet newcommand renewcommand providecommand newenvironment renewenvironment
DeclareRobustCommand DeclareMathOperator usepackage RequirePackage documentclass catcode csname endcsname
immediate special directlua luaexec jobname newcount newdimen newif par verb item section subsection
subsubsection chapter paragraph part newpage clearpage pagebreak else fi or cr crcr halign valign noalign
span omit protect""".split())
MATH_ENVS = {"matrix", "pmatrix", "bmatrix", "vmatrix", "Vmatrix", "Bmatrix", "smallmatrix", "cases", "aligned",
             "gathered", "array", "split"}
MAX_MATH_LEN = 400


def esc_char(c):
    if c in SPECIAL:
        return SPECIAL[c]
    o = ord(c)
    if o < 32 or o == 127:
        return " "
    if o < 128:
        return c
    if c in UNI_TEXT:
        return UNI_TEXT[c]
    if 0xC0 <= o <= 0x17F and c not in "×÷":
        return c
    return "\\textbf{[U+%04X]}" % o


def find_close(s, i):
    """Index of the `$` closing the math that opens at s[i], or -1 (pandoc-style rules)."""
    n = len(s)
    if i + 1 >= n or s[i + 1].isspace() or s[i + 1] == "$":
        return -1
    k = i + 1
    while k < n:
        c = s[k]
        if c == "\\":
            k += 2
            continue
        if c == "$":
            if s[k - 1].isspace() or (k + 1 < n and s[k + 1].isdigit()):
                return -1
            return k
        k += 1
    return -1


def check_math(inner):
    """Static well-formedness filter.  Returns the math with Unicode converted, or None."""
    if not inner.strip() or len(inner) > MAX_MATH_LEN:
        return None
    conv = []
    for ch in inner:
        if ord(ch) < 128:
            conv.append(ch)
        elif ch in UNI_MATH:
            conv.append(UNI_MATH[ch] + " ")
        else:
            return None
    s = "".join(conv).strip()
    n, i, depth, envs = len(s), 0, 0, []
    while i < n:
        c = s[i]
        if c == "\\":
            if i + 1 >= n:
                return None
            nx = s[i + 1]
            if nx.isalpha():
                j = i + 1
                while j < n and s[j].isalpha():
                    j += 1
                name = s[i + 1:j]
                if name in MATH_DENY or (name.startswith("if") and name != "iff"):
                    return None
                if name in ("begin", "end"):
                    m = re.match(r"\s*\{([A-Za-z]+)\}", s[j:])
                    if not m or m.group(1) not in MATH_ENVS:
                        return None
                    if name == "begin":
                        envs.append(m.group(1))
                    else:
                        if not envs or envs.pop() != m.group(1):
                            return None
                    j += m.end()
                i = j
                continue
            if nx == "\\":
                return None
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                return None
        elif c in "%#$":
            return None
        elif c == "&" and not envs:
            return None
        i += 1
    if depth != 0 or envs:
        return None
    return s


class Tex:
    """Escapes agent text for LaTeX; well-formed $...$ pairs pass through as math."""

    def __init__(self, bad_math=frozenset(), all_math_bad=False):
        self.bad = set(bad_math)
        self.all_bad = all_math_bad
        self.seen = {}

    def math(self, inner):
        conv = check_math(inner)
        if conv is None or self.all_bad or conv in self.bad:
            return None
        self.seen[conv] = True
        return "$" + conv + "$"

    def __call__(self, text):
        if text is None:
            return ""
        s = " ".join(str(text).split())
        out, i, n = [], 0, len(s)
        while i < n:
            c = s[i]
            if c == "\\" and i + 1 < n and s[i + 1] in "&%$#_{}":
                out.append(esc_char(s[i + 1]))
                i += 2
                continue
            if c == "$":
                j = find_close(s, i)
                if j > 0:
                    m = self.math(s[i + 1:j])
                    out.append(m if m is not None else "".join(esc_char(x) for x in s[i:j + 1]))
                    i = j + 1
                    continue
            out.append(esc_char(c))
            i += 1
        return "".join(out)


# --------------------------------------------------------------------------- number / date formats

def half_up(x, nd):
    q = F(10) ** nd
    return int((F(x) * q + F(1, 2)) // 1) / float(q)


def fmt_grade(x):
    return "--" if x is None else f"{half_up(x, 1):.1f}"


def fmt_pct(x, nd=0):
    return "--" if x is None else f"{half_up(F(x) * 100, nd):.{nd}f}\\,\\%"


def fmt_num(x):
    return L.fmt_num(x)


def fmt_pts(x):
    v = half_up(x, 1)
    return str(int(v)) if v == int(v) else f"{v:.1f}"


def fmt_date(d):
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return f"{L.WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


def fmt_short(d):
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return f"{d.day} {MONTHS[d.month - 1]}"


# --------------------------------------------------------------------------- data gathering

class CourseData:
    def __init__(self, cfg, course, on_date):
        self.course = course
        self.state = L.CourseState(cfg, course, on_date)
        self.summary = self.state.summary()
        self.plan = None
        self.plan_problem = None
        self.times = {}
        self.problems = []
        st = self.state
        if st.bp is None and st.problem and "file not found" not in st.problem:
            self.problems.append(st.problem)
        if st.ledger_problem:
            self.problems.append(st.ledger_problem)
        self.problems += st.warnings
        if st.bp is not None and not st.ledger_problem:
            try:
                self.plan = L.plan_next(cfg, course, st.bp, st.rows, "train", None, on_date, st)
            except L.DataError as e:
                self.plan_problem = "; ".join(e.msgs)
            for s in st.sets:
                self.times[s["set"]] = self.read_time(s["set"])

    def read_time(self, set_id):
        try:
            fb = L.load_json(self.course.path / "feedback" / f"{set_id}.json")
        except L.DataError:
            return None
        t = fb.get("time_spent_min") if isinstance(fb, dict) else None
        return t if L.is_num(t) else None

    def error_breakdown(self):
        """{tag: [items, points lost]} plus the total; points are split evenly between an item's tags."""
        tags, total, n_items = {}, F(0), 0
        for r in self.state.rows:
            if r["status"] == "skipped_not_covered":
                continue
            lost = L.fr(r["max"]) - L.fr(r["score"])
            if lost <= 0:
                continue
            use = r["errors"] or ["(untagged)"]
            n_items += 1
            total += lost
            for t in use:
                e = tags.setdefault(t, [0, F(0)])
                e[0] += 1
                e[1] += lost / len(use)
        order = list(L.ERROR_TAGS) + ["(untagged)"]
        rows = sorted(tags.items(), key=lambda kv: (-kv[1][1], order.index(kv[0])))
        return rows, total, n_items

    def time_overruns(self):
        """(sets looked at, rows that took more than 1.5 x budget, rows with a time) for the last
        TIME_SETS recorded sets; rows are in set order, then file order."""
        sets = [s["set"] for s in self.state.sets[-TIME_SETS:]]
        rows = [r for sid in sets for r in self.state.rows
                if r["set"] == sid and r["status"] != "skipped_not_covered"]
        timed = [r for r in rows if L.row_minutes(r) is not None]
        return sets, [r for r in rows if L.row_slow(r)], len(timed)

    def hints(self):
        """(hinted row, the next attempt at the same question type or None), newest first."""
        rows = [r for r in L.chrono(self.state.rows) if r["status"] != "skipped_not_covered"]
        out = []
        for i, r in enumerate(rows):
            if L.row_hint(r):
                later = next((x for x in rows[i + 1:] if x["archetype"] == r["archetype"]), None)
                out.append((r, later))
        out.reverse()
        return out[:HINT_LIMIT], len(out)

    def mistakes(self):
        """Takeaways of items that lost points, carry tags or were assisted, newest set first, items in set order."""
        by_set = {}
        for r in self.state.rows:
            if r["status"] == "skipped_not_covered" or not (r.get("takeaway") or "").strip():
                continue
            if not (r["errors"] or L.fr(r["score"]) < L.fr(r["max"]) or L.row_assisted(r)):
                continue
            by_set.setdefault(r["set"], []).append(r)
        order = sorted(self.state.sets, key=lambda s: (s["date"], s["first_index"]), reverse=True)
        out = []
        for s in order:
            out += by_set.get(s["set"], [])
        return out[:MISTAKE_LIMIT], sum(len(v) for v in by_set.values())


# --------------------------------------------------------------------------- LaTeX building blocks

PREAMBLE = r"""\documentclass[a4paper,10pt]{article}
\usepackage[report]{prep}
\usepackage{longtable,array,titlesec}
\hypersetup{pdftitle={Exam preparation progress},pdfauthor={tools/build_report.py}}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small Exam preparation progress}
\fancyhead[R]{\small generated @@DATE@@}
\fancyfoot[C]{\small\thepage\ / \pageref{LastPage}}
\renewcommand{\headrulewidth}{0.3pt}
\titleformat{\section}{\Large\bfseries}{}{0pt}{}
\titleformat{\subsection}{\large\bfseries}{}{0pt}{}
\titlespacing*{\section}{0pt}{0pt}{6pt}
\titlespacing*{\subsection}{0pt}{13pt}{4pt}
\setlength{\parskip}{0.35\baselineskip plus 1pt}
\setlength{\LTleft}{0pt}\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\renewcommand{\arraystretch}{1.2}
\newcolumntype{P}[1]{>{\raggedright\arraybackslash}p{#1}}
\newcommand{\sready}{\textcolor{prepgreen}{\textbf{exam-ready}}}
\newcommand{\sclose}{\textcolor{prepamber}{\textbf{close}}}
\newcommand{\sneeds}{\textcolor{prepred}{\textbf{needs-work}}}
\newcommand{\snone}{\textcolor{prepgrey}{\textit{unmeasured}}}
\newcommand{\hd}[2]{\shortstack[l]{#1\\#2}}
\newcommand{\hdr}[2]{\shortstack[r]{#1\\#2}}
\newcommand{\smallnote}[1]{{\footnotesize\color{prepgrey}#1\par}}
% mastery bar: #1 = filled width in mm (0..22), #2 = colour; ticks at 0.55 and 0.80
\newcommand{\mbar}[2]{\begin{tikzpicture}[baseline=0.4mm]
  \fill[black!9] (0,0) rectangle (22mm,2.4mm);
  \fill[#2] (0,0) rectangle (#1mm,2.4mm);
  \draw[black!55,line width=0.25pt] (0,0) rectangle (22mm,2.4mm);
  \draw[black!80,line width=0.3pt] (12.1mm,-0.5mm) -- (12.1mm,0mm) (12.1mm,2.4mm) -- (12.1mm,2.9mm);
  \draw[black!80,line width=0.3pt] (17.6mm,-0.5mm) -- (17.6mm,0mm) (17.6mm,2.4mm) -- (17.6mm,2.9mm);
\end{tikzpicture}}
\newcommand{\mbarnone}{\begin{tikzpicture}[baseline=0.4mm]
  \draw[black!45,dash pattern=on 1pt off 1pt,line width=0.3pt] (0,0) rectangle (22mm,2.4mm);
\end{tikzpicture}}
% points-lost bar: #1 = width in mm (max 30)
\newcommand{\lbar}[1]{\begin{tikzpicture}[baseline=0.4mm]
  \fill[black!55] (0,0) rectangle (#1mm,2.4mm);
\end{tikzpicture}}
\begin{document}
"""


class Report:
    def __init__(self, datas, on_date, tex):
        self.datas, self.date, self.T = datas, on_date, tex
        self.out = []
        self.errors = []

    def safe(self, label, fn, *args):
        """Run one report section; if it fails, drop its partial output and say so in the document."""
        mark = len(self.out)
        try:
            fn(*args)
        except Exception as e:  # noqa: BLE001 - the report must still build
            del self.out[mark:]
            msg = f"{label}: {type(e).__name__}: {e}"
            self.errors.append(msg)
            self.add(f"\\par\\textit{{This section could not be built ({self.T(msg)}).}}\\par")

    def add(self, s=""):
        self.out.append(s)

    # ---- overview -------------------------------------------------------------------
    def overview(self):
        T = self.T
        self.add("\\section*{Exam preparation progress}")
        self.add(f"\\noindent Generated {T(fmt_date(self.date))} {self.date.year}. "
                 "Grades are on a 0--10 scale; ``measured'' and ``banked'' are estimates, not predictions to lean on.\\par")
        self.add("\\vspace{0.6em}")
        self.add("\\begingroup\\small\\setlength{\\tabcolsep}{3.5pt}")
        self.add("\\begin{tabular}{@{}P{37mm} l r r r P{19mm} r r r P{25mm}@{}}")
        self.add("\\toprule")
        self.add("Course & Exam & \\hdr{Days}{left} & \\hdr{Study}{days left} & \\hdr{Sets}{done} & "
                 "\\hd{Last}{set} & \\hdr{Grade}{measured} & Coverage & \\hdr{Grade}{banked} & "
                 "\\hd{Held-out}{exam} \\\\")
        self.add("\\midrule")
        for d in self.datas:
            s = d.summary
            name = f"\\textbf{{{T(d.course.key)}}}\\newline{{\\scriptsize {T(d.course.name)}}}"
            dl = s["days_left"]
            days = str(dl) if dl >= 0 else "past"
            sd = str(s["study_days_left"]) if dl >= 0 else "--"
            last = "--"
            if s["last_set"]:
                ls = s["last_set"]
                pct = "" if ls["pct"] is None else f" {fmt_pct(ls['pct'])}"
                last = f"{T(ls['set'])}\\newline{{\\scriptsize {fmt_num(ls['score'])}/{fmt_num(ls['max'])}{pct}}}"
            g = d.state.grades
            meas = fmt_grade(g["grade_on_measured"]) if g else "--"
            cov = fmt_pct(g["coverage"]) if g else "--"
            bank = fmt_grade(g["grade_banked"]) if g else "--"
            ho = "--"
            if s["holdout"]:
                h = s["holdout"]
                hp = "" if h["pct"] is None else fmt_pct(h["pct"])
                ge = "" if h["grade_eq"] is None else f", grade {fmt_grade(h['grade_eq'])}"
                ho = f"{T(h['set'])}\\newline{{\\scriptsize {hp}{ge}}}"
            self.add(f"{name} & {T(fmt_date(d.course.exam_date))} & {days} & {sd} & {s['sets_done']} & {last} & "
                     f"{meas} & {cov} & {bank} & {ho} \\\\")
        self.add("\\bottomrule")
        self.add("\\end{tabular}\\endgroup")
        self.add("")
        self.add("\\subsection*{What the three grade figures mean}")
        self.add("\\begin{description}[leftmargin=0pt,labelsep=0.5em,itemsep=0.3em,font=\\bfseries]")
        self.add("\\item[Grade measured] The grade you would get if the exam only contained the topics you have "
                 "practised at least once, and you did them as well as your recent work suggests. "
                 "Optimistic while coverage is low.")
        self.add("\\item[Coverage] The share of the exam's points that sits in topics you have practised at least once.")
        self.add("\\item[Grade banked] The grade you would get today if every topic you have not practised yet "
                 "scored zero. Cautious: it only goes up as you cover more and master more.")
        self.add("\\end{description}")
        self.add("Mastery of a topic is a weighted average of your scores on it, newest work counting double the "
                 "work before it; full marks on easier-than-exam questions count for less. The grade is "
                 "10 $\\times$ the weighted mastery.\\par")
        self.grade_picture()
        probs = [(d.course.key, p) for d in self.datas for p in d.problems]
        if probs:
            self.add("\\subsection*{Data problems}")
            self.add("\\begin{itemize}[leftmargin=1.2em,itemsep=0.1em,topsep=0.2em]")
            for k, p in probs:
                self.add(f"\\item {{\\small \\textbf{{{T(k)}}}: {T(p)}}}")
            self.add("\\end{itemize}")

    def grade_picture(self):
        T = self.T
        rows = [d for d in self.datas if d.state.grades is not None]
        if not rows:
            return
        self.add("\\subsection*{Where you stand}")
        W = 100.0
        self.add("\\begin{center}\\begin{tikzpicture}[x=1mm,y=1mm]")
        n = len(rows)
        for i, d in enumerate(rows):
            y = -i * 8.0
            g = d.state.grades
            pg = float(d.state.bp["pass_grade"])
            self.add(f"\\node[anchor=east,font=\\small\\bfseries] at (-2,{y}) {{{T(d.course.key)}}};")
            self.add(f"\\fill[black!8] (0,{y - 2.6}) rectangle ({W},{y + 2.6});")
            self.add(f"\\fill[black!60] (0,{y - 2.6}) rectangle ({float(g['grade_banked']) * W / 10:.2f},{y + 2.6});")
            if g["grade_on_measured"] is not None:
                x = float(g["grade_on_measured"]) * W / 10
                self.add(f"\\draw[fill=white,line width=0.6pt] ({x - 1.9:.2f},{y}) -- ({x:.2f},{y + 1.9}) -- "
                         f"({x + 1.9:.2f},{y}) -- ({x:.2f},{y - 1.9}) -- cycle;")
            self.add(f"\\draw[dashed,black!85,line width=0.5pt] ({pg * W / 10:.2f},{y - 3.6}) -- ({pg * W / 10:.2f},{y + 3.6});")
            lab = f"banked {fmt_grade(g['grade_banked'])}"
            if g["grade_on_measured"] is not None:
                lab += f", measured {fmt_grade(g['grade_on_measured'])}"
            self.add(f"\\node[anchor=west,font=\\scriptsize] at ({W + 3},{y}) {{{lab}}};")
        yb = -(n - 1) * 8.0 - 5.2
        for v in (0, 5, 10):
            self.add(f"\\node[anchor=north,font=\\scriptsize] at ({v * W / 10:.1f},{yb}) {{{v}}};")
        self.add("\\end{tikzpicture}\\end{center}")
        self.add("\\smallnote{Dark bar: banked grade. Diamond: grade on the measured part. Dashed line: pass mark.}")

    # ---- per course -----------------------------------------------------------------
    def course(self, d):
        T = self.T
        c, s, st = d.course, d.summary, d.state
        self.add("\\clearpage")
        self.add(f"\\section*{{{T(c.key)} \\textemdash\\ {T(c.name)}}}")
        dl = s["days_left"]
        bits = [f"Exam {T(fmt_date(c.exam_date))} {c.exam_date.year}"]
        bits.append(f"{dl} days left, {s['study_days_left']} study days" if dl >= 0 else "exam date has passed")
        if st.grades is not None and st.sets:
            bits.append(f"grade measured {fmt_grade(st.grades['grade_on_measured'])}, banked {fmt_grade(st.grades['grade_banked'])}, "
                        f"coverage {fmt_pct(st.grades['coverage'])}")
        self.add("\\noindent " + "; ".join(bits) + ".\\par")
        if st.bp is None:
            if st.problem and "file not found" not in st.problem:
                self.add(f"\\par\\textbf{{Blueprint unreadable:}} {T(st.problem)}\\par")
            self.add("\\subsection*{Mastery}\\textit{Nothing yet: no blueprint has been written for this course.}\\par")
            return
        if st.ledger_problem:
            self.add(f"\\par\\textbf{{Ledger unreadable:}} {T(st.ledger_problem)}\\par")
            self.add("\\textit{Nothing can be shown until the ledger is fixed.}\\par")
            return
        for fn in (self.mastery, self.history, self.points, self.time, self.mistakes, self.hints, self.next_up):
            self.safe(f"{c.key} {fn.__name__}", fn, d)

    def mastery(self, d):
        T, st = self.T, d.state
        self.add("\\subsection*{Mastery per question type}")
        groups = {}
        for a in st.bp["archetypes"]:
            groups.setdefault(a["group"], []).append(a)
        self.add("\\begingroup\\small")
        self.add("\\begin{longtable}{@{}P{58mm} r r r r l l@{}}")
        head = ("Question type & Weight & Attempts & Assisted & \\hdr{Last}{level} & "
                "Mastery & Status \\\\")
        self.add("\\toprule " + head + " \\midrule \\endfirsthead")
        self.add("\\toprule " + head + " \\midrule \\endhead")
        self.add("\\bottomrule \\endfoot")
        for g, arch in groups.items():
            self.add(f"\\addlinespace[0.5ex]\\multicolumn{{7}}{{@{{}}l}}{{\\textbf{{\\textsc{{{T(g)}}}}}}} \\\\ \\midrule")
            for a in arch:
                s = st.stats[a["id"]]
                w = f"{T(L.pct_str(a['w'], 1))}\\,\\%"
                name = T(a["name"])
                if a["covered_from"] is not None and a["covered_from"] > self.date:
                    name += f"\\newline{{\\scriptsize\\color{{prepgrey}}lectured from {T(fmt_short(a['covered_from']))}}}"
                if s["mastery"] is None:
                    self.add(f"{{\\leavevmode\\color{{prepgrey}}{name}}} & {{\\color{{prepgrey}}{w}}} & {{\\color{{prepgrey}}0}} & "
                             f"{{\\color{{prepgrey}}0}} & {{\\color{{prepgrey}}--}} & \\mbarnone\\ {{\\color{{prepgrey}}--}} & \\snone \\\\")
                else:
                    m = float(s["mastery"])
                    self.add(f"{name} & {w} & {s['attempts']} & {s['assisted']} & L{s['last_level']} & "
                             f"\\mbar{{{m * BAR_MM:.2f}}}{{{STATUS_COLOR[s['status']]}}}\\ {m:.2f} & {STATUS_MACRO[s['status']]} \\\\")
        self.add("\\end{longtable}")
        self.add("\\vspace{-1.2em}\\smallnote{Bars run from 0 to 1; the ticks mark 0.55 (close) and 0.80 (exam-ready). "
                 "Dashed bar: not attempted yet. Weight is the topic's expected share of the exam's points. "
                 "Assisted: attempts written with outside help; only the unaided work was scored.}")
        self.add("\\endgroup")

    def history(self, d):
        T, st = self.T, d.state
        self.add("\\subsection*{Set history}")
        if not st.sets:
            self.add("\\textit{Nothing yet: no set has been graded.}\\par")
            return
        bp = st.bp
        self.add("\\begingroup\\small")
        self.add("\\begin{longtable}{@{}l l l r r r r r r@{}}")
        head = ("Set & Date & Kind & Score & Percent & \\hdr{Grade}{equivalent} & \\hdr{Time}{spent} & "
                "\\hdr{Time vs}{budget} & \\hdr{Assisted}{items} \\\\")
        self.add("\\toprule " + head + " \\midrule \\endfirsthead")
        self.add("\\toprule " + head + " \\midrule \\endhead")
        self.add("\\bottomrule \\endfoot")
        for s in st.sets:
            t = d.times.get(s["set"])
            tt = "--" if t is None else f"{fmt_num(t)} min"
            tb = "--" if s["time_ratio"] is None else fmt_pct(s["time_ratio"])
            self.add(f"{T(s['set'])} & {T(fmt_short(s['date']))} & {T(KIND_LABEL.get(s['kind'], s['kind']))} & "
                     f"{fmt_num(s['score'])}/{fmt_num(s['max'])} & {fmt_pct(s['pct'])} & {fmt_grade(s['grade_eq'])} & {tt} & {tb} & {s['assisted']} \\\\")
        self.add("\\end{longtable}")
        self.add("\\vspace{-1.2em}\\smallnote{Grade equivalent: the set's percentage applied to the full exam "
                 f"({fmt_num(bp['total_points'])} points, grade = points / {fmt_num(bp['grade_divisor'])}). "
                 "Items skipped as not yet covered are left out of the score. "
                 "Time vs budget: minutes spent over minutes budgeted, for the items that have a time stamp. "
                 "Assisted items were written with outside help and score only their unaided part.}")
        self.add("\\endgroup")
        if len(st.sets) >= 2:
            self.plot(d)

    def plot(self, d):
        st, bp = d.state, d.state.bp
        sets = [s for s in st.sets if s["pct"] is not None]
        if len(sets) < 2:
            return
        d0 = date.fromisoformat(sets[0]["date"])
        xs = [(date.fromisoformat(s["date"]) - d0).days for s in sets]
        xmax = max(xs[-1], 1)
        pad = max(1, round(xmax * 0.04))
        ticks = sorted({x for x in xs})
        if len(ticks) > 7:
            step = (len(ticks) - 1) / 6.0
            ticks = sorted({ticks[round(i * step)] for i in range(7)})
        labels = [fmt_short(date.fromordinal(d0.toordinal() + x)) for x in ticks]
        passpct = float(F(str(bp["pass_grade"])) * F(str(bp["grade_divisor"])) / F(str(bp["total_points"])) * 100)
        self.add("\\par\\begin{center}\\begin{tikzpicture}")
        self.add("\\begin{axis}[width=0.92\\linewidth,height=46mm,ymin=0,ymax=100,"
                 f"xmin={-pad},xmax={xmax + pad},ytick={{0,25,50,75,100}},"
                 f"xtick={{{','.join(str(t) for t in ticks)}}},xticklabels={{{','.join(labels)}}},"
                 "tick label style={font=\\scriptsize},label style={font=\\scriptsize},"
                 "ylabel={score (\\%)},grid=major,grid style={black!12},"
                 "legend style={font=\\scriptsize,at={(0.5,-0.2)},anchor=north,legend columns=-1,draw=none,/tikz/every even column/.append style={column sep=7pt}},"
                 "every axis plot/.append style={thick}]")
        coords = " ".join(f"({x},{float(s['pct']) * 100:.1f})" for x, s in zip(xs, sets))
        self.add(f"\\addplot[black!50,thin,forget plot] coordinates {{{coords}}};")
        marks = {"diagnostic": "triangle*", "train": "*", "full": "square*", "holdout": "diamond*"}
        for kind, mk in marks.items():
            pts = [(x, s) for x, s in zip(xs, sets) if s["kind"] == kind]
            if pts:
                cs = " ".join(f"({x},{float(s['pct']) * 100:.1f})" for x, s in pts)
                self.add(f"\\addplot[only marks,mark={mk},mark size=2.3pt,black] coordinates {{{cs}}};")
                self.add(f"\\addlegendentry{{{KIND_LABEL[kind]}}}")
        self.add(f"\\addplot[dashed,black!70,thin,no marks] coordinates {{({-pad},{passpct:.1f}) ({xmax + pad},{passpct:.1f})}};")
        self.add(f"\\addlegendentry{{pass mark ({passpct:.0f}\\,\\%)}}")
        self.add("\\end{axis}\\end{tikzpicture}\\end{center}")

    def points(self, d):
        T = self.T
        self.add("\\subsection*{Where the points go}")
        rows, total, n_items = d.error_breakdown()
        if not rows:
            self.add("\\textit{Nothing yet: no lost points have been recorded.}\\par")
            return
        mx = max(r[1][1] for r in rows)
        self.add("\\begingroup\\small")
        self.add("\\begin{tabular}{@{}l P{78mm} r r l@{}}")
        self.add("\\toprule Error type & Meaning & Items & \\hdr{Points}{lost} & \\\\ \\midrule")
        for tag, (n, pts) in rows:
            meaning = L.ERROR_TAGS.get(tag, "graded without an error tag")
            w = 30 * float(pts / mx)
            self.add(f"{T(tag)} & {T(meaning)} & {n} & {fmt_pts(pts)} & \\lbar{{{w:.1f}}} \\\\")
        self.add(f"\\midrule \\textbf{{Total}} & & {n_items} & {fmt_pts(total)} & \\\\")
        self.add("\\bottomrule\\end{tabular}")
        self.add("\\par\\vspace{0.3em}\\smallnote{Points lost on an item with several error types are split evenly between them. "
                 "``Items'' counts each lost-points item once per type.}")
        self.add("\\endgroup")

    def time(self, d):
        T, st = self.T, d.state
        self.add("\\subsection*{Time}")
        sets, slow, n_timed = d.time_overruns()
        if not sets:
            self.add("\\textit{Nothing yet: no set has been graded.}\\par")
            return
        span = "set" if len(sets) == 1 else f"{len(sets)} sets"
        if n_timed == 0:
            self.add(f"\\textit{{Nothing yet: no item times were recorded in the last {span}.}}\\par")
            return
        if not slow:
            self.add(f"\\noindent No item took more than 1.5 times its budget in the last {span} "
                     f"({T(', '.join(sets))}).\\par")
            return
        self.add(f"\\noindent Items that took more than 1.5 times their budget in the last {span} "
                 f"({T(', '.join(sets))}).\\par")
        names = {a["id"]: a["name"] for a in st.bp["archetypes"]}
        self.add("\\begingroup\\small")
        self.add("\\begin{longtable}{@{}P{25mm} P{86mm} r r r@{}}")
        head = "Set \\textperiodcentered\\ item & Question type & Minutes & Budget & Ratio \\\\"
        self.add("\\toprule " + head + " \\midrule \\endfirsthead")
        self.add("\\toprule " + head + " \\midrule \\endhead")
        self.add("\\bottomrule \\endfoot")
        for r in slow:
            used, budget = r["minutes"], r["budget_minutes"]
            ratio = float(L.fr(used) / L.fr(budget))
            self.add(f"{T(r['set'])} \\textperiodcentered\\ {T(r['item'])} & "
                     f"{T(names.get(r['archetype'], r['archetype']))} & "
                     f"{fmt_num(used)} & {fmt_num(budget)} & {ratio:.2f}$\\times$ \\\\")
        self.add("\\end{longtable}")
        self.add("\\endgroup")

    def mistakes(self, d):
        T = self.T
        self.add("\\subsection*{Mistake book}")
        shown, total = d.mistakes()
        if not shown:
            self.add("\\textit{Nothing yet: no takeaways have been recorded.}\\par")
            return
        self.add("\\begingroup\\small")
        self.add("\\begin{longtable}{@{}P{25mm} P{23mm} P{116mm}@{}}")
        head = "Set \\textperiodcentered\\ item & Error type & Takeaway \\\\"
        self.add("\\toprule " + head + " \\midrule \\endfirsthead")
        self.add("\\toprule " + head + " \\midrule \\endhead")
        self.add("\\bottomrule \\endfoot")
        for r in shown:
            tags = ", ".join(r["errors"]) if r["errors"] else "--"
            where = f"{T(r['set'])} \\textperiodcentered\\ {T(r['item'])}"
            tk = T(r["takeaway"])
            if r.get("confidence") == "low":
                tk = "\\textbf{[check reading]} " + tk
            if L.row_hint(r):
                tk = f"\\textbf{{[hint: {L.HINT_RUNGS[L.row_hint(r)['rung']]}]}} " + tk
            elif L.row_assisted(r):
                tk = "\\textbf{[needed help]} " + tk
            self.add(f"{where} & {T(tags)} & {tk} \\\\")
        self.add("\\end{longtable}")
        if total > len(shown):
            self.add(f"\\vspace{{-1.2em}}\\smallnote{{Showing the {len(shown)} most recent of {total} takeaways.}}")
        self.add("\\endgroup")

    def hints(self, d):
        T = self.T
        self.add("\\subsection*{Hints}")
        shown, total = d.hints()
        if not shown:
            self.add("\\textit{None yet: no item needed a hint from \\texttt{/hint} before it was attempted.}\\par")
            return
        self.add("\\noindent Items you asked a hint for before or during the attempt, what you had to be told, "
                 "and how the next attempt at that question type went.\\par")
        self.add("\\begingroup\\small")
        self.add("\\begin{longtable}{@{}P{25mm} P{14mm} P{88mm} P{34mm}@{}}")
        head = "Set \\textperiodcentered\\ item & Hint & What you needed & Next attempt \\\\"
        self.add("\\toprule " + head + " \\midrule \\endfirsthead")
        self.add("\\toprule " + head + " \\midrule \\endhead")
        self.add("\\bottomrule \\endfoot")
        for r, nxt in shown:
            h = L.row_hint(r)
            if nxt is None:
                after = "\\textit{not re-tested yet}"
            else:
                after = f"{T(nxt['set'])} \\textperiodcentered\\ {T(nxt['item'])}: {fmt_num(nxt['score'])}/{fmt_num(nxt['max'])}"
                if L.row_hint(nxt) or L.row_assisted(nxt):
                    after += ", help again"
                elif nxt["status"] == "blank":
                    after += ", blank"
            self.add(f"{T(r['set'])} \\textperiodcentered\\ {T(r['item'])} & {T(L.HINT_RUNGS[h['rung']])} & "
                     f"{T(h['learned'])} & {after} \\\\")
        self.add("\\end{longtable}")
        if total > len(shown):
            self.add(f"\\vspace{{-1.2em}}\\smallnote{{Showing the {len(shown)} most recent of {total} hints.}}")
        self.add("\\endgroup")

    def next_up(self, d):
        T = self.T
        self.add("\\subsection*{Next up}")
        plan = d.plan
        if plan is None:
            self.add(f"\\textit{{Not available: {T(d.plan_problem or 'no plan could be made')}}}\\par")
            return
        if not plan["items"]:
            self.add("\\textit{Nothing yet: no topic has been lectured as of today.}\\par")
            return
        self.add(f"\\noindent Next training set \\textbf{{{T(plan['set'])}}}: "
                 f"{fmt_num(plan['planned_minutes'])} of {fmt_num(plan['minutes'])} minutes, "
                 f"{fmt_num(plan['planned_points'])} points.\\par")
        self.add("\\begingroup\\small")
        self.add("\\begin{longtable}{@{}P{55mm} r r l P{60mm}@{}}")
        head = "Question type & Level & Minutes & Status & Why \\\\"
        self.add("\\toprule " + head + " \\midrule \\endfirsthead")
        self.add("\\toprule " + head + " \\midrule \\endhead")
        self.add("\\bottomrule \\endfoot")
        for it in plan["items"]:
            why = T(it["reason"]) + ("; right last time but too slow" if it.get("slow_last") else "")
            self.add(f"{T(it['name'])} & L{it['level']} & {fmt_num(it['minutes'])} & {STATUS_MACRO[it['status']]} & "
                     f"{{\\scriptsize {why}}} \\\\")
        self.add("\\end{longtable}")
        self.add("\\endgroup")

    # ---- whole document ---------------------------------------------------------------
    def build(self):
        self.add(PREAMBLE.replace("@@DATE@@", self.date.isoformat()).rstrip("\n"))
        self.safe("overview", self.overview)
        for d in self.datas:
            self.safe(f"{d.course.key}", self.course, d)
        self.add("\\end{document}")
        return "\n".join(self.out) + "\n"


def render(datas, on_date, bad_math=frozenset(), all_math_bad=False):
    tex = Tex(bad_math, all_math_bad)
    rep = Report(datas, on_date, tex)
    text = rep.build()
    return text, list(tex.seen), rep.errors


# --------------------------------------------------------------------------- compiling

def precheck_math(snippets):
    """Test-compile every distinct math snippet; return the set of those LaTeX rejects."""
    if not snippets:
        return set()
    header = ["\\documentclass[a4paper]{article}", "\\usepackage[report]{prep}", "\\begin{document}"]
    lines = header + [f"\\setbox0\\hbox{{${s}$}}" for s in snippets] + ["\\end{document}"]
    with tempfile.TemporaryDirectory(prefix="report_math_") as td:
        Path(td, "check.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
        env = dict(os.environ)
        tin = env.get("TEXINPUTS", "")
        if tin and not tin.endswith(":"):
            tin += ":"
        env["TEXINPUTS"] = f".:{TEXDIR}:{tin}"
        try:
            p = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-file-line-error", "check.tex"],
                               cwd=td, env=env, capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired):
            return set()
        bad = set()
        for m in re.finditer(r"^(?:\./)?check\.tex:(\d+):", p.stdout, re.M):
            i = int(m.group(1)) - len(header) - 1
            if 0 <= i < len(snippets):
                bad.add(snippets[i])
        return bad


def compile_pdf(tex_path):
    p = subprocess.run([str(TOOLS / "build_tex.sh"), str(tex_path)], capture_output=True, text=True)
    return p.returncode == 0, (p.stderr or p.stdout).strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rebuild progress/progress.tex and progress/progress.pdf.")
    ap.add_argument("--no-pdf", action="store_true", help="write progress.tex only")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD (default: today; env PREP_TODAY also works)")
    args = ap.parse_args(argv)
    try:
        cfg = L.load_config()
        if args.today:
            on_date = L.parse_date(args.today)
            if on_date is None:
                print(f"ERROR --today {args.today!r} is not a YYYY-MM-DD date", file=sys.stderr)
                return 2
        else:
            on_date = L.today()
    except L.DataError as e:
        return L.fail(e.msgs)

    datas = [CourseData(cfg, c, on_date) for c in cfg.courses.values()]
    warns = [f"{d.course.key}: {p}" for d in datas for p in d.problems]

    text, math, errors = render(datas, on_date)
    warns += [f"report section skipped, {e}" for e in errors]
    bad = precheck_math(math)
    if bad:
        warns += [f"math shown as plain text (LaTeX rejects it): ${m}$" for m in sorted(bad)]
        text, math, _ = render(datas, on_date, bad_math=bad)

    outdir = ROOT / "progress"
    outdir.mkdir(exist_ok=True)
    tex_path = outdir / "progress.tex"
    tex_path.write_text(text, encoding="utf-8")
    pdf_note = ""
    if not args.no_pdf:
        ok, msg = compile_pdf(tex_path)
        if not ok and math:
            first = msg.splitlines()[1] if len(msg.splitlines()) > 1 else msg
            warns.append(f"LaTeX failed with math passthrough ({first}); rebuilt with all math as plain text")
            text, _, _ = render(datas, on_date, all_math_bad=True)
            tex_path.write_text(text, encoding="utf-8")
            ok, msg = compile_pdf(tex_path)
        if not ok:
            print(msg, file=sys.stderr)
            print(f"ERROR could not build {L.rel(outdir / 'progress.pdf')}", file=sys.stderr)
            return 1
        pdf_note = " " + msg.rsplit("(", 1)[-1].rstrip(")") if "pages" in msg else ""
    n_sets = sum(d.summary["sets_done"] for d in datas)
    n_bp = sum(1 for d in datas if d.state.bp is not None)
    target = "progress.pdf" if not args.no_pdf else "progress.tex"
    print(f"{L.rel(outdir / target)} built{(' (' + pdf_note.strip() + ')') if pdf_note else ''}: "
          f"{len(datas)} courses, {n_bp} with blueprint, {n_sets} sets recorded, {len(warns)} warnings")
    for w in warns:
        print(f"WARN {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
