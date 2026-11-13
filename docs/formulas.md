# Formulas

Every number the app calculates, with its inputs and where it comes from. None of these is AI: they are plain,
tested code (`src/progress.py`, `src/calories.py`; tests in `tests/`). The AI coach only explains their results.

Each value is marked **sourced** (taken from a published source) or **design choice** (our own decision, with
the reason). Design choices are the first thing to revisit with real users.

## Exercise kinds

How an exercise is logged follows from free-exercise-db's own fields (`exercise_kind`):

| Kind | Rule | Logged as |
|---|---|---|
| cardio | category = cardio (14 exercises) | minutes at a level 1–10 |
| timed | category = stretching, or the name contains plank, hold, wall sit or isometric | sets × seconds |
| bodyweight | equipment = body only | sets × reps, optional extra kg |
| weighted | everything else | sets × reps × kg |
| activity | the app's own list of classes (`app/activities.csv`): yoga, Pilates, stretching routine, aerobics, step, Zumba | minutes; each class has its own MET |

Design choice: the dataset has no "logged by time" field, so holds are found by name. free-exercise-db has no
whole classes such as yoga (only single poses), so those are added from the Compendium as their own kind.

## Training volume and the muscle map

```
load   = weight_kg                                    (weighted)
load   = weight_kg + 0.65 × body weight               (bodyweight)
volume = reps × load                                  (per set; 0 for timed and cardio)
```

- The **main muscle** of an exercise gets the full volume, each **helper muscle half** (`SECONDARY_SHARE = 0.5`).
  *Design choice:* free-exercise-db lists primary and secondary muscles but not how much each works.
- **0.65 × body weight** for bodyweight exercises. *Sourced for push-ups:* a standard push-up loads the hands with
  about 64% of body mass (Ebben et al., "Kinetic analysis of several variations of push-ups"). Used for all
  bodyweight exercises as a simplification; it undercounts exercises such as pull-ups and dips, which move almost
  the whole body.
- Timed exercises and cardio add no volume but do count as training the muscle that day.
- Muscle map colour: the muscle's share of total volume, relative to the most-trained muscle; untrained = grey.
- Volume share is shown for the chosen period and for the last 14 days (*design choice*: a recent gap should not
  be hidden by older sessions).

## Strength and trends

```
estimated 1RM = load × (1 + reps / 30)                (Epley formula)
change %      = (best e1RM in the last week done − best e1RM in the first week done) / first × 100
```

- **Epley formula:** *sourced* (Epley, 1985); a widely used estimate of the one-repetition maximum.
- improving: change > 2.5%; stalled: ≤ 2.5% over at least two weeks; not done recently: last done ≥ 10 days ago;
  too little data: done in one week only. *Design choices.*

## Neglected muscles, recovery and having enough data

- **Neglected:** a major muscle group not trained for ≥ 10 days, or not at all in the period. Nothing is flagged
  when the user's history is shorter than 10 days. *Design choice.*
- **Recovery:** "recovering" if trained less than 2 days (48 hours) ago, else "ready". A rule of thumb in line with
  the ACSM advice to train each major muscle group on 2–3 days a week as a novice (ACSM, 2009); *not a prediction*,
  and labelled as a guideline in the app.
- **Enough data:** at least 3 workouts in the period. Below that, the coach is told to keep advice general.
  *Design choice.*

## Next-session targets

| Kind | Rule |
|---|---|
| weighted | **Double progression** within the goal's rep range: below the range, keep the weight until the bottom of the range; inside it, add one rep; at the top, add 2.5 kg (upper body) or 5 kg (lower body) and start again at the bottom |
| weighted, stalled | about 90% of the weight (rounded to 2.5 kg) for the top of the range, then build back up |
| bodyweight | add one rep, up to 20; then make it harder |
| timed | hold 5 seconds longer, up to 120 seconds |
| cardio | 5 minutes longer; from 45 minutes, one level harder instead |

Rep ranges per goal: get stronger 4–6, build muscle 8–12, lose fat 10–15, general fitness 8–12.

