"""Calorie estimate for a workout with the MET formula: kcal = MET x body weight (kg) x hours.

This is an estimate, not a measurement. The calorie experiment (notebooks/calorie_model_starter.ipynb) found
that a trained model only beats this formula on data that is probably synthetic, so the app uses the formula.
Cardio minutes get a MET value by level; the rest of the session counts as resistance training.
"""

# Approximate MET values, based on the Compendium of Physical Activities; check the exact values against the
# Compendium before citing them.
MET_BY_RPE = [(4, 3.5), (7, 5.0), (10, 6.0)]          # resistance training by how hard it felt (RPE 1-10)
CARDIO_MET_BY_LEVEL = [(3, 4.0), (6, 7.0), (10, 10.0)]  # cardio: light, moderate, vigorous (level 1-10)
DEFAULT_MET = 5.0                                       # resistance training without an RPE
DEFAULT_LEVEL = 5


def met_for_rpe(rpe: int | None) -> float:
    if rpe is None:
        return DEFAULT_MET
    return next(met for top, met in MET_BY_RPE if rpe <= top)


def met_for_level(level: int | None) -> float:
    return next(met for top, met in CARDIO_MET_BY_LEVEL if (level or DEFAULT_LEVEL) <= top)


def estimate_kcal(weight_kg: float, duration_min: int | None, rpe: int | None,
                  cardio: list[tuple[float, int | None]] = ()) -> int | None:
    """kcal for a session: cardio parts at their own MET, the remaining minutes as resistance training.

    cardio = [(minutes, level), ...]. None when there is neither a duration nor cardio.
    """
    if not duration_min and not cardio:
        return None
    cardio_minutes = sum(m for m, _ in cardio)
    kcal = sum(met_for_level(level) * weight_kg * minutes / 60 for minutes, level in cardio)
    rest = (duration_min or 0) - cardio_minutes
    if rest > 0:
        kcal += met_for_rpe(rpe) * weight_kg * rest / 60
    return round(kcal)
