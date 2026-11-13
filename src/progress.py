"""Training progress from a workout log: the numbers the app shows and the coach explains.

Everything here is plain calculation, no AI. Input is one row per set:
date, exercise (name as in free-exercise-db), reps, weight_kg.
"""
from datetime import date

import pandas as pd

# Muscle groups the app reports on (names as in free-exercise-db)
MAJOR_MUSCLES = ["chest", "shoulders", "triceps", "biceps", "lats", "middle back", "lower back",
                 "quadriceps", "hamstrings", "glutes", "calves", "abdominals"]
SECONDARY_SHARE = 0.5        # a secondary muscle gets half the set's volume (documented simplification)
RECENT_DAYS = 14             # "last 2 weeks" window for volume share
NOT_DONE_RECENTLY_DAYS = 10  # an exercise not done for this long is not called "stalled"
IMPROVING_PCT = 2.5          # estimated 1RM must rise more than this to count as improving


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
    return {
        "period_weeks": weeks,
        "period": f"{log['date'].min():%Y-%m-%d} to {log['date'].max():%Y-%m-%d}",
        "workouts": int(len(workout_days)),
        "workouts_per_week": round(len(workout_days) / weeks, 1),
        "volume_share_pct": _share_pct(mv),
        "volume_share_pct_last_2_weeks": _share_pct(recent),
        "days_since_last_trained": {
            m: (int((pd.Timestamp(today) - last_trained[m]).days) if m in last_trained else None)
            for m in MAJOR_MUSCLES},
        "strength_trends": strength_trends(log, today),
    }


def neglected_muscles(summary: dict, min_days: int = NOT_DONE_RECENTLY_DAYS) -> list[str]:
    """Muscle groups not trained for `min_days` or more, or not at all in the period."""
    days = summary.get("days_since_last_trained", {})
    return [m for m, d in days.items() if d is None or d >= min_days]
