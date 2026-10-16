#!/usr/bin/env python3
"""Render a review storyboard as a short step-by-step maths video (Manim).

Usage: animate.sh STORYBOARD.json [--out OUT.mp4] [--sheet] [--draft]
       animate.sh STORYBOARD.json --lines

The storyboard is written by the /review session; its format is in
prompts/storyboard.md. The video plays the question, then the student's own lines one
at a time (each line grows out of the previous one), boxes the exact spot where it
went wrong with a one-line caption, rewinds to the last good line, continues correctly
from there, and ends on the takeaway.

Every line carries a number in the margin so the student can ask about "line 12":
the attempt lines are 1..n in storyboard order and the fix lines continue from n+1.
--lines prints that numbering (with each line's note) without rendering.

Output defaults to the storyboard path with .mp4. Layout problems (a line shrunk to fit,
a note too long) are printed as warnings. --sheet also writes OUT.sheet.png, one still
per step, to check the layout by eye. --draft renders 480p15 for a quick look. Run
through tools/animate.sh, which provides the Manim environment.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from manim import (DOWN, LEFT, RIGHT, UP, Create, FadeIn, FadeOut, Line, MathTex,
                   Scene, SurroundingRectangle, Tex, TexTemplate,
                   TransformMatchingShapes, VGroup, Write, config, tempconfig)

CACHE = Path.home() / ".cache" / "exam-prep-anim"

BG, FG, DIM = "#15171C", "#ECEFF4", "#7B818C"
GREEN, RED, AMBER, BLUE = "#6BD08F", "#FF6B6B", "#F2B65A", "#7AB8FF"
BAD_KEY, GOOD_KEY = "#FF0001", "#00FF01"     # marker colours set by \bad{} and \good{}

# frame is 14.22 x 8 units
TOP_Y, BOTTOM_Y = 2.85, -1.75                # math area
NUM_X, GUTTER_X, MATH_X, MATH_W = -6.75, -6.05, -5.35, 11.8
SUB_Y, SUB_X, SUB_W, SUB_H = -2.85, -6.15, 12.4, 1.55   # caption strip
MATH_FS, SUB_FS, CHROME_FS = 44, 34, 26
CM_PER_UNIT_48 = 1 / 1.4173                  # a 1 cm parbox is 1.4173 units at font size 48

PREAMBLE = r"""
\usepackage{mathtools,bm,cancel,xcolor,pifont,newunicodechar}
\newcommand{\bad}[1]{\textcolor[HTML]{FF0001}{#1}}
\newcommand{\good}[1]{\textcolor[HTML]{00FF01}{#1}}
\providecommand{\ket}[1]{\left|#1\right\rangle}
\providecommand{\bra}[1]{\left\langle#1\right|}
\providecommand{\braket}[2]{\left\langle#1\middle|#2\right\rangle}
\providecommand{\expval}[1]{\left\langle#1\right\rangle}
\providecommand{\abs}[1]{\left|#1\right|}
\providecommand{\norm}[1]{\left\lVert#1\right\rVert}
\providecommand{\dd}{\mathrm{d}}
\providecommand{\ii}{\mathrm{i}}
\providecommand{\R}{\mathbb{R}}
\providecommand{\C}{\mathbb{C}}
\providecommand{\N}{\mathbb{N}}
\providecommand{\Z}{\mathbb{Z}}
\providecommand{\grad}{\nabla}
\providecommand{\curl}{\nabla\times}
\providecommand{\diverg}{\nabla\cdot}
\providecommand{\va}{\bm{a}}
\providecommand{\vc}{\bm{c}}
\providecommand{\vn}{\bm{n}}
\providecommand{\vu}{\bm{u}}
\providecommand{\vv}{\bm{v}}
\providecommand{\vw}{\bm{w}}
\providecommand{\vx}{\bm{x}}
\providecommand{\vG}{\bm{\Gamma}}
\providecommand{\ex}{\bm{e}_x}
\providecommand{\ey}{\bm{e}_y}
\providecommand{\ez}{\bm{e}_z}
\providecommand{\pe}[1]{\bm{e}_{(#1)}}
\providecommand{\bigO}{\mathcal{O}}
\DeclareMathOperator{\rect}{rect}
\DeclareMathOperator{\sinc}{sinc}
\DeclareMathOperator{\tri}{tri}
"""
UNICODE = {"α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "θ": r"\theta",
           "λ": r"\lambda", "μ": r"\mu", "π": r"\pi", "σ": r"\sigma", "φ": r"\varphi",
           "ψ": r"\psi", "ω": r"\omega", "ħ": r"\hbar", "‖": r"\|", "√": r"\surd",
           "·": r"\cdot", "′": r"'", "→": r"\to", "≤": r"\le", "≥": r"\ge", "≠": r"\ne",
           "≈": r"\approx", "∞": r"\infty", "±": r"\pm", "×": r"\times", "½": r"\tfrac12",
           "²": r"^2", "³": r"^3", "−": "-", "∫": r"\int", "∂": r"\partial", "∇": r"\nabla"}

MARKS = {"plain", "ok", "hint", "slip", "wrong", "after", "fix"}
LABEL = {"wrong": ("Mistake.", RED), "slip": ("Slip.", AMBER), "hint": ("Hint used.", BLUE)}
BAR = {"wrong": RED, "slip": AMBER, "hint": BLUE, "ok": GREEN, "fix": GREEN, "after": DIM}


def template(extra=""):
    pre = PREAMBLE + "".join(rf"\newunicodechar{{{c}}}{{\ensuremath{{{t}}}}}" "\n"
                             for c, t in UNICODE.items())
    return TexTemplate(preamble=TexTemplate().preamble + pre + extra)


def plain_len(s):
    """Rough count of visible characters in a LaTeX string, for reading time."""
    s = re.sub(r"\\[a-zA-Z]+", "x", s)
    return len(re.sub(r"[{}$^_\\ ]", "", s))


def esc(s):
    return re.sub(r"([&%#_$])", r"\\\1", str(s))


class Review(Scene):
    def __init__(self, board, **kw):
        super().__init__(**kw)
        self.b = board
        self.T = template(board.get("preamble", ""))
        self.pace = float(board.get("pace", 1.0))
        self.rows = []          # visible rows: dict(math, marker, group)
        self.row_of = {}        # attempt line number (1-based) -> row dict
        self.caption = None
        self.label = None
        self.stamps = []        # (time, label) at the end of each step, for --sheet
        self.lineno = 0         # number shown in the margin; see numbered_lines()
        self.warnings = []

    # ------------------------------------------------------------- building blocks
    def math(self, tex, where):
        try:
            m = MathTex(tex, tex_template=self.T, font_size=MATH_FS, color=FG)
        except Exception as e:
            raise SystemExit(f"animate: LaTeX error in {where}: {tex!r}\n{e}")
        if m.width > MATH_W:
            if MATH_W / m.width < 0.8:
                self.warnings.append(f"{where}: too wide, shrunk to {100 * MATH_W / m.width:.0f}%;"
                                     " split it into two lines")
            m.scale_to_fit_width(MATH_W)
        if m.height > TOP_Y - BOTTOM_Y:
            self.warnings.append(f"{where}: taller than the math area; split it")
        bad, good = [], []
        for g in m.family_members_with_points():
            h = g.get_fill_color().to_hex().upper()
            if h == BAD_KEY:
                bad.append(g)
                g.set_color(FG)          # revealed later, after the line is in place
            elif h == GOOD_KEY:
                good.append(g)
                g.set_color(GREEN)
        m.bad, m.good = bad, good
        return m

    def text(self, body, width, fs, where, color=FG, sans=False):
        cm = width / (fs / 48) * CM_PER_UNIT_48
        font = r"\sffamily " if sans else ""
        src = rf"\parbox{{{cm:.2f}cm}}{{\raggedright {font}{body}}}"
        try:
            t = Tex(src, tex_template=self.T, font_size=fs, color=color)
        except Exception as e:
            raise SystemExit(f"animate: LaTeX error in {where}: {body!r}\n{e}")
        for g in t.family_members_with_points():
            h = g.get_fill_color().to_hex().upper()
            if h == BAD_KEY:
                g.set_color(RED)
            elif h == GOOD_KEY:
                g.set_color(GREEN)
        return t

    def chrome(self, s, color=DIM, fs=CHROME_FS):
        return Tex(rf"\sffamily {s}", tex_template=self.T, font_size=fs, color=color)

    def marker(self, mark):
        if mark in ("ok", "fix"):
            m = MathTex(r"\checkmark", tex_template=self.T, font_size=40, color=GREEN)
        elif mark == "wrong":
            m = Tex(r"\ding{55}", tex_template=self.T, font_size=40, color=RED)
        elif mark == "slip":
            m = Tex(r"\sffamily\bfseries !", tex_template=self.T, font_size=44, color=AMBER)
        elif mark == "hint":
            m = Tex(r"\sffamily\bfseries hint", tex_template=self.T, font_size=20, color=BLUE)
        else:
            return None
        return m

    def read_time(self, s, lo=1.6, hi=7.0):
        return self.pace * min(hi, max(lo, 1.2 + 0.05 * plain_len(s or "")))

    def stamp(self, label):
        self.stamps.append((self.renderer.time - 0.05, label))

    # ------------------------------------------------------------------ scenes
    def construct(self):
        b = self.b
        self.title_card()
        for i, c in enumerate(b.get("intro", [])):
            self.card(c, f"intro {i + 1}")
        self.header()
        attempt = b.get("attempt", [])
        if attempt:
            self.section("Your work", AMBER)
            for i, line in enumerate(attempt, 1):
                self.step(line, f"attempt line {i}", default_mark="plain")
                self.row_of[i] = self.rows[-1]
        fix = b.get("fix")
        if fix:
            self.rewind(int(fix.get("from", 0)))
            self.section(fix.get("title", "How to continue"), GREEN)
            for i, line in enumerate(fix.get("lines", []), 1):
                self.step(line, f"fix line {i}", default_mark="fix")
        self.clear_board()
        for i, c in enumerate(b.get("outro", [])):
            self.card(c, f"outro {i + 1}")
        self.wait(0.5)

    def title_card(self):
        b = self.b
        top = self.chrome(f"{esc(b.get('set', ''))} \\textperiodcentered\\ {esc(b.get('item', ''))}",
                          fs=30)
        title = self.text(b.get("title", ""), 11.5, 52, "title")
        parts = [top, title]
        if b.get("score"):
            parts.append(self.chrome(f"scored {esc(b['score'])}", fs=28))
        g = VGroup(*parts).arrange(DOWN, buff=0.4, aligned_edge=LEFT)
        g.move_to(0)
        self.play(FadeIn(g, shift=UP * 0.2), run_time=0.8)
        self.wait(1.6 * self.pace)
        self.stamp("title")
        self.play(FadeOut(g), run_time=0.5)

    def card(self, c, where):
        parts = []
        if c.get("title"):
            parts.append(self.chrome(rf"\bfseries {c['title']}", color=BLUE, fs=32))
        if c.get("text"):
            parts.append(self.text(c["text"], 12.2, 36, where))
        maths = [self.math(t, f"{where} tex") for t in c.get("tex", [])]
        g = VGroup(*parts, *maths).arrange(DOWN, buff=0.45)
        for p in parts:
            p.align_to(g, LEFT)
        if g.height > 6.8:
            self.warnings.append(f"{where}: card too full, shrunk to {680 / g.height:.0f}%")
            g.scale_to_fit_height(6.8)
        g.move_to(0)
        head = VGroup(*parts)
        if parts:
            self.play(FadeIn(head, shift=UP * 0.2), run_time=0.7)
        for m in maths:
            self.play(Write(m), run_time=min(2.0, 0.6 + 0.02 * len(m)))
        reading = c.get("text", "") + " ".join(c.get("tex", []))
        self.wait(self.read_time(reading, lo=2.0, hi=9.0))
        self.stamp(where)
        self.play(*[FadeOut(x) for x in [head, *maths] if len(x.submobjects)], run_time=0.5)

    def header(self):
        b = self.b
        left = self.chrome(f"{esc(b.get('set', ''))} \\textperiodcentered\\ {esc(b.get('item', ''))}")
        left.to_corner(UP + LEFT, buff=0.35)
        rule = Line([-6.75, 3.2, 0], [6.75, 3.2, 0], stroke_width=1, color=DIM)
        self.play(FadeIn(left), Create(rule), run_time=0.5)

    def section(self, name, color):
        new = self.chrome(rf"\bfseries {name}", color=color).to_corner(UP + RIGHT, buff=0.35)
        if self.label is None:
            self.play(FadeIn(new, shift=LEFT * 0.2), run_time=0.5)
        else:
            self.play(FadeOut(self.label, shift=UP * 0.2), FadeIn(new, shift=UP * 0.2),
                      run_time=0.6)
        self.label = new

    def set_caption(self, line, mark):
        """Animations that swap the caption strip to this line's note: (out, in, wait)."""
        out = []
        if self.caption is not None:
            out.append(FadeOut(self.caption, run_time=0.3))
            self.caption = None
        note = line.get("note")
        if not note:
            return out, [], 0
        body = note
        if mark in LABEL:
            word, col = LABEL[mark]
            body = rf"\textbf{{\textcolor[HTML]{{{col[1:]}}}{{{word}}}}} " + note
        t = self.text(body, SUB_W, SUB_FS, "note")
        if t.height > SUB_H:
            self.warnings.append(f"note {plain_len(note)} chars too long, shrunk to "
                                 f"{100 * SUB_H / t.height:.0f}%: shorten it")
            t.scale_to_fit_height(SUB_H)
        t.move_to([SUB_X + t.width / 2, SUB_Y, 0])
        bar = Line([SUB_X - 0.22, SUB_Y + t.height / 2, 0], [SUB_X - 0.22, SUB_Y - t.height / 2, 0],
                   stroke_width=5, color=BAR.get(mark, DIM))
        self.caption = VGroup(bar, t)
        return out, [FadeIn(self.caption, shift=UP * 0.15, run_time=0.5)], self.read_time(note)

    # ------------------------------------------------------------------ steps
    def step(self, line, where, default_mark):
        mark = line.get("mark", default_mark)
        if mark not in MARKS:
            raise SystemExit(f"animate: {where}: unknown mark {mark!r} (one of {sorted(MARKS)})")
        m = self.math(line["tex"], where)
        prev = self.rows[-1] if self.rows else None
        how = line.get("how", "derive" if prev else "write")
        mk = self.marker(mark)
        self.lineno += 1
        num = Tex(rf"\sffamily {self.lineno}", tex_template=self.T, font_size=28, color=DIM)

        if how == "replace" and prev:
            m.move_to(prev["math"], aligned_edge=LEFT)
            m.align_to(prev["math"], UP)
            anims = [TransformMatchingShapes(prev["math"], m, run_time=1.2)]
            old_extra = list(prev["group"][1:])
            anims += [FadeOut(x, run_time=0.4) for x in old_extra]
            self.rows.pop()
        else:
            top = prev["group"].get_bottom()[1] - 0.42 if prev else TOP_Y
            m.move_to([MATH_X + m.width / 2, top - m.height / 2, 0])
            overflow = BOTTOM_Y - m.get_bottom()[1]
            if overflow > 0:
                self.scroll(overflow)
                m.shift(UP * overflow)
            if how == "derive" and prev:
                anims = [TransformMatchingShapes(prev["math"].copy(), m, run_time=1.3)]
            else:
                anims = [Write(m, run_time=min(2.0, 0.7 + 0.025 * len(m)))]

        if mark == "after":
            m.set_opacity(0.55)
        cap_out, cap_in, wait = self.set_caption(line, mark)
        self.play(*anims, *cap_out)

        num.move_to([NUM_X, m.get_center()[1], 0])
        group = VGroup(m, num)
        extra = [FadeIn(num)]
        if mk is not None:
            mk.move_to([GUTTER_X, m.get_center()[1], 0])
            extra.append(FadeIn(mk, scale=0.6))
            group.add(mk)
        boxes = []
        if m.bad:
            col = AMBER if mark == "slip" else RED
            for g in m.bad:
                g.set_color(col)
            boxes.append(SurroundingRectangle(VGroup(*m.bad), color=col, buff=0.035,
                                              corner_radius=0.04, stroke_width=2.5))
        if m.good:
            boxes.append(SurroundingRectangle(VGroup(*m.good), color=GREEN, buff=0.035,
                                              corner_radius=0.04, stroke_width=2.5))
        if line.get("box"):
            boxes.append(SurroundingRectangle(m, color=GREEN, buff=0.15, corner_radius=0.08,
                                              stroke_width=3))
        group.add(*boxes)
        if extra or boxes or cap_in:
            self.play(*extra, *[Create(x) for x in boxes], *cap_in, run_time=0.6)
        self.remove(*group)
        self.add(group)
        self.rows.append({"math": m, "group": group, "pristine": group.copy()})
        hold = wait if mark != "after" else min(wait, 2.5 * self.pace)
        self.wait(max(hold, 0.8 * self.pace) + float(line.get("pause", 0)))
        self.stamp(where)

    def scroll(self, dy):
        """Move every row up by dy; rows that leave the math area fade out."""
        anims, keep = [], []
        for r in self.rows:
            if r["group"].get_top()[1] + dy > TOP_Y + 0.25:
                anims.append(FadeOut(r["group"], shift=UP * dy))
            else:
                anims.append(r["group"].animate.shift(UP * dy))
                keep.append(r)
        self.rows = keep
        self.play(*anims, run_time=0.6)

    def rewind(self, n):
        """Strike the lines after attempt line n, then continue below line n."""
        cap_anims, _, _ = self.set_caption({}, "plain")
        keep = self.row_of.get(n) if n else None
        if n and keep is None:
            raise SystemExit(f"animate: fix.from={n} but the attempt has {len(self.row_of)} lines")
        visible = keep in self.rows
        later = [r for r in self.rows if r is not keep and
                 (not visible or r["group"].get_center()[1] < keep["group"].get_center()[1])]
        strikes = []
        for r in later:
            mm = r["math"]
            strikes.append(Line(mm.get_left() + LEFT * 0.1, mm.get_right() + RIGHT * 0.1,
                                color=RED, stroke_width=3))
        if later:
            self.play(*[r["group"].animate.set_opacity(0.35) for r in later],
                      *[Create(s) for s in strikes], *cap_anims, run_time=0.8)
            self.wait(0.6 * self.pace)
        gone = [r["group"] for r in self.rows if r is not keep]
        anims = [FadeOut(g, shift=RIGHT * 0.6) for g in gone] + [FadeOut(s) for s in strikes]
        if keep is not None and visible:
            anims.append(keep["group"].animate.shift(UP * (TOP_Y - keep["group"].get_top()[1])))
        elif keep is not None:          # scrolled off earlier: bring a fresh copy back
            g = keep["pristine"].copy()
            g.shift(UP * (TOP_Y - g.get_top()[1]))
            keep = {"math": g[0], "group": g, "pristine": keep["pristine"]}
            anims.append(FadeIn(g, shift=DOWN * 0.3))
        if anims:
            self.play(*anims, run_time=0.9)
        self.rows = [keep] if keep is not None else []
        self.stamp("rewind")

    def clear_board(self):
        if self.mobjects:
            self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.6)
        self.rows, self.caption, self.label = [], None, None


def contact_sheet(video, stamps, out):
    import av
    from PIL import Image, ImageDraw
    want = sorted(stamps)
    shots, i = [], 0
    with av.open(str(video)) as c:
        for frame in c.decode(video=0):
            while i < len(want) and frame.time >= want[i][0]:
                shots.append((want[i][1], frame.to_image()))
                i += 1
            if i >= len(want):
                break
    if not shots:
        return
    w, h, cols = 640, 360, 3
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * (h + 24)), BG)
    d = ImageDraw.Draw(sheet)
    for k, (label, img) in enumerate(shots):
        x, y = (k % cols) * w, (k // cols) * (h + 24)
        sheet.paste(img.resize((w, h)), (x, y + 24))
        d.text((x + 6, y + 5), f"{k + 1}. {label}", fill=FG)
    sheet.save(out)


def numbered_lines(board):
    """The margin numbers: attempt lines first, then the fix lines continue."""
    out = []
    for part, lines, default in (("attempt", board.get("attempt", []), "plain"),
                                 ("fix", (board.get("fix") or {}).get("lines", []), "fix")):
        for line in lines:
            out.append((len(out) + 1, part, line.get("mark", default), line))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--out")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--lines", action="store_true")
    a = ap.parse_args()

    src = Path(a.storyboard).resolve()
    board = json.loads(src.read_text())
    if a.lines:
        frm = (board.get("fix") or {}).get("from")
        for n, part, mark, line in numbered_lines(board):
            print(f"{n:>3}  {part:<7} {mark:<6} {line['tex']}")
            if line.get("note"):
                print(f"{'':>20}note: {line['note']}")
        if frm is not None:
            print(f"fix continues after line {frm}")
        return
    out = Path(a.out).resolve() if a.out else src.with_suffix(".mp4")
    w, h, fps = (854, 480, 15) if a.draft else (1920, 1080, 30)
    opts = {"pixel_width": w, "pixel_height": h, "frame_rate": fps,
            "background_color": BG, "media_dir": str(CACHE / "media"),
            "output_file": out.stem, "verbosity": "WARNING", "progress_bar": "none"}
    with tempconfig(opts):
        scene = Review(board)
        scene.render()
        made = Path(scene.renderer.file_writer.movie_file_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(made, out)
    length = scene.renderer.time
    print(f"{out}  ({length:.0f} s, {w}x{h})")
    for msg in scene.warnings:
        print(f"warning: {msg}")
    if not scene.warnings:
        print("layout: no warnings")
    if a.sheet:
        sheet = out.with_suffix(".sheet.png")
        contact_sheet(out, scene.stamps, sheet)
        print(sheet)


if __name__ == "__main__":
    sys.exit(main())
