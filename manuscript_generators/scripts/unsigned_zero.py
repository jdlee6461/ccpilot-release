"""Post-processing of the generated tables and macro files: a value that rounds to zero is printed without a sign.

    python scripts/unsigned_zero.py          (run from paper/; `make unsignedzero`, also the last step of the
                                              numbers, confirm2 and tables targets)

"$-$0.0" -> "0.0", interval ends included, any number of decimals (JD memo v12-1 Y3, instruction 31 v02 §1: the
signed zero is formatted in more than two places across the generators, so the rule is one post-processing step).
Comment lines (source notes with raw values) are left as they are. Idempotent; prints the replacements per file.
"""
import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
FILES = sorted((PAPER / "generated" / "tables").glob("*.tex")) + [
    PAPER / "generated" / f for f in ("numbers.tex", "confirm2_numbers.tex", "review_numbers.tex",
                                      "custody_numbers.tex", "app_confirm2.tex")]
# minus sign ($-$, a hyphen that is not part of a dash or a word, or U+2212) before 0, 0.0, 0.00, ... ending the number
NEG_ZERO = re.compile(r"(?:\$-\$|(?<![\w.\-])-|−)(0(?:\.0+)?)(?![\w.])")


def main():
    total = 0
    for f in FILES:
        if not f.exists():
            continue
        lines, n = f.read_text(encoding="utf-8").split("\n"), 0
        for i, x in enumerate(lines):
            if not x.lstrip().startswith("%"):
                lines[i], k = NEG_ZERO.subn(r"\1", x)
                n += k
        if n:
            f.write_text("\n".join(lines), encoding="utf-8")
            print(f"[unsigned_zero] {f.relative_to(PAPER)}: {n}")
        total += n
    print(f"[unsigned_zero] {total} replacements")


if __name__ == "__main__":
    main()