- **Sourced:** ACSM (2009) recommends loading zones such as 8–12 RM for most training, heavy loads (1–6 RM) for
  maximal strength, and "a 2–10% increase in load ... when the individual can perform the current workload for one to
  two repetitions over the desired number". Adding 2.5 kg to a 77.5 kg bench press is 3.2%, inside that range.
- **Design choices:** the exact rep ranges per goal, the 90% lighter week for stalled lifts, and the hold and cardio
  steps.

## Calories

```
kcal = MET × body weight (kg) × hours
session kcal = Σ cardio and classes at their own MET + remaining minutes × MET for the rest of the session
```

The remaining minutes count as **resistance training** (MET by RPE) when the session has weights or bodyweight
sets, and as **light stretching** (2.3, code 02101) when it has only holds, stretches or classes. A yoga or
stretching session is not weight training: before this rule, 60 minutes of yoga was counted at MET 5.0.

MET values are *sourced* from the **2024 Adult Compendium of Physical Activities** (Herrmann et al., 2024):

| Used for | MET | Compendium code and description |
|---|---|---|
| resistance training, RPE 1–4 | 3.5 | 02054, resistance (weight) training, multiple exercises, 8–15 reps at varied resistance |
| resistance training, RPE 5–7 (and no RPE) | 5.0 | 02061, health club exercise classes, general, gym/weight training combined in one visit |
| resistance training, RPE 8–10 | 6.0 | 02050, resistance (weight lifting), power lifting or body building, vigorous effort |
| cardio, level 1–3 | 4.0 | 01214, bicycling, stationary, 50 watts, light effort |
| cardio, level 4–6 | 6.0 | 01220, bicycling, stationary, 90–100 watts, moderate to vigorous |
| cardio, level 7–8 | 8.0 | 01228, bicycling, stationary, 126–150 watts |
| cardio, level 9–10 | 10.8 | 01236, bicycling, stationary, 200–229 watts, vigorous |
| rest of a session without weights | 2.3 | 02101, stretching, mild |
| yoga, Hatha / Vinyasa / Hot / Power / sun salutation | 2.3 / 2.7 / 3.0 / 4.0 / 3.5 | 02150 / 02185 / 02155 / 02160 / 02180 |
| Pilates, mat / general | 1.8 / 2.8 | 02103 / 02105 |
| stretching routine | 2.3 | 02101 |
| aerobics / step class / Zumba | 7.3 / 7.8 / 6.5 | 02000 / 02004 / 02310 |

*Design choices:* the RPE and level bands, and stationary cycling as the reference for all cardio machines
(rowing, treadmill and elliptical have similar values per effort level). The calorie experiment
(`docs/model_card.md`) explains why the app uses this formula instead of a trained model.

## Consistency

- **This week:** training days from Monday to today.
- **Week streak:** weeks in a row with at least the user's weekly target (1–7, default 3) of training days. The
  current week counts only once its target is reached, so the streak does not break on a Monday morning.
  *Design choice:* weeks rather than days, because rest days are part of training.

## Sources

- American College of Sports Medicine (2009). Progression models in resistance training for healthy adults.
  *Medicine & Science in Sports & Exercise*, 41(3), 687–708.
  [pubmed.ncbi.nlm.nih.gov/19204579](https://pubmed.ncbi.nlm.nih.gov/19204579/)
- Ebben, W. P., et al. Kinetic analysis of several variations of push-ups.
  [ojs.ub.uni-konstanz.de/cpa/article/view/4457](https://ojs.ub.uni-konstanz.de/cpa/article/view/4457)
- Epley, B. (1985). *Poundage chart*. Boyd Epley Workout, Lincoln, NE.
- Herrmann, S. D., et al. (2024). 2024 Adult Compendium of Physical Activities: A third update of the energy costs
  of human activities. *Journal of Sport and Health Science*, 13(1), 6–12.
  [pacompendium.com](https://pacompendium.com/adult-compendium/)
