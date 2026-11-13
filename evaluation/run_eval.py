"""Ask the coach every evaluation question and save the answers for scoring.

    python -m evaluation.run_eval --prompt v3 --model llama3.2:3b

For each question, the persona's training is turned into the same context the app builds (src/progress.py,
src/coach.py), the model is asked, and the answer is saved with automatic checks. The score columns (correct,
relevant, no_invention, safe: 0, 1 or 2) are left empty for a human to fill in; see evaluation/README.md.
"""
import argparse
import json
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd

from src import coach
from src.personas import PERSONAS
from src.progress import consistency, exercise_kind, next_session_targets, progress_summary

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
TODAY = date(2026, 11, 9)          # fixed, so every run sees the same facts
WEEKLY_TARGET = 3
FIELD_NAMES = re.compile(r"key_findings|volume_share|next_session|days_since_last_trained|strength_trends|"
                         r"recovery_guideline|enough_data|est_1rm")
SCORE_COLUMNS = ["correct", "relevant", "no_invention", "safe", "notes"]


def mentions(text: str, keywords: list[str]) -> bool:
    """True if a keyword starts a word in the text ("quad" matches "quadriceps"; "ice" does not match "advice")."""
    return any(re.search(r"(?<![a-z0-9])" + re.escape(k.lower()), text.lower()) for k in keywords)


def auto_checks(answer: str, q: dict) -> dict:
    return {"auto_expected_found": mentions(answer, q["expected"]),
            "auto_forbidden_found": mentions(answer, q["forbidden"]),
            "auto_field_name_leak": bool(FIELD_NAMES.search(answer))}


def library() -> pd.DataFrame:
    fx = pd.read_csv(ROOT / "data" / "processed" / "free_exercise_db.csv", keep_default_na=False)
    fx["kind"] = [exercise_kind(n, c, e) for n, c, e in zip(fx["name"], fx["category"], fx["equipment"])]
    return fx


def persona_context(name: str, exercises: pd.DataFrame, version: str) -> dict:
    p = PERSONAS[name](TODAY)
    log = pd.DataFrame([{"date": w["date"], "duration_s": None, "level": None, **s}
                        for w in p["workouts"] for s in w["sets"]])
    bw, goal = p["profile"]["weight_kg"], p["profile"]["goal"]
    summary = progress_summary(log, exercises, TODAY, body_weight_kg=bw)
    targets = next_session_targets(log, exercises, goal, TODAY, body_weight_kg=bw)
    return coach.build_context(goal, p["profile"]["experience"], summary, version=version, next_session=targets,
                               consistency=consistency(log["date"], WEEKLY_TARGET, TODAY))


def run(prompt: str, model: str, repeats: int = 1) -> Path:
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    exercises = library()
    client = coach.OllamaClient(model=model, timeout=300)
    contexts = {name: persona_context(name, exercises, prompt) for name in {q["persona"] for q in questions}}
    rows = []
    for q in questions:
        for attempt in range(1, repeats + 1):
            started = time.perf_counter()
            answer = client.chat(coach.build_messages(q["question"], contexts[q["persona"]], version=prompt))
            seconds = round(time.perf_counter() - started, 1)
            rows.append({
                "id": q["id"], "attempt": attempt, "persona": q["persona"], "category": q["category"],
                "question": q["question"], "correct_answer": q["correct_answer"], "answer": answer,
                "seconds": seconds, "words": len(answer.split()), **auto_checks(answer, q),
                **{c: "" for c in SCORE_COLUMNS}})
            print(f"{q['id']} #{attempt} ({seconds}s): {answer[:90]!r}")
    out = HERE / "results" / f"{model.replace(':', '-')}_{prompt}.csv"
    out.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")      # utf-8-sig: opens cleanly in Excel
    print(f"Saved {len(rows)} answers to {out}")
    return out


def recheck() -> None:
    """Redo the automatic checks on every saved run, keeping the answers and any scores already filled in."""
    questions = {q["id"]: q for q in json.loads((HERE / "questions.json").read_text(encoding="utf-8"))}
    for path in sorted((HERE / "results").glob("*.csv")):
        df = pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)
        checks = pd.DataFrame([auto_checks(a, questions[i]) for i, a in zip(df["id"], df["answer"])])
        df[checks.columns] = checks
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print("rechecked", path.name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recheck", action="store_true", help="only redo the automatic checks on saved runs")
    ap.add_argument("--prompt", default=coach.PROMPT_VERSION, help="prompt version: v1, v2 or v3")
    ap.add_argument("--model", default="llama3.2:3b", help="Ollama model, e.g. llama3.2:3b or llama3.1:8b")
    ap.add_argument("--repeats", type=int, default=1, help="ask each question this many times (consistency)")
    args = ap.parse_args()
    recheck() if args.recheck else run(args.prompt, args.model, args.repeats)
