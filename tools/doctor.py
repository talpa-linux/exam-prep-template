#!/usr/bin/env python3
"""doctor.py [--quick] [--json]

Check that everything this project needs is installed, and say how to install what is
missing. Run it after following SETUP.md, and whenever a script complains about a
missing program. --quick skips the LaTeX test build (a few seconds). Exit status 0
when everything the core loop needs is there, 1 otherwise. Changes nothing.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent

# what the core loop needs from TeX Live (prep.sty, the progress report, the guide)
CORE_TEX = ["geometry.sty", "amsmath.sty", "amssymb.sty", "mathtools.sty", "bm.sty",
            "siunitx.sty", "tikz.sty", "pgfplots.sty", "enumitem.sty", "booktabs.sty",
            "xcolor.sty", "graphicx.sty", "cancel.sty", "hyperref.sty", "lmodern.sty",
            "t1lmr.fd", "needspace.sty", "fancyhdr.sty", "lastpage.sty", "tcolorbox.sty",
            "titlesec.sty", "tabularx.sty", "longtable.sty", "microtype.sty"]
# extra for the Manim videos (Manim's own TeX template plus tools/animate.py's preamble)
VIDEO_TEX = ["standalone.cls", "preview.sty", "newunicodechar.sty", "pifont.sty", "english.ldf"]

# Debian/Ubuntu (also WSL) package for each missing thing
APT = {
    "python3": "python3", "sympy": "python3-sympy", "PIL": "python3-pil",
    "latexmk": "latexmk", "pdflatex": "texlive-latex-base", "kpsewhich": "texlive-latex-base",
    "geometry.sty": "texlive-latex-base", "amsmath.sty": "texlive-latex-base",
    "bm.sty": "texlive-latex-base", "graphicx.sty": "texlive-latex-base",
    "hyperref.sty": "texlive-latex-base", "fancyhdr.sty": "texlive-latex-base",
    "tabularx.sty": "texlive-latex-base", "longtable.sty": "texlive-latex-base",
    "pifont.sty": "texlive-latex-base", "english.ldf": "texlive-latex-base",
    "amssymb.sty": "texlive-base",
    "mathtools.sty": "texlive-latex-recommended", "booktabs.sty": "texlive-latex-recommended",
    "xcolor.sty": "texlive-latex-recommended", "microtype.sty": "texlive-latex-recommended",
    "siunitx.sty": "texlive-science", "tikz.sty": "texlive-pictures", "pgfplots.sty": "texlive-pictures",
    "enumitem.sty": "texlive-latex-extra", "cancel.sty": "texlive-latex-extra",
    "needspace.sty": "texlive-latex-extra", "lastpage.sty": "texlive-latex-extra",
    "tcolorbox.sty": "texlive-latex-extra", "titlesec.sty": "texlive-latex-extra",
    "standalone.cls": "texlive-latex-extra", "newunicodechar.sty": "texlive-latex-extra",
    "lmodern.sty": "lmodern", "t1lmr.fd": "lmodern", "preview.sty": "preview-latex-style",
    "imagemagick": "imagemagick", "heic": "libheif-plugin-libde265",
    "poppler": "poppler-utils", "qpdf": "qpdf", "git": "git",
    "venv": "python3-venv", "pkg-config": "pkg-config", "cairo": "libcairo2-dev",
    "pango": "libpango1.0-dev", "cc": "build-essential", "Python.h": "python3-dev",
    "dvisvgm": "dvisvgm",
}

results = []  # dicts: group, name, ok, detail, fix (key into APT or free text)


def check(group, name, ok, detail="", fix=None):
    results.append({"group": group, "name": name, "ok": bool(ok), "detail": detail, "fix": fix})
    return ok


def run(cmd, timeout=60, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
    except (OSError, subprocess.TimeoutExpired):
        return None


def first_line(cmd):
    r = run(cmd)
    out = (r.stdout or r.stderr).strip().splitlines() if r else []
    return out[0] if out else ""


def environment():
    sysname = platform.system()
    wsl = sysname == "Linux" and "microsoft" in platform.release().lower()
    distro = ""
    try:
        osr = Path("/etc/os-release").read_text()
        m = re.search(r'^PRETTY_NAME="?([^"\n]+)', osr, re.M)
        distro = m.group(1) if m else ""
        like = " ".join(re.findall(r"^(?:ID|ID_LIKE)=\"?([^\"\n]+)", osr, re.M)).lower()
    except OSError:
        like = ""
    apt = "debian" in like or "ubuntu" in like
    where = ("WSL, " if wsl else "") + (distro or sysname)
    native_win = sysname == "Windows" or sysname.startswith(("MINGW", "MSYS", "CYGWIN"))
    check("environment", "operating system", not native_win, where,
          "Native Windows is not supported: install WSL 2 with Ubuntu and run the project inside it (SETUP.md).")
    if sysname == "Darwin":
        check("recommended", "macOS", False, "not tested",
              "The shell scripts need GNU tools: brew install bash coreutils findutils, and put them first on PATH.")
    if wsl and str(ROOT).startswith("/mnt/"):
        check("recommended", "project location", False, str(ROOT),
              "The project is on the Windows drive, which is slow from WSL. Move it into your Linux home, "
              "e.g. cp -r \"" + str(ROOT) + "\" ~/ (SETUP.md).")
    else:
        check("environment", "project location", True, str(ROOT))
    cfg = TOOLS / "config.json"
    if cfg.exists():
        try:
            n = len(json.loads(cfg.read_text()).get("courses", {}))
            check("environment", "courses", True, f"{n} configured in tools/config.json")
        except ValueError:
            check("environment", "courses", False, "tools/config.json does not parse", "Fix or remove tools/config.json.")
    else:
        check("environment", "courses", True, "none yet: /start sets them up")
    return apt, sysname


def core(quick):
    g = "core"
    v = sys.version_info
    check(g, "python 3.9+", v >= (3, 9), platform.python_version(), "python3")
    try:
        import sympy
        check(g, "sympy", True, sympy.__version__)
    except ImportError:
        check(g, "sympy", False, "agents use it to check every answer key", "sympy")
    git = shutil.which("git")
    check(g, "git", git, first_line(["git", "--version"]) if git else "the desktop app needs it", "git")
    for prog in ("latexmk", "pdflatex"):
        p = shutil.which(prog)
        check(g, prog, p, first_line([prog, "--version"])[:60] if p else "TeX Live", prog)
    kp = shutil.which("kpsewhich")
    missing_tex = []
    if kp:
        r = run([kp] + CORE_TEX + VIDEO_TEX)
        found = {Path(x).name for x in (r.stdout.split() if r else [])}
        missing_tex = [f for f in CORE_TEX if f not in found]
        video_missing = [f for f in VIDEO_TEX if f not in found]
    else:
        missing_tex, video_missing = list(CORE_TEX), list(VIDEO_TEX)
    check(g, "LaTeX packages", not missing_tex,
          f"{len(CORE_TEX) - len(missing_tex)}/{len(CORE_TEX)} found" + (f"; missing {' '.join(missing_tex)}" if missing_tex else ""),
          missing_tex or None)
    if not quick and shutil.which("latexmk") and not missing_tex:
        ok, detail = tex_test()
        check(g, "LaTeX test build", ok, detail, None if ok else "See the error; usually a missing TeX package.")
    im = shutil.which("magick") or shutil.which("convert")
    if im and Path(im).name == "convert" and platform.system() == "Windows":
        im = None  # Windows' own convert.exe is not ImageMagick
    check(g, "ImageMagick", im, first_line([im, "-version"])[:60] if im else "photo preparation", ["imagemagick", "heic"])
    if im:
        r = run([im, "-list", "format"])
        fmts = r.stdout if r else ""
        heic = re.search(r"^\s*HEIC\*?\s+\S+\s+r", fmts, re.M)
        check(g, "HEIC photos (iPhone)", heic, "readable" if heic else "cannot read .heic", "heic")
    for prog in ("pdftoppm", "pdftotext", "pdfinfo"):
        check(g, prog, shutil.which(prog), "poppler", "poppler")
    return video_missing


def tex_test():
    readme = (TOOLS / "tex" / "README.md").read_text(encoding="utf-8")
    docs = [b for b in re.findall(r"```latex\n(.*?)```", readme, re.S) if "\\documentclass" in b]
    if not docs:
        return False, "no example found in tools/tex/README.md"
    with tempfile.TemporaryDirectory(prefix="doctor ") as d:
        tex = Path(d) / "example.tex"
        tex.write_text(docs[0], encoding="utf-8")
        r = run(["bash", str(TOOLS / "build_tex.sh"), str(tex)], timeout=180)
        if r and r.returncode == 0 and (Path(d) / "example.pdf").is_file():
            return True, "an example exam compiled with tools/tex/prep.sty"
        err = (r.stderr if r else "build_tex.sh did not run").strip().splitlines()
        return False, " | ".join(err[:3])


def recommended():
    g = "recommended"
    q = shutil.which("qpdf") or (shutil.which("pdfseparate") and shutil.which("pdfunite"))
    check(g, "qpdf", q, "splits an exam from its answers for the held-out exam", "qpdf")
    w = shutil.which("wolframscript")
    check(g, "wolframscript", w, "found" if w else "only for courses with a Mathematica part (sympy covers the rest)",
          "Wolfram Engine is free for personal use: https://www.wolfram.com/engine/ , then `wolframscript -activate` "
          "(you sign in with your own Wolfram ID).")
    try:
        import PIL  # noqa: F401
        check(g, "Pillow", True, "for tools/tests/run.sh")
    except ImportError:
        check(g, "Pillow", False, "only for tools/tests/run.sh", "PIL")


def videos(video_missing):
    g = "videos (optional)"
    venv = Path(os.environ.get("EXAM_PREP_ANIM_VENV", Path.home() / ".local/share/exam-prep-anim/venv"))
    py = venv / "bin" / "python"
    r = run([str(py), "-c", "import manim; print(manim.__version__)"]) if py.exists() else None
    if r and r.returncode == 0:
        check(g, "Manim", True, f"{r.stdout.strip()} in {venv}")
    else:
        check(g, "Manim", True, f"not installed yet; the first video installs it into {venv} (a few minutes)")
        ens = run([sys.executable, "-c", "import ensurepip, venv"])
        check(g, "python venv", ens and ens.returncode == 0, "to create the Manim environment", "venv")
        pc = shutil.which("pkg-config")
        check(g, "pkg-config", pc, "to build pycairo and ManimPango", ["pkg-config", "cairo", "pango"])
        if pc:
            for lib, key in (("cairo", "cairo"), ("pangocairo", "pango")):
                ok = run([pc, "--exists", lib])
                check(g, f"{lib} headers", ok and ok.returncode == 0, "", key)
        check(g, "C compiler", shutil.which("cc") or shutil.which("gcc"), "", "cc")
        inc = sysconfig.get_paths().get("include", "")
        check(g, "Python headers", Path(inc, "Python.h").is_file(), inc, "Python.h")
    check(g, "dvisvgm", shutil.which("dvisvgm"), "turns the formulas into shapes", "dvisvgm")
    check(g, "LaTeX for videos", not video_missing,
          "all found" if not video_missing else "missing " + " ".join(video_missing), video_missing or None)


def fixes(r):
    f = r["fix"]
    return f if isinstance(f, list) else [f] if f else []


def main():
    quick = "--quick" in sys.argv
    apt, sysname = environment()
    video_missing = core(quick)
    recommended()
    videos(video_missing)
    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
    else:
        group = None
        for r in results:
            if r["group"] != group:
                group = r["group"]
                print(f"\n{group}")
            mark = "ok " if r["ok"] else ("-- " if group in ("recommended", "videos (optional)") else "XX ")
            print(f"  {mark} {r['name']:<22} {r['detail']}")
            for f in fixes(r):
                if not r["ok"] and f not in APT:
                    print(f"       {f}")
        missing = [r for r in results if not r["ok"]]
        for label, groups in (("needed", ("core", "environment")), ("recommended", ("recommended",)),
                              ("for videos", ("videos (optional)",))):
            pk = []
            for r in missing:
                if r["group"] in groups:
                    pk += [APT[f] for f in fixes(r) if f in APT and APT[f] not in pk]
            if pk:
                print(f"\nTo install what is {label}" + (":" if apt else " (Debian/Ubuntu names; see SETUP.md for others):"))
                print("  sudo apt update && sudo apt install -y " + " ".join(sorted(set(pk))))
    core_ok = all(r["ok"] for r in results if r["group"] in ("core", "environment"))
    if "--json" not in sys.argv:
        print("\n" + ("Everything the core loop needs is installed." if core_ok
                      else "Something the core loop needs is missing: see above and SETUP.md."))
    sys.exit(0 if core_ok else 1)


if __name__ == "__main__":
    main()
