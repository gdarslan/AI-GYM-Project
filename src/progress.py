"""Training progress from a workout log: the numbers the app shows and the coach explains.

Everything here is plain calculation, no AI. Input is one row per set:
date, exercise (name as in free-exercise-db), reps, weight_kg.
"""
from datetime import date, timedelta

import pandas as pd

# Muscle groups the app reports on (names as in free-exercise-db)
MAJOR_MUSCLES = ["chest", "shoulders", "triceps", "biceps", "lats", "middle back", "lower back",
                 "quadriceps", "hamstrings", "glutes", "calves", "abdominals"]
SECONDARY_SHARE = 0.5        # a secondary muscle gets half the set's volume (documented simplification)
RECENT_DAYS = 14             # "last 2 weeks" window for volume share
NOT_DONE_RECENTLY_DAYS = 10  # an exercise not done for this long is not called "stalled"
IMPROVING_PCT = 2.5          # estimated 1RM must rise more than this to count as improving
MIN_WORKOUTS = 3             # fewer workouts than this: too little data for firm conclusions


def estimated_1rm(weight_kg, reps):
    """Epley formula: weight x (1 + reps / 30)."""
    return weight_kg * (1 + reps / 30)


def muscle_volume(log: pd.DataFrame, exercises: pd.DataFrame) -> pd.DataFrame:
    """One row per (set, muscle): primary muscles get the full volume, secondary muscles half."""
    m = log.merge(exercises[["name", "primary_muscles", "secondary_muscles"]],
                  left_on="exercise", right_on="name", how="left")
    if m["primary_muscles"].isna().any():
        unknown = sorted(m.loc[m["primary_muscles"].isna(), "exercise"].unique())
        raise ValueError(f"Unknown exercises: {unknown}")
    volume = m["reps"] * m["weight_kg"]
    rows = []
    for d, vol, primary, secondary in zip(m["date"], volume, m["primary_muscles"], m["secondary_muscles"]):
        rows += [(d, mus, vol, True) for mus in filter(None, str(primary).split("; "))]
        rows += [(d, mus, vol * SECONDARY_SHARE, False) for mus in filter(None, str(secondary).split("; "))]
    return pd.DataFrame(rows, columns=["date", "muscle", "volume", "primary"])


def _share_pct(rows: pd.DataFrame) -> dict:
    vol = rows.groupby("muscle")["volume"].sum()
    total = vol.sum()
    return {m: (round(float(vol.get(m, 0.0)) / total * 100, 1) if total else 0.0) for m in MAJOR_MUSCLES}


