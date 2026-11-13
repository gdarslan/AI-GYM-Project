"""Compare all evaluation runs in one table: python -m evaluation.summarize

Reads every evaluation/results/*.csv. Automatic checks are always shown; the human scores (0-2) are averaged
once they are filled in. Writes evaluation/summary.md.
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SCORES = ["correct", "relevant", "no_invention", "safe"]


def summarize() -> pd.DataFrame:
    rows = []
    for path in sorted((HERE / "results").glob("*.csv")):
        df = pd.read_csv(path, encoding="utf-8-sig")
        model, prompt = path.stem.rsplit("_", 1)
        row = {"model": model, "prompt": prompt, "answers": len(df),
               "expected fact found %": round(df["auto_expected_found"].mean() * 100),
               "forbidden content %": round(df["auto_forbidden_found"].mean() * 100),
               "field-name leak %": round(df["auto_field_name_leak"].mean() * 100),
               "avg seconds": round(df["seconds"].mean(), 1)}
        scored = df[SCORES].apply(pd.to_numeric, errors="coerce")
        row["scored"] = int(scored.notna().all(axis=1).sum())
        for c in SCORES:
            row[f"{c} (0-2)"] = round(scored[c].mean(), 2) if scored[c].notna().any() else None
        rows.append(row)
    table = pd.DataFrame(rows)
    (HERE / "summary.md").write_text("# Coach evaluation summary\n\n" + table.to_markdown(index=False) + "\n",
                                     encoding="utf-8")
    return table


if __name__ == "__main__":
    print(summarize().to_string(index=False))
