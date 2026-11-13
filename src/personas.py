"""Made-up test users with known training patterns, for tests, demos and the coach evaluation.

Each persona returns a profile and a list of workouts relative to `today`, so the expected facts (e.g. "legs not
trained for 17 days") stay true whenever it is run. The expected facts are in each docstring and are checked in
tests/test_personas.py, so the coach evaluation (eval/) can rely on them.
"""
from datetime import date, time, timedelta


def _sets(exercise, weight, reps=8, n=3):
    return [{"exercise": exercise, "reps": reps, "weight_kg": weight} for _ in range(n)]


def _hold(exercise, seconds, n=3):
    return [{"exercise": exercise, "reps": 0, "weight_kg": 0, "duration_s": seconds} for _ in range(n)]


def _cardio(exercise, minutes, level):
    return [{"exercise": exercise, "reps": 0, "weight_kg": 0, "duration_s": minutes * 60, "level": level}]


def _workout(day, sets, focus, duration=60, rpe=7):
    return {"date": day, "start_time": time(18, 0), "focus": focus, "duration_min": duration, "rpe": rpe,
            "sets": sets}


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
            workouts.append(_workout(start + timedelta(days=7 * w + day), session(w), focus))
    profile = {"age": 24, "gender": "male", "height_cm": 180, "weight_kg": 78,
               "goal": "build muscle", "experience": "intermediate"}
    return {"profile": profile, "workouts": workouts}


def new_beginner(today: date | None = None) -> dict:
    """Beginner, goal general fitness. Only two full-body workouts, 5 and 2 days ago.

    Expected facts:
    - too little data: 2 workouts (enough_data is false); nothing counts as neglected yet (5 days of history)
    - next time: barbell squat 3 × 9 @ 40 kg, pushups 3 × 11 (bodyweight), bent over barbell row 3 × 9 @ 30 kg
    """
    today = today or date.today()
    session = (_sets("barbell squat", 40) + _sets("pushups", 0, reps=10) + _sets("bent over barbell row", 30))
    workouts = [_workout(today - timedelta(days=d), session, "full body", duration=45, rpe=6) for d in (5, 2)]
    profile = {"age": 22, "gender": "female", "height_cm": 165, "weight_kg": 60,
               "goal": "general fitness", "experience": "beginner"}
    return {"profile": profile, "workouts": workouts}


def plateau(today: date | None = None) -> dict:
    """Advanced, goal get stronger. Lower/upper split three times a week for 4 weeks; nothing goes up.

    Expected facts:
    - stalled: barbell squat, romanian deadlift, barbell bench press, standing military press, bent over barbell row
    - next time (stalled: about 90% for the top of the 4-6 range): squat 3 × 6 @ 90 kg, bench 3 × 6 @ 72.5 kg
    - abdominals not trained in the period
    """
    today = today or date.today()
    start = today - timedelta(days=27)          # last workout 2 days ago

    def lower():
        return _sets("barbell squat", 100, reps=5) + _sets("romanian deadlift", 110, reps=5)

    def upper():
        return (_sets("barbell bench press - medium grip", 80, reps=5) + _sets("standing military press", 50, reps=5)
                + _sets("bent over barbell row", 70, reps=5))

    workouts = []
    for w in range(4):
        order = [lower, upper, lower] if w % 2 == 0 else [upper, lower, upper]
        for day, session in zip((0, 2, 4), order):
            workouts.append(_workout(start + timedelta(days=7 * w + day), session(),
                                     "legs" if session is lower else "chest, back, shoulders", duration=75, rpe=8))
    profile = {"age": 34, "gender": "male", "height_cm": 182, "weight_kg": 90,
               "goal": "get stronger", "experience": "advanced"}
    return {"profile": profile, "workouts": workouts}


def overtrainer(today: date | None = None) -> dict:
    """Intermediate, goal build muscle, target 3 days a week, but trains chest and triceps every day for 14 days.

    Expected facts:
    - 14 workouts in 14 days, all chest and triceps; chest and triceps still recovering (trained today)
    - quadriceps, hamstrings, glutes, calves, lats, middle back, lower back, biceps, abdominals not trained
      (neglected: 13 days of history)
    """
    today = today or date.today()
    session = (_sets("barbell bench press - medium grip", 60) + _sets("dumbbell flyes", 14, reps=12)
               + _sets("triceps pushdown", 25, reps=12))
    workouts = [_workout(today - timedelta(days=d), session, "chest, arms", duration=50, rpe=8)
                for d in range(13, -1, -1)]
    profile = {"age": 28, "gender": "male", "height_cm": 176, "weight_kg": 74,
               "goal": "build muscle", "experience": "intermediate"}
    return {"profile": profile, "workouts": workouts}


def cardio_mixed(today: date | None = None) -> dict:
    """Woman of 52, goal general fitness. Each week for 4 weeks: bike and plank, a light full-body session, rowing.
    The weights go up a little every two weeks.

    Expected facts:
    - 280 minutes of cardio in 4 weeks (8 cardio sessions): bike 40 min @ level 6, rowing 30 min @ level 7
    - goblet squat, dumbbell bench press and seated cable rows improving; nothing stalled
    - next time: bike 45 min @ level 6, rowing 35 min @ level 7, plank 3 × 50 s, goblet squat 3 × 11 @ 18 kg
    """
    today = today or date.today()
    start = today - timedelta(days=27)          # last workout 2 days ago
    workouts = []
    for w in range(4):
        base = start + timedelta(days=7 * w)
        workouts += [
            _workout(base, _cardio("bicycling, stationary", 40, 6) + _hold("plank", 45), "cardio, core", rpe=6),
            _workout(base + timedelta(days=2), _sets("goblet squat", 16 + 2 * (w // 2), reps=10)
                     + _sets("dumbbell bench press", 12 + (w // 2), reps=10)
                     + _sets("seated cable rows", 30 + 2.5 * (w // 2), reps=10),
                     "full body", duration=45, rpe=6),
            _workout(base + timedelta(days=4), _cardio("rowing, stationary", 30, 7), "cardio", duration=30, rpe=7),
        ]
    profile = {"age": 52, "gender": "female", "height_cm": 168, "weight_kg": 66,
               "goal": "general fitness", "experience": "intermediate"}
    return {"profile": profile, "workouts": workouts}


PERSONAS = {"legs_neglected": legs_neglected, "new_beginner": new_beginner, "plateau": plateau,
            "overtrainer": overtrainer, "cardio_mixed": cardio_mixed}