def strength_trends(log: pd.DataFrame, today: date) -> dict:
    """Best estimated 1RM in the first and last week each weighted exercise was done."""
    weighted = log[log["weight_kg"] > 0]
    if weighted.empty:
        return {}
    weighted = weighted.assign(e1rm=estimated_1rm(weighted["weight_kg"], weighted["reps"]),
                               week=(weighted["date"] - weighted["date"].min()).dt.days // 7)
    best = weighted.groupby(["exercise", "week"])["e1rm"].max().unstack()
    last_done = weighted.groupby("exercise")["date"].max()
    trends = {}
    for ex, r in best.iterrows():
        r = r.dropna()
        first, latest = float(r.iloc[0]), float(r.iloc[-1])
        change = (latest - first) / first * 100
        days_ago = (pd.Timestamp(today) - last_done[ex]).days
        if days_ago >= NOT_DONE_RECENTLY_DAYS:
            trend = "not done recently"
        elif len(r) < 2:
            trend = "too little data"
        else:
            trend = "improving" if change > IMPROVING_PCT else "stalled"
        trends[ex] = {"est_1rm_first_week_kg": round(first, 1), "est_1rm_last_week_kg": round(latest, 1),
                      "change_pct": round(change, 1), "last_done_days_ago": int(days_ago), "trend": trend}
    return trends


def progress_summary(log: pd.DataFrame, exercises: pd.DataFrame, today: date | None = None,
                     weeks: int = 4) -> dict:
    """Summary of the last `weeks` weeks of training, ending on `today`."""
    today = today or date.today()
    log = log.assign(date=pd.to_datetime(log["date"]))
    log = log[(log["date"] >= pd.Timestamp(today) - pd.Timedelta(weeks=weeks))
              & (log["date"] <= pd.Timestamp(today))]
    if log.empty:
        return {"period_weeks": weeks, "workouts": 0, "message": "No workouts logged in this period."}

    mv = muscle_volume(log, exercises)
    recent = mv[mv["date"] > pd.Timestamp(today) - pd.Timedelta(days=RECENT_DAYS)]
    last_trained = mv.groupby("muscle")["date"].max()
    workout_days = log["date"].dt.normalize().unique()
    days_since = {m: (int((pd.Timestamp(today) - last_trained[m]).days) if m in last_trained else None)
                  for m in MAJOR_MUSCLES}
    days_of_history = int((pd.Timestamp(today) - log["date"].min()).days)
    return {
        "period_weeks": weeks,
        "period": f"{log['date'].min():%Y-%m-%d} to {log['date'].max():%Y-%m-%d}",
        "workouts": int(len(workout_days)),
        "days_of_history": days_of_history,
        "enough_data": bool(len(workout_days) >= MIN_WORKOUTS),
        "workouts_per_week": round(len(workout_days) / weeks, 1),
        "volume_share_pct": _share_pct(mv),
        "volume_share_pct_last_2_weeks": _share_pct(recent),
        "days_since_last_trained": days_since,
        "recovery_guideline": recovery_status(days_since),
        "strength_trends": strength_trends(log, today),
    }


def neglected_muscles(summary: dict, min_days: int = NOT_DONE_RECENTLY_DAYS) -> list[str]:
    """Muscle groups not trained for `min_days` or more, or not at all in the period.

    Someone who started less than `min_days` ago cannot have neglected anything yet, so nothing is flagged.
    """
    if summary.get("days_of_history", min_days) < min_days:
        return []
    days = summary.get("days_since_last_trained", {})
    return [m for m, d in days.items() if d is None or d >= min_days]


RECOVERY_DAYS = 2   # general guideline of about 48 hours rest per muscle group; a heuristic, not a prediction


def recovery_status(days_since: dict) -> dict:
    """'recovering' if a muscle group was trained less than RECOVERY_DAYS ago, else 'ready'."""
    return {m: ("recovering" if d < RECOVERY_DAYS else "ready") for m, d in days_since.items() if d is not None}


def exercise_history(log: pd.DataFrame, exercise: str) -> list[dict]:
    """Per workout day: the sets done for one exercise and the best estimated 1RM, oldest first."""
    ex = log[log["exercise"] == exercise].assign(date=lambda d: pd.to_datetime(d["date"]))
    out = []
    for day, sets in ex.groupby("date"):
        out.append({"date": f"{day:%Y-%m-%d}",
                    "sets": [{"reps": int(r), "weight_kg": float(w)} for r, w in zip(sets["reps"], sets["weight_kg"])],
                    "best_est_1rm_kg": round(float(estimated_1rm(sets["weight_kg"], sets["reps"]).max()), 1),
                    "volume_kg": float((sets["reps"] * sets["weight_kg"]).sum())})
    return out


def new_records(earlier: pd.DataFrame, workout: pd.DataFrame) -> list[str]:
    """Exercises in `workout` whose best estimated 1RM beats every earlier session (weighted exercises only)."""
    if earlier.empty:
        return []
    best_before = estimated_1rm(earlier["weight_kg"], earlier["reps"]).groupby(earlier["exercise"]).max()
    best_now = estimated_1rm(workout["weight_kg"], workout["reps"]).groupby(workout["exercise"]).max()
    return sorted(ex for ex, v in best_now.items() if ex in best_before and v > best_before[ex] and v > 0)


# ---------------- next-session targets (double progression) ----------------
# Rep range per goal. Within the range, add a rep each session; at the top of the range, add weight and start
# again at the bottom. A widely used progression rule, written as code so the coach only has to explain it.
REP_RANGES = {"get stronger": (4, 6), "build muscle": (8, 12), "lose fat": (10, 15), "general fitness": (8, 12)}
LOWER_BODY = {"quadriceps", "hamstrings", "glutes", "calves", "adductors", "abductors", "lower back"}
DELOAD = 0.9                 # a stalled lift: 90% of the weight, more reps, then build back up


def round_to(weight: float, step: float = 2.5) -> float:
    return round(weight / step) * step


def next_session_targets(log: pd.DataFrame, exercises: pd.DataFrame, goal: str, today: date | None = None) -> list:
    """Per exercise done recently: what to aim for next time, and why."""
    today = today or date.today()
    log = log.assign(date=pd.to_datetime(log["date"]))
    log = log[log["date"] <= pd.Timestamp(today)]
    if log.empty:
        return []
    lo, hi = REP_RANGES.get(goal, (8, 12))
    trends = strength_trends(log, today)
    primary = dict(zip(exercises["name"], exercises["primary_muscles"]))
    targets = []
    for ex, rows in log.groupby("exercise"):
        last_day = rows["date"].max()
        if (pd.Timestamp(today) - last_day).days >= NOT_DONE_RECENTLY_DAYS:
            continue
        sets = rows[rows["date"] == last_day]
        weight = float(sets["weight_kg"].max())
        reps = int(sets.loc[sets["weight_kg"] == weight, "reps"].min())
        n = int(len(sets))
        step = 5.0 if any(m in LOWER_BODY for m in str(primary.get(ex, "")).split("; ")) else 2.5
        if weight == 0:                                                   # bodyweight: progress in reps
            nxt_w, nxt_r = 0.0, min(reps + 1, 20)
            why = ("You reached 20 reps: make it harder (add weight or a harder variation)." if reps >= 20
                   else "Bodyweight: add one rep per set.")
        elif trends.get(ex, {}).get("trend") == "stalled":
            nxt_w, nxt_r = round_to(weight * DELOAD), hi
            why = f"Stalled: use about 90% of the weight for {hi} reps this week, then build back up."
        elif reps >= hi:
            nxt_w, nxt_r = weight + step, lo
            why = f"You reached {hi} reps: add {step:g} kg and start again at {lo} reps."
        elif reps < lo:
            nxt_w, nxt_r = weight, lo
            why = f"Below your {lo}–{hi} rep range: keep this weight until you reach {lo} reps."
        else:
            nxt_w, nxt_r = weight, reps + 1
            why = f"Add one rep per set; add weight when you reach {hi} reps."
        targets.append({"exercise": ex, "last": f"{n}×{reps} @ {weight:g} kg", "last_date": f"{last_day:%Y-%m-%d}",
                        "sets": n, "reps": nxt_r, "weight_kg": nxt_w, "reason": why})
    return sorted(targets, key=lambda t: t["last_date"], reverse=True)


# ---------------- consistency ----------------
def consistency(dates, weekly_target: int, today: date | None = None) -> dict:
    """Training days this week, and how many weeks in a row reached the weekly target.

    Weeks run Monday to Sunday. The current week only counts once its target is reached, so a streak is not
    broken on Monday morning.
    """
    today = today or date.today()
    days = {pd.Timestamp(d).date() for d in dates}
    monday = today - timedelta(days=today.weekday())

    def days_in_week(start):
        return sum(1 for d in days if start <= d < start + timedelta(days=7))

    this_week = days_in_week(monday)
    week = monday if this_week >= weekly_target else monday - timedelta(days=7)
    streak = 0
    while days_in_week(week) >= weekly_target:
        streak += 1
        week -= timedelta(days=7)
    return {"weekly_target": weekly_target, "this_week": this_week, "week_streak": streak}
