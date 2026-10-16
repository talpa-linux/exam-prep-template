# Setting up

What has to be installed, per operating system, and how to check it. Written so that
either you or Claude can follow it. If Claude is doing it for you, see **For agents** at
the end.

## What you need

- A Claude **Pro or Max** plan (Team and Enterprise work too; your organisation then
  decides whether bypass permissions mode is available). The free plan has no Claude
  Code.
- The **Claude desktop app** (Code tab), or Claude Code in a terminal. The project is
  built for the desktop app: PDFs arrive as files in the conversation, and the maths
  renders.
- About **5 GB** of disk, mostly TeX Live, plus about 1 GB more for the optional review
  videos.
- The software below: Python 3 with sympy, TeX Live with latexmk, ImageMagick (with HEIC
  support for iPhone photos), poppler and git.

## Windows: WSL 2 with Ubuntu (the supported route)

The scripts are bash and Linux tools, so on Windows the project runs inside WSL, the
Linux that ships with Windows. The desktop app runs Code sessions inside WSL directly.

1. **Install WSL and Ubuntu.** Open PowerShell as administrator and run

   ```powershell
   wsl --install -d Ubuntu
   ```

   Restart when asked. Ubuntu then opens a window and asks for a Linux user name and
   password; choose them yourself and remember the password (`sudo` asks for it).
2. **Install the software**, in the Ubuntu window:

   ```bash
   sudo apt update
   sudo apt install -y git python3 python3-venv python3-sympy python3-pil \
     latexmk texlive-latex-base texlive-latex-recommended texlive-latex-extra \
     texlive-science texlive-pictures texlive-fonts-recommended lmodern \
     imagemagick libheif-plugin-libde265 poppler-utils qpdf
   ```

   TeX Live is large: this takes 5 to 15 minutes. If apt cannot find
   `libheif-plugin-libde265` (older Ubuntu), leave it out.
3. **Put the project in your Linux home**, not on the C: drive (WSL reads Windows files
   slowly). With git:

   ```bash
   git clone <the repository URL> ~/"Exam prep"
   ```

   or copy a downloaded folder from Windows (here from Downloads; use your own
   Windows user name):

   ```bash
   cp -r "/mnt/c/Users/<you>/Downloads/Exam prep template" ~/"Exam prep"
   ```

4. **Check**: `cd ~/"Exam prep" && python3 tools/doctor.py`. It should end with
   "Everything the core loop needs is installed".
5. **Open it in the desktop app**: Code tab → new session → open the environment picker
   → under **WSL** pick **Ubuntu** → choose the folder `~/Exam prep` → trust it. The first
   session in WSL takes a little longer while the app sets itself up.
6. **Allow bypass permissions**: Settings → Claude Code → "Allow bypass permissions
   mode", then choose **Bypass permissions** in the session's mode selector (the app
   remembers it for this folder). See "Permissions" below.
7. Type `/start`.

**Your files from Windows.** In Explorer, the project is at
`\\wsl.localhost\Ubuntu\home\<linux user>\Exam prep`. Pin that folder to Quick access:
that is where you drop course files and the photos of your work. WSL sessions in the
desktop app have no terminal pane and no file browser; use the Ubuntu app for commands
and Explorer for files.

## Linux

Debian and Ubuntu: step 2 above. Fedora (names may differ slightly):

```bash
sudo dnf install git python3 python3-sympy python3-pillow latexmk texlive-scheme-medium \
  texlive-siunitx texlive-pgfplots texlive-tcolorbox texlive-titlesec texlive-cancel \
  texlive-needspace texlive-lastpage texlive-enumitem ImageMagick libheif poppler-utils qpdf
```

Arch: `sudo pacman -S git python python-sympy python-pillow texlive-basic texlive-latex
texlive-latexrecommended texlive-latexextra texlive-science texlive-pictures
texlive-fontsrecommended imagemagick libheif poppler qpdf`.

Whatever the distribution, `python3 tools/doctor.py` names the TeX files still missing.

## macOS

Not tested. The Python tools and LaTeX work with Homebrew (`brew install python
imagemagick poppler qpdf` and `brew install --cask mactex-no-gui`, then `pip3 install
sympy`), but `tools/prep_photos.sh` uses GNU tools and bash 4: also `brew install bash
coreutils findutils` and put Homebrew's `gnubin` folders first on `PATH`.

## Native Windows (without WSL)

Not supported: the shell scripts, `python3` and the ImageMagick and poppler tools behave
differently there. Use WSL.

## Optional

**Review videos** (`/review` can animate your own working and the fix). Extra packages:

```bash
sudo apt install -y build-essential python3-dev pkg-config libcairo2-dev libpango1.0-dev \
  dvisvgm preview-latex-style texlive-latex-extra
```

The first video then installs Manim into `~/.local/share/exam-prep-anim/venv` by itself
(a few minutes, about 500 MB). If apt has no `dvisvgm` package, it is part of
`texlive-binaries`.

**Wolfram Engine**, only for a course with a Mathematica part (sympy covers
everything else). It is free for personal use: download it from
https://www.wolfram.com/engine/ , install it, and activate it once with
`wolframscript -activate`, signing in with your own Wolfram ID.

## Permissions

Each skill runs many scripts and starts agents, and in the default mode you would
approve each command. The project is meant to run in **Bypass permissions** mode: allow
it once under Settings → Claude Code ("Allow bypass permissions mode"; on Team and
Enterprise plans your organisation controls it), then pick it in the mode selector of
this folder. A project's own settings file cannot switch it on; it is your choice in the
app. In this mode Claude runs commands without asking, so use it for this project
only. If you would rather approve things, **Auto** mode asks only for unusual actions;
**Manual** asks for everything.

## Check

```bash
python3 tools/doctor.py          # everything, with a LaTeX test build
python3 tools/doctor.py --quick  # without the test build
bash tools/tests/run.sh          # the test suite of the scripts (about 30 s)
```

## For agents

When the user asks you to install or check this project's software:

1. Run `python3 tools/doctor.py` and read it. It prints, per missing item, the package
   and one install line per group.
2. Never type a password and never run `sudo` yourself: give the user the install line
   in a bash code block to run in their own terminal (on Windows, the Ubuntu app), wait
   until they say it is done, and run the doctor again.
3. Install nothing beyond what this file and the doctor name without asking. Do not
   change system settings, shell profiles or the user's Claude settings.
4. The Wolfram Engine activation and the desktop app's permission settings are the
   user's to do: explain them, do not attempt them.
5. If the doctor reports native Windows, stop and point to the WSL section above.
6. When `core` is complete, the user continues with `/start`.
