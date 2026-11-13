"""Calorie estimate for a workout with the MET formula: kcal = MET x body weight (kg) x hours.

This is an estimate, not a measurement. The calorie experiment (notebooks/calorie_model_starter.ipynb) found
that a trained model only beats this formula on data that is probably synthetic, and fails badly on a second
dataset, so the app uses the formula. Cardio minutes get a MET value by level; the rest of the session counts as
resistance training.

MET values: 2024 Adult Compendium of Physical Activities (Herrmann et al., 2024, Journal of Sport and Health
Science; pacompendium.com). The code of each value is given next to it.
"""

# Resistance training, by how hard the session felt (RPE 1-10): (highest RPE in band, MET, Compendium code)
MET_BY_RPE = [
    (4, 3.5, "02054"),    # resistance (weight) training, multiple exercises, 8-15 reps at varied resistance
    (7, 5.0, "02061"),    # health club exercise classes, general, gym/weight training combined in one visit
    (10, 6.0, "02050"),   # resistance (weight lifting), power lifting or body building, vigorous effort
]
# Cardio by level 1-10, using stationary cycling as the reference: (highest level in band, MET, Compendium code).
# Other machines (rowing, treadmill, elliptical) have similar values per effort; this is an approximation.
CARDIO_MET_BY_LEVEL = [
    (3, 4.0, "01214"),    # bicycling, stationary, 50 watts, light effort
    (6, 6.0, "01220"),    # bicycling, stationary, 90-100 watts, moderate to vigorous
    (8, 8.0, "01228"),    # bicycling, stationary, 126-150 watts
    (10, 10.8, "01236"),  # bicycling, stationary, 200-229 watts, vigorous
]
DEFAULT_MET = 5.0         # no RPE given: the general gym value (02061)
LIGHT_MET = 2.3           # 02101, stretching, mild: the rest of a session without weights (only holds or classes)
DEFAULT_LEVEL = 5


def met_for_rpe(rpe: int | None) -> float:
    if rpe is None:
        return DEFAULT_MET
    return next(met for top, met, _ in MET_BY_RPE if rpe <= top)


def met_for_level(level: int | None) -> float:
    return next(met for top, met, _ in CARDIO_MET_BY_LEVEL if (level or DEFAULT_LEVEL) <= top)


def estimate_kcal(weight_kg: float, duration_min: int | None, rpe: int | None,
                  cardio: list[tuple[float, int | None]] = (), activities: list[tuple[float, float]] = (),
                  lifting: bool = True) -> int | None:
    """kcal for a session: cardio and classes at their own MET, the remaining minutes as the rest of the session.

    cardio = [(minutes, level), ...]; activities = [(minutes, MET), ...] for classes such as yoga.
    The remaining minutes count as resistance training (MET by RPE) when the session has weights or bodyweight
    sets (lifting=True), and as light stretching (2.3) when it has only holds, stretches or classes: a yoga or
    stretching session is not weight training. None when there is neither a duration nor any timed part.
    """
    if not duration_min and not cardio and not activities:
        return None
    timed_minutes = sum(m for m, _ in cardio) + sum(m for m, _ in activities)
    kcal = sum(met_for_level(level) * weight_kg * minutes / 60 for minutes, level in cardio)
    kcal += sum(met * weight_kg * minutes / 60 for minutes, met in activities)
    rest = (duration_min or 0) - timed_minutes
    if rest > 0:
        kcal += (met_for_rpe(rpe) if lifting else LIGHT_MET) * weight_kg * rest / 60
    return round(kcal)
