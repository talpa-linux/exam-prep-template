# prep.sty: writing exams, answer keys and feedback

One LaTeX style, `prep.sty`, for the three documents agents write by hand:

| document | what it is | environments used |
|---|---|---|
| practice exam | questions for the student, A4, points in the margin | `\problem`, `subqs`, `\subq`, `mc`, `\opt` |
| answer key | the same questions plus worked solutions | add `solution`, `\rubric`, `\pitfall` |
| feedback | one block per graded item | `fbitem`, `\youwrote`, `\firsterror`, `\fix`, `\takeaway` |

## Compile

```
tools/build_tex.sh path/to/file.tex      # writes path/to/file.pdf next to the source
```

The script compiles in the file's directory, finds `prep.sty` by itself, leaves no
auxiliary files behind, prints `built <pdf> (N pages)` on success and, on failure, the
first LaTeX error with context (exit status 1). pdfLaTeX only: no `fontspec`, no `xelatex`.
Every document starts with exactly `\documentclass[a4paper,11pt]{article}` followed by
`\usepackage{prep}` and needs nothing else. Do not load further packages and do not change the geometry.
`prep.sty` already loads amsmath, amssymb, mathtools, bm, siunitx, tikz, pgfplots,
enumitem, booktabs, xcolor, graphicx, cancel, hyperref, tcolorbox, geometry (A4).

## Macro reference

Arguments in braces are mandatory. Every argument is plain LaTeX; "number" means digits
with an optional decimal point (`5`, `2.5`), no unit and no comma.

| macro / environment | arguments | effect |
|---|---|---|
| `\prepheader{course}{set id}{kind label}{time}{points}{aids}` | six texts | Title block, once, right after `\begin{document}`. Also fills the running page header. Example values: `{Multivariable Calculus (MATH201)}{MATH-T03}{Training set}{90 min}{40}{formula sheet; no calculator}`. |
| `\problem{Title}{points}` | text, number | Starts "Problem N --- Title (20 p)". N counts up by itself. |
| `\begin{subqs} ... \end{subqs}` | none | List of sub-questions, numbered `N.k` after the current problem (`1.1`, `1.2`, ...). |
| `\subq{points}` | number | New sub-question inside `subqs`; the points appear in the right margin. The question text follows directly. |
| `\begin{mc} ... \end{mc}` | none | Multiple-choice options, lettered (a), (b), (c), ... Put it inside a `\subq` item. |
| `\opt` | none | New option inside `mc`; the option text follows directly. |
| `\begin{solution} ... \end{solution}` | none | Shaded, side-barred worked solution. Breaks across pages. Use inside a `\subq` item (or after a `\problem`). |
| `\rubric{points}{criterion}` | number, text | One marking line inside `solution`: `[2 p] criterion`. |
| `\pitfall{text}` | text | Typical mistake, inside `solution`. |
| `\begin{fbitem}{item id}{score}{max} ... \end{fbitem}` | text, number, number | One graded item: "Item 1.2" on the left, "3 / 5" on the right (green full marks, amber partial, red zero). |
| `\youwrote{text}` | text | What the grader read in the student's work. Only inside `fbitem`. |
| `\firsterror{text}` | text | Where the work first goes wrong. Only inside `fbitem`. |
| `\fix{text}` | text | What would have been correct. Only inside `fbitem`. |
| `\takeaway{text}` | text | One-line lesson (same text as the feedback JSON `takeaway`, at most 25 words). Only inside `fbitem`. |

Math shortcuts (defined only if nothing else defines them): `\ket{}`, `\bra{}`,
`\braket{}{}`, `\expval{}`, `\abs{}`, `\norm{}`, `\dd` (upright d), `\ii` (upright i),
`\R \C \N \Z \Q`, `\grad`, `\curl`, `\diverg`. siunitx is loaded: `\qty{9.81}{\meter\per\second\squared}`,
`\num{1.5e3}`, `\unit{\kilo\gram}`.

### Rules that keep documents compiling

- Each structural macro only works inside its own environment (`\subq` in `subqs`, `\opt`
  in `mc`, `\rubric`/`\pitfall` in `solution`, `\youwrote`/`\firsterror`/`\fix`/`\takeaway`
  in `fbitem`). Anywhere else LaTeX stops with `prep: \subq used outside \begin{subqs}`
  (or the matching message).
- Text between `\subq`/`\opt` and the next one is the content of that item; leave a blank
  line before `\begin{mc}` / `\begin{solution}` if you like, but do not put `\\` or
  `\newline` at the end of an item.
- In plain text escape `& % $ # _ { } ~ ^ \` as `\& \% \$ \# \_ \{ \} \textasciitilde{} \textasciicircum{} \textbackslash{}`;
  math goes between `$...$` (inline) or `\[ ... \]` (display).
- `\problem` and `\prepheader` are used in the document body, never inside a list.
- Do not nest `subqs` in `subqs`, or `mc` in `mc`.
- Use `\DeclareMathOperator` and your own `\newcommand`s only in the preamble, if at all.

## Example 1: practice exam

