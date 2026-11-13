"""Made-up test users with known training patterns, for tests, demos and the coach evaluation.

Each persona returns a profile and a list of workouts relative to `today`, so the
expected facts (e.g. "legs not trained for 17 days") stay true whenever it is run.
"""
from datetime import date, time, timedelta


def _sets(exercise, weight, reps=8, n=3):
    return [{"exercise": exercise, "reps": reps, "weight_kg": weight} for _ in range(n)]


def legs_neglected(today: date | None = None) -> dict:
    """Intermediate, goal build muscle. Push/pull/legs for 2 weeks, then push/pull/push.

    Expected facts (with `today` as given):
    - quadriceps, hamstrings, glutes, calves, lower back: last trained 17 days ago
    - bench press improving; standing military press stalled (45 kg every week)
    - squat, leg press, romanian deadlift: not done recently
    """
    today = today or date.today()
    start = today - timedelta(days=28)          # 4 weeks back; last workout 3 days ago

    def push(w):
        return (_sets("barbell bench press - medium grip", 70 + 2.5 * w)
                + _sets("standing military press", 45)
                + _sets("triceps pushdown", 30 + 2.5 * (w // 2)))

    def pull(w):
        return (_sets("bent over barbell row", 60 + 2.5 * w) + _sets("seated cable rows", 55 + 2.5 * w)
                + _sets("barbell curl", 30 + 2.5 * (w // 2)))

    def legs(w):
        return _sets("barbell squat", 90) + _sets("romanian deadlift", 80) + _sets("leg press", 150)

    workouts = []
    for w in range(4):
        for day, session in [(0, push), (2, pull), (4, legs if w < 2 else push)]:
            focus = "legs" if session is legs else "back, arms" if session is pull else "chest, shoulders, arms"
            workouts.append({"date": start + timedelta(days=7 * w + day), "start_time": time(18, 0),
                             "focus": focus, "duration_min": 60, "rpe": 7, "sets": session(w)})
    profile = {"age": 24, "gender": "male", "height_cm": 180, "weight_kg": 78,
               "goal": "build muscle", "experience": "intermediate"}
    return {"profile": profile, "workouts": workouts}


PERSONAS = {"legs_neglected": legs_neglected}
