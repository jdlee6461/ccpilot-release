"""Repository bundle supplementary_tables/ (instruction 10 §6): the text, tables, and figures that v5 moved out of the
paper and its supplementary material, taken verbatim from git 7c55fbc (sections/appendix.tex, sections/supplementary.tex).

    python scripts/make_supplementary_tables.py     (run from paper/ after main.pdf and supplementary.pdf are built;
                                                      `make repotables` also compiles supplementary_tables.pdf)

Kept: appendix A-C of 7c55fbc (earlier evaluation; confirmation experiment, further results; implementation details)
and sections I-III of its supplementary material (held-out analyses, reanalysis, confirmation diagnostics and tuning).
Left out: appendix D (deviations; in the paper) and every float that the v5 supplementary material now shows (EXCLUDE),
except the two tables of the section "Additional Analyses Added During Revision", which is kept whole (verdict 11 §1-4:
its opening paragraph marks the analyses as post hoc inside the bundle; the tables are also Tables S6 and S7).
Added (verdict 11 §1-3): the sentence of 7c55fbc sections/sec4_method.tex that defines the uniform scale, with its
numbered equation (label eq:tau-uni), before the paragraph on the logarithmic scale, so that Algorithm R1 refers to it.
Added in the same way (v5-3 made the equation inline in the paper): the sentence of 7c55fbc sections/sec4_method.tex that sets
the observed target under imperfect detection, with its numbered equation (label eq:det-target), before the paragraph
of the supplementary text that refers to it. No sentence is changed. Only mechanical edits:
references resolved against this document, the v5 paper (prefix M-) and the v5 supplementary material (prefix S-);
\\appendices dropped; floats numbered R1, R2, ... (tables and figures) and equations (R1), (R2), ...
Unresolved references are listed in supplementary_tables/unresolved_refs.txt and print as "??".
"""
import re
import subprocess
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
SRC = "7c55fbc"
OUT = PAPER / "supplementary_tables"
EXCLUDE = {"tab:main", "tab:c2_targets", "tab:c2_classify", "tab:c2_partitions", "tab:c2_custody"}


def show(path):
    return subprocess.run(["git", "show", f"{SRC}:{path}"], cwd=PAPER, capture_output=True, text=True, check=True).stdout


def labels_of_aux(aux):
    t = (PAPER / aux).read_text(errors="replace") if (PAPER / aux).exists() else ""
    return set(re.findall(r"\\newlabel\{([^}]*)\}", t))


def drop_floats(s):
    """remove float environments whose label is in EXCLUDE; return text and removed labels"""
    gone = []
    pat = re.compile(r"\\begin\{(table\*?|figure\*?)\}.*?\\end\{\1\}\n?", re.S)
    def f(m):
        labs = set(re.findall(r"\\label\{([^}]*)\}", m.group(0)))
        if labs & EXCLUDE:
            gone.extend(sorted(labs)); return ""
        return m.group(0)
    return pat.sub(f, s), gone


def section_slice(s, start_title, end_title=None):
    i = s.index(f"\\section{{{start_title}}}")
    j = s.index(f"\\section{{{end_title}}}") if end_title else len(s)
    return s[i:j]


def main():
    app, sup = show("sections/appendix.tex"), show("sections/supplementary.tex")
    app = section_slice(app, "Earlier Evaluation on the Held-Out Period", "Deviations")
    sec4 = show("sections/sec4_method.tex")
    i = sec4.index("The original \\emph{uniform} scale corresponds to"); j = sec4.index("calibration data.", i) + len("calibration data.")
    uni = ("% verbatim from " + SRC + " sections/sec4_method.tex (definition of the uniform scale; verdict 11 §1-3)\n"
           "\\paragraph*{Uniform scale (Section IV of version " + SRC + ")}\n" + sec4[i:j] + "\n\n")
    k = app.index("\\paragraph*{Why a logarithmic scale}")
    app = app[:k] + uni + app[k:]
    sup_intro = sup[sup.index("\\section*{Supplementary Material}"):sup.index("\\section{Additional Analyses on the Held-Out Period}")]
    sup_intro = sup_intro.replace("\\section*{Supplementary Material}", "\\section*{From the Supplementary Material of Version 7c55fbc}")
    sup_body = section_slice(sup, "Additional Analyses on the Held-Out Period")
    app, g1 = drop_floats(app); sup_intro, g2 = drop_floats(sup_intro); sup_body, g3 = drop_floats(sup_body)
    body_app = app; body_sup = sup_intro + sup_body
    here = set(re.findall(r"\\label\{([^}]*)\}", body_app + body_sup))
    main_l, supp_l = labels_of_aux("main.aux"), labels_of_aux("supplementary.aux")   # each document's own labels
    unresolved = []

    def resolve(m):
        cmd, lab = m.group(1), m.group(2)
        base = lab[2:] if lab[:2] in ("S-", "M-") else lab
        if base in here:
            return f"\\{cmd}{{{base}}}"
        if base in supp_l:
            return f"\\{cmd}{{S-{base}}}"
        if base in main_l:
            return f"\\{cmd}{{M-{base}}}"
        unresolved.append(lab)
        return m.group(0)

    # 7c55fbc equations that the v5 paper no longer numbers: the defining sentence, verbatim, before the first paragraph
    # of this document that refers to it (verdict 11 §1-3)
    i = sec4.index("To target a true recall of $1-\\alpha$, the observed"); j = sec4.index("for the deployed detector.", i) + len("for the deployed detector.")
    det = ("% verbatim from " + SRC + " sections/sec4_method.tex (observed target under imperfect detection)\n"
           "\\paragraph*{Detection target (Section IV of version " + SRC + ")}\n" + sec4[i:j] + "\n\n")
    if "eq:det-target" not in main_l:
        k = body_sup.index("eq:det-target}"); k = body_sup.rfind("\n\n", 0, k) + 2
        body_sup = body_sup[:k] + det + body_sup[k:]
        here.add("eq:det-target")
    ref = re.compile(r"\\(ref|eqref|pageref)\{([^}]*)\}")
    body_app, body_sup = ref.sub(resolve, body_app), ref.sub(resolve, body_sup)
    OUT.mkdir(exist_ok=True)
    head = (f"% GENERATED by scripts/make_supplementary_tables.py from git {SRC} (verbatim text; references resolved, "
            f"floats in the v5 supplementary material left out: {', '.join(sorted(set(g1 + g2 + g3)))})\n")
    (OUT / "body_appendix.tex").write_text(head + body_app)
    (OUT / "body_supplementary.tex").write_text(head + body_sup)
    (OUT / "unresolved_refs.txt").write_text("\n".join(sorted(set(unresolved))) + ("\n" if unresolved else ""))
    print(f"[supplementary_tables] floats left out: {sorted(set(g1 + g2 + g3))}; unresolved refs: {sorted(set(unresolved))}")


if __name__ == "__main__":
    main()
