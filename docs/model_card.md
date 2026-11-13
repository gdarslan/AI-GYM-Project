# Model card – calorie prediction experiment

**Decision:** the app does **not** use a trained calorie model. It uses the MET formula with values from the 2024
Adult Compendium of Physical Activities. The trained models only beat the formula on data that is probably
synthetic, and all of them fail on a second dataset.

Source of every number below: `notebooks/calorie_model_starter.ipynb` (sections 2–5) and `notebooks/model_results.csv`.

## Data

| | |
|---|---|
| Training data | Exercise + Calories (Kaggle, fmendes): 15,000 sessions, 1–30 minutes, 1–314 kcal. No licence, used locally only |
| Split | 80/20 train/test, `random_state = 42` (3,000 test sessions) |
| Outside test | Gym Members (Kaggle, Apache 2.0): 973 sessions, 30–120 minutes, 303–1,783 kcal; 258 Strength sessions |
| Known problem | Both datasets look generated: calories barely depend on body weight (r = 0.04) and in Gym Members every workout type burns the same per hour. See `notebooks/Sprint-Docs-Notes/` |

## Models and features

- **Baselines:** MET formula, kcal = MET × weight (kg) × hours, with MET = 5.0 (Compendium code 02061, "gym/weight
  training combined in one visit"), and the best single MET fitted on the training data (4.70).
- **Models:** Linear Regression and Random Forest (200 trees, default settings; not tuned, because a better fit to
  synthetic data would not mean a better model for real people).
- **Feature sets:** full (gender, age, height, weight, duration, heart rate, body temperature); no body temperature;
  app-only (gender, age, height, weight, duration: what the app can collect without sensors).

## Results on the test set

| Model | MAE (kcal) | RMSE (kcal) | R² |
|---|---|---|---|
| MET 5.0 (Compendium 02061) | 21.8 | 28.5 | 0.80 |
| MET 4.70 (best fit on training data) | 20.9 | 27.8 | 0.81 |
| Linear Regression, full | 8.4 | 11.5 | 0.97 |
| Random Forest, full | 1.7 | 2.7 | 0.998 |
| Random Forest, no body temperature | 1.6 | 2.5 | 0.998 |
| Linear Regression, app-only | 12.3 | 16.3 | 0.93 |
| Random Forest, app-only | 8.9 | 12.7 | 0.96 |

An R² of 0.998 is not realistic for real energy expenditure; it suggests the model learned the formula used to
generate the data. Body temperature adds nothing; heart rate does (app-only MAE 8.9 vs. 1.6 kcal).

## Results on Gym Members (a different dataset)

| Model | MAE all (kcal) | R² all | MAE Strength (kcal) | R² Strength |
|---|---|---|---|---|
| MET 5.0 | 442 | −2.1 | 456 | −2.3 |
| Linear Regression, app-only | 391 | −1.4 | 394 | −1.5 |
| Random Forest, no body temperature | 659 | −5.8 | 665 | −6.1 |
| Random Forest, app-only | 701 | −6.6 | 706 | −6.9 |

Every model is worse than predicting the average (negative R²). Random Forest never predicts more than 286 kcal,
because it cannot go beyond what it saw in training, while real sessions reach 1,783 kcal. The test measures
extrapolation, not only a new group of people.

## Bias check (test set, app-only Random Forest vs. MET formula)

| Group | n | Mean kcal | MAE RF | RF error as % of mean | MET error as % of mean |
|---|---|---|---|---|---|
| Female | 1,510 | 89.7 | 7.3 | 8.2% | 18.6% |
| Male | 1,490 | 93.0 | 10.4 | 11.2% | 29.1% |
| 20–39 | 1,466 | 82.6 | 8.9 | 10.7% | 29.3% |
| 40–59 | 879 | 95.0 | 8.9 | 9.4% | 21.4% |
| 60–79 | 655 | 105.9 | 8.8 | 8.3% | 17.4% |

The model is relatively less accurate for men and for younger users; the MET formula has the same pattern, more
strongly. Because the data is probably synthetic, this shows how the data was generated more than how real people
differ. The app shows calories as an estimate, never as a measurement.

## Not done, and why

- **Cross-validation tuning:** a better fit to synthetic data would not make the estimate better for real people.
- **RPE simulation** (estimating heart rate from a 1–10 effort score): the app does not feed a model, so the loss it
  would measure does not apply to the app.
- **Saving the model with joblib:** the model is not used by the app.

## Intended use and limits

For the report only: to show whether machine learning earns its place over a simple formula. Not for medical use.
Valid at most for sessions of 1–30 minutes and ages 20–79, and only as far as the synthetic training data reflects
reality.