```latex
\documentclass[a4paper,11pt]{article}
\usepackage{prep}
\begin{document}
\prepheader{Multivariable Calculus (MATH201)}{MATH-T03}{Training set}{90 min}{40}{formula sheet; no calculator}

\problem{Line integrals}{25}
Let $\mathbf{F}(x,y)=(y,\,x)$ and let $C$ be the quarter circle $x=\cos t,\ y=\sin t$ with $0\le t\le\pi/2$.
\begin{subqs}
  \subq{10} Compute $\int_C \mathbf{F}\cdot\dd\mathbf{r}$.
  \subq{5} Is $\mathbf{F}$ conservative? Motivate your answer.
  \subq{10} Which statement about $\oint_C \mathbf{F}\cdot\dd\mathbf{r}$ over any closed curve $C$ is correct?
  \begin{mc}
    \opt It is always $0$.
    \opt It equals twice the enclosed area.
    \opt It equals the enclosed area.
    \opt It depends on the orientation only.
  \end{mc}
\end{subqs}

\problem{Divergence}{15}
\begin{subqs}
  \subq{5} Compute $\diverg\mathbf{G}$ for $\mathbf{G}=(x^2,\,y^2,\,z^2)$.
  \subq{10} Use the divergence theorem to find the flux of $\mathbf{G}$ out of the unit cube $[0,1]^3$.
\end{subqs}
\end{document}
```

## Example 2: answer key

```latex
\documentclass[a4paper,11pt]{article}
\usepackage{prep}
\begin{document}
\prepheader{Multivariable Calculus (MATH201)}{MATH-T03}{Answer key}{90 min}{40}{formula sheet; no calculator}

\problem{Line integrals}{25}
Let $\mathbf{F}(x,y)=(y,\,x)$ and let $C$ be the quarter circle $x=\cos t,\ y=\sin t$ with $0\le t\le\pi/2$.
\begin{subqs}
  \subq{10} Compute $\int_C \mathbf{F}\cdot\dd\mathbf{r}$.
  \begin{solution}
    With $\dd\mathbf{r}=(-\sin t,\cos t)\,\dd t$ the integrand is $-\sin^2 t+\cos^2 t=\cos 2t$, so
    \[ \int_0^{\pi/2}\cos 2t\,\dd t=\Bigl[\tfrac12\sin 2t\Bigr]_0^{\pi/2}=0. \]
    \rubric{3}{Parametrisation and $\dd\mathbf{r}$ correct, limits $0$ to $\pi/2$}
    \rubric{4}{Integrand simplified to $\cos 2t$}
    \rubric{3}{Correct antiderivative and value $0$}
    \pitfall{Using $\dd\mathbf{r}=(\cos t,\sin t)\,\dd t$ (forgetting the derivative of the parametrisation).}
  \end{solution}
  \subq{5} Is $\mathbf{F}$ conservative? Motivate your answer.
  \begin{solution}
    Yes: $\mathbf{F}=\grad(xy)$ on all of $\R^2$, which is simply connected.
    \rubric{2}{Potential $xy$ found or $\partial_x F_2=\partial_y F_1$ checked}
    \rubric{3}{Domain argument (simply connected) stated}
  \end{solution}
\end{subqs}
\end{document}
```

## Example 3: feedback

```latex
\documentclass[a4paper,11pt]{article}
\usepackage{prep}
\begin{document}
\prepheader{Multivariable Calculus (MATH201)}{MATH-T03}{Feedback}{62 min spent}{27 / 40}{none}

\begin{fbitem}{1.1}{7}{10}
  \youwrote{Parametrised the arc correctly, then integrated $\int_0^{\pi/2}(\cos^2 t+\sin^2 t)\,\dd t$.}
  \firsterror{Used $\dd\mathbf{r}=(\cos t,\sin t)\,\dd t$ instead of $(-\sin t,\cos t)\,\dd t$.}
  \fix{Differentiate the parametrisation: the integrand becomes $\cos 2t$ and the integral is $0$.}
  \takeaway{Always differentiate the parametrisation before substituting into $\mathbf{F}\cdot\dd\mathbf{r}$.}
\end{fbitem}

\begin{fbitem}{1.2}{5}{5}
  \youwrote{Found the potential $xy$ and noted the domain is $\R^2$.}
  \takeaway{Complete answer; keep stating the domain argument.}
\end{fbitem}

\begin{fbitem}{1.3}{0}{10}
  \youwrote{Left blank.}
  \firsterror{No attempt.}
  \fix{Apply Green's theorem: the circulation equals $\iint (\partial_x F_2-\partial_y F_1)\,\dd A=2A$.}
  \takeaway{Learn the Green's theorem form of the circulation before the next set.}
\end{fbitem}
\end{document}
```

`\youwrote`, `\firsterror`, `\fix` and `\takeaway` are all optional inside an `fbitem`, and
may appear in any order, but use them in the order shown.


## Contents and long documents (reviews, lessons, keys)

- `\preptoc` — a compact clickable table of contents. Put it directly after
  `\prepheader`. It lists every `\section`, `\problem`, `\reviewpart`, `\reviewitem` and
  `\reviewshort`; the same entries appear as PDF bookmarks in the viewer's sidebar.
- `\reviewpart{Title}{one-line intro}` — starts a part of a review on a new page.
- `\reviewitem{id}{title}{score}{max}` — heading of a full item review; starts a new page
  unless it directly follows `\reviewpart`.
- `\reviewshort{id}{title}{score text}` — heading of a short item review, no page break.
- `\step{Label}` — a bold run-in label for a step of a worked solution.
- `\ok`, `\bad` — a green tick and a red cross for annotating the student's lines.
- Boxes: `\begin{redo}…\end{redo}`, `\begin{mistakebook}…\end{mistakebook}`,
  `\begin{summary}{Title}…\end{summary}`.

Math in a heading is fine; it shows as plain text in the sidebar bookmarks.
