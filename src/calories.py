"""Calorie estimate for a strength workout with the MET formula: kcal = MET x body weight (kg) x hours.

This is an estimate, not a measurement. The calorie experiment (notebooks/calorie_model_starter.ipynb) found
that a trained model only beats this formula on data that is probably synthetic, so the app uses the formula.
"""

# Approximate MET values for resistance training, by how hard the session felt (RPE 1-10).
# Based on the Compendium of Physical Activities (light/moderate/vigorous resistance training);
# check the exact values against the Compendium before citing them.
MET_BY_RPE = [(4, 3.5), (7, 5.0), (10, 6.0)]   # (highest RPE in band, MET)
DEFAULT_MET = 5.0                               # used when no RPE is given


def met_for_rpe(rpe: int | None) -> float:
    if rpe is None:
        return DEFAULT_MET
    return next(met for top, met in MET_BY_RPE if rpe <= top)


def estimate_kcal(weight_kg: float, duration_min: int | None, rpe: int | None) -> int | None:
    """None when the duration is unknown."""
    if not duration_min:
        return None
    return round(met_for_rpe(rpe) * weight_kg * duration_min / 60)
