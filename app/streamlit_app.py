"""AI Gym Coach – screens. Double-click start_app.bat, or start the API first and then, from the project root:

    python -m uvicorn app.main:app --reload
    python -m streamlit run app/streamlit_app.py
"""
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import altair as alt
import httpx
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import ui  # noqa: E402
from src.calories import estimate_kcal  # noqa: E402
from src.progress import neglected_muscles  # noqa: E402

# 127.0.0.1, not "localhost": on Windows "localhost" tries IPv6 first and every new connection then waits ~2 s
API = os.environ.get("GYM_API_URL", "http://127.0.0.1:8000")
GOALS = ["build muscle", "get stronger", "lose fat", "general fitness"]
LEVELS = ["beginner", "intermediate", "advanced"]
GENDERS = ["male", "female", "other"]
SUGGESTED_QUESTIONS = ["Which muscles am I neglecting?", "Am I getting stronger?",
                       "What should I focus on next week?", "Which lift has stalled, and what can I change?"]

PRIVACY_NOTICE = """
**What is stored:** a username you choose, your password as a one-way hash (it cannot be read back), your training
profile (age, gender, height, weight, goal, experience) and the workouts you log. No name or e-mail address.

**Why:** to calculate your progress and coach you. Workout and body data can count as health data under the GDPR,
so the app only stores it with your explicit consent (GDPR art. 9(2)(a)).

**The AI coach (optional, separate consent):** only your goal, experience level and the progress numbers the app
calculated are given to a language model. The model runs on this computer, so nothing is sent to another company.
Your conversations with the coach are saved in your account, so you can read them again and rate
the answers; you can delete any conversation, and all of them go when you delete your account. Admins
only see totals (how many answers, how many rated helpful), never the conversations.

**Who can see your data:** only you. Admins see account details (username, role, dates, number of workouts), never
your workouts or body data.

**How long:** until you delete your account. Demo accounts are deleted when you log out.

**Your rights:** download all your data, correct your profile, switch the AI coach off at any time, and delete your
account and everything in it. Withdrawing consent for your training data means deleting your account.

**Security:** passwords are hashed with PBKDF2 (600,000 rounds), sessions end after 8 hours, an account locks for
15 minutes after 5 wrong passwords, and the app can only be opened from this computer.
"""

st.set_page_config(page_title="AI Gym Coach", page_icon=":material/fitness_center:", layout="wide",
                   initial_sidebar_state="expanded" if "token" in st.session_state else "collapsed")
ui.apply_theme()


def log_out_locally(message: str | None = None):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    if message:
        st.session_state.flash = message


@st.cache_resource
def http_client() -> httpx.Client:
    """One connection to the API that stays open, shared by all reruns (a new connection costs ~250 ms)."""
    return httpx.Client(base_url=API, timeout=30)


def api(method: str, path: str, timeout: float = 30, **kwargs):
    """Call the backend with the login token; show a readable error instead of a crash."""
    if "token" in st.session_state:
        kwargs.setdefault("headers", {})["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        r = http_client().request(method, path, timeout=timeout, **kwargs)
    except httpx.ConnectError:
        st.error(f"Cannot reach the API at {API}. Start the app with start_app.bat, "
                 "or run: `python -m uvicorn app.main:app --reload`")
        st.stop()
    except httpx.TimeoutException:
        st.error("The request took too long. If you were asking the coach, the model may still be loading; "
                 "try again in a moment.")
        return None
    if r.status_code == 401 and "token" in st.session_state:
        log_out_locally("Your session has ended. Please log in again.")
        st.rerun()
    if r.status_code >= 400:
        detail = r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") \
            else r.text
        if isinstance(detail, list):        # validation errors from FastAPI
            detail = "; ".join(f"{'.'.join(map(str, d['loc'][1:]))}: {d['msg']}" for d in detail)
        st.error(f"{detail}")
        return None
    return r.json() if r.content else True


def signed_in(result):
    st.session_state.token = result["token"]
    st.session_state.me = result["user"]
    st.rerun()


def red_bars(df: pd.DataFrame, x: str, y: str, color: str | None = None, height: int = 320):
    """A horizontal bar chart in the app's colours."""
    enc = {"x": alt.X(f"{x}:Q", title=None, axis=alt.Axis(grid=True, gridColor=ui.BORDER, labelColor=ui.MUTED)),
           "y": alt.Y(f"{y}:N", sort="-x", title=None, axis=alt.Axis(labelColor=ui.TEXT, labelFontSize=12)),
           "tooltip": [y, alt.Tooltip(f"{x}:Q", format=".1f")] + ([color] if color else [])}
    if color:
        enc["color"] = alt.Color(f"{color}:N", title=None, scale=alt.Scale(range=[ui.RED, "#52525B"]),
                                 legend=alt.Legend(orient="top", labelColor=ui.MUTED))
        enc["yOffset"] = alt.YOffset(f"{color}:N")
    else:
        enc["color"] = alt.value(ui.RED)
    chart = alt.Chart(df).mark_bar(cornerRadiusEnd=4, height=9 if color else 14).encode(**enc)
    st.altair_chart(chart.properties(height=height, background="transparent").configure_view(strokeWidth=0),
                    width="stretch")


# ---------------- login screen ----------------
def login_screen():
    st.markdown(ui.hero("TRAIN SMARTER.", "Log your workouts, see your progress,", "and ask an AI coach about your training."),
                unsafe_allow_html=True)
    st.write("")
    left, right = st.columns([5, 6], gap="large")
    with left:
        st.markdown(
            ui.feature("1", "Log every set", "876 exercises, your last session shown, personal bests celebrated.")
            + ui.feature("2", "See what you are missing", "A muscle map and warnings for muscle groups you skip.")
            + ui.feature("3", "Ask your coach", "An AI that explains your own numbers. It runs on this computer.")
            + ui.feature("4", "Your data stays yours", "No name or e-mail needed. Download or delete everything."),
            unsafe_allow_html=True)
    with right:
        if "flash" in st.session_state:
            st.info(st.session_state.pop("flash"))
        login_tab, register_tab, demo_tab = st.tabs(["Log in", "Create account", "Try the demo"])

        with login_tab:
            with st.form("login"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Log in", type="primary", width="stretch"):
                    result = api("POST", "/auth/login", json={"username": username, "password": password})
                    if result:
                        signed_in(result)

        with register_tab:
            with st.form("register"):
                username = st.text_input("Username", help="3–30 letters, digits, '.', '_' or '-'. "
                                                          "No real name needed.")
                a, b = st.columns(2)
                password = a.text_input("Password", type="password", help="At least 8 characters. "
                                                                          "A short sentence works well.")
                repeat = b.text_input("Repeat password", type="password")
                st.markdown("**Training profile**")
                a, b = st.columns(2)
                age = a.number_input("Age", 16, 100, 25)
                gender = b.selectbox("Gender", GENDERS)
                height = a.number_input("Height (cm)", 100.0, 250.0, 175.0, step=1.0)
                weight = b.number_input("Weight (kg)", 30.0, 300.0, 75.0, step=0.5)
                goal = a.selectbox("Goal", GOALS)
                level = b.selectbox("Experience", LEVELS)
                st.markdown("**Consent**")
                health = st.checkbox("I agree that the app stores and processes my training profile and workouts "
                                     "to show my progress (required).")
                coach = st.checkbox("I also want to use the AI coach, which reads my calculated progress "
                                    "(optional, can be switched off later).", value=True)
                if st.form_submit_button("Create account", type="primary", width="stretch"):
                    if password != repeat:
                        st.error("The passwords do not match.")
                    elif not health:
                        st.error("The app cannot store your training without this consent.")
                    else:
                        result = api("POST", "/auth/register", json={
                            "username": username, "password": password, "consent_health_data": health,
                            "consent_ai_coach": coach, "age": age, "gender": gender, "height_cm": height,
                            "weight_kg": weight, "goal": goal, "experience": level})
                        if result:
                            signed_in(result)

        with demo_tab:
            st.markdown('<div class="gc-panel">A temporary account with four weeks of made-up training: legs '
                        'skipped for the last two weeks, bench press going up, shoulder press stuck. Everything is '
                        'deleted when you log out.</div>', unsafe_allow_html=True)
            st.write("")
            if st.button("Start the demo", type="primary", width="stretch", icon=":material/play_arrow:"):
                result = api("POST", "/auth/demo")
                if result:
                    signed_in(result)

        with st.expander("Privacy notice"):
            st.markdown(PRIVACY_NOTICE)


if "token" not in st.session_state:
    login_screen()
    st.stop()

me = api("GET", "/me")
if not me:
    st.stop()
st.session_state.me = me


# ---------------- pages ----------------
TREND_LABEL = {"improving": "↑ Improving", "stalled": "→ Stalled",
               "not done recently": "· Not done recently", "too little data": "· Too little data"}


def progress_page():
    ui.page_header("Your progress", f"Welcome back, {me['username']}. Goal: {me['goal']}.")
    weeks = st.segmented_control("Period", [4, 8, 12], default=4, format_func=lambda w: f"Last {w} weeks",
                                 label_visibility="collapsed") or 4
    p = api("GET", "/me/progress", params={"weeks": weeks})
    if not p or p["workouts"] == 0:
        st.info("No workouts in this period yet. Log your first one to see your progress here.")
        return
    days = p["days_since_last_trained"]
    gaps = neglected_muscles(p)
    trends = p["strength_trends"]
    improving = sum(t["trend"] == "improving" for t in trends.values())
    ui.cards([("Workouts", p["workouts"], f"in the last {weeks} weeks", False),
              ("Per week", p["workouts_per_week"], "average sessions", False),
              ("Lifts improving", f"{improving}/{len(trends)}", "estimated 1-rep max", False),
              ("Muscles to train", len(gaps), "not trained for 10+ days", bool(gaps))])
    if gaps:
        ui.alert("<b>Not trained for 10+ days:</b> " + ", ".join(
            f"{m} ({days[m]} days)" if days[m] is not None else f"{m} (not in this period)" for m in gaps))

    left, right = st.columns([5, 4], gap="large")
    with left:
        ui.section("Muscle map")
        recent = st.toggle("Last 2 weeks only", value=True)
        share = p["volume_share_pct_last_2_weeks"] if recent else p["volume_share_pct"]
        st.markdown(ui.body_map(share, days), unsafe_allow_html=True)
        st.caption("Volume = reps × weight. The main muscle of an exercise counts fully, helper muscles half. "
                   "Hover a muscle for its numbers.")
    with right:
        ui.section("Recovery")
        rec = p["recovery_guideline"]
        ready = sorted(m for m, s in rec.items() if s == "ready")
        recovering = sorted(m for m, s in rec.items() if s == "recovering")
        st.markdown("".join(f'<span class="gc-chip red">{m}</span>' for m in recovering)
                    + ("<br><br>" if recovering else "")
                    + "".join(f'<span class="gc-chip">{m}</span>' for m in ready), unsafe_allow_html=True)
        st.caption("Red: trained less than 48 hours ago, still recovering. Grey: ready. A general guideline, "
                   "not a prediction.")
        ui.section("Volume per muscle group")
        vol = pd.DataFrame([{"muscle": m, "share": v, "period": f"Last {weeks} weeks"}
                            for m, v in p["volume_share_pct"].items()]
                           + [{"muscle": m, "share": v, "period": "Last 2 weeks"}
                              for m, v in p["volume_share_pct_last_2_weeks"].items()])
        red_bars(vol[vol["share"] > 0], "share", "muscle", color="period", height=330)

    ui.section("Strength per exercise")
    table = pd.DataFrame(trends).T
    if not table.empty:
        table = table.assign(trend=table["trend"].map(TREND_LABEL))
        st.dataframe(table, width="stretch", column_config={
            "est_1rm_first_week_kg": st.column_config.NumberColumn("First (kg)", format="%.1f"),
            "est_1rm_last_week_kg": st.column_config.NumberColumn("Latest (kg)", format="%.1f"),
            "change_pct": st.column_config.NumberColumn("Change", format="%.1f%%"),
            "last_done_days_ago": st.column_config.NumberColumn("Last done", format="%d days ago"),
            "trend": "Trend"})
        workouts = api("GET", "/me/workouts") or []
        ids = {s["exercise"]: s["exercise_id"] for w in workouts for s in w["sets"]}
        exercise = st.selectbox("Progress over time", list(table.index))
        history = api("GET", f"/me/exercise-history/{ids[exercise]}") or []
        if history:
            df = pd.DataFrame(history)
            line = alt.Chart(df).mark_line(color=ui.RED, strokeWidth=3, point=alt.OverlayMarkDef(
                color=ui.RED, size=70, filled=True)).encode(
                x=alt.X("date:T", title=None, axis=alt.Axis(labelColor=ui.MUTED, gridColor=ui.BORDER, format="%d %b")),
                y=alt.Y("best_est_1rm_kg:Q", title="Estimated 1-rep max (kg)", scale=alt.Scale(zero=False),
                        axis=alt.Axis(labelColor=ui.MUTED, titleColor=ui.MUTED, gridColor=ui.BORDER)),
                tooltip=["date:T", alt.Tooltip("best_est_1rm_kg:Q", title="kg")])
            st.altair_chart(line.properties(height=260, background="transparent").configure_view(strokeWidth=0),
                            width="stretch")


FOCUS_OPTIONS = ["chest", "back", "shoulders", "arms", "legs", "core", "full body"]
MAX_PICKS = 15          # exercises added in one go
MAX_SETS = 100          # the API accepts at most 100 sets per workout
PLAN_COLUMNS = {"exercise": "object", "sets": "int64", "reps": "int64", "weight_kg": "float64"}


def empty_plan() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in PLAN_COLUMNS.items()})


def exercise_library() -> dict:
    """All 876 exercises by name, fetched once per session."""
    if "library" not in st.session_state:
        st.session_state.library = {e["name"]: e for e in api("GET", "/exercises", params={"limit": 1000}) or []}
    return st.session_state.library


def current_plan() -> pd.DataFrame:
    """The workout table including edits the user made in it since the last save of the plan."""
    df = st.session_state.get("plan", empty_plan()).copy().reset_index(drop=True)
    changes = st.session_state.get("plan_editor") or {}
    for i, cols in changes.get("edited_rows", {}).items():
        for col, value in cols.items():
            df.loc[int(i), col] = value
    df = df.drop(index=[i for i in changes.get("deleted_rows", []) if i in df.index])
    added = pd.DataFrame(changes.get("added_rows", []), columns=list(PLAN_COLUMNS))
    return pd.concat([df, added], ignore_index=True) if not added.empty else df.reset_index(drop=True)


def add_to_plan(names: list[str], last_weight: dict):
    rows = pd.DataFrame([{"exercise": n, "sets": 3, "reps": 8, "weight_kg": float(last_weight.get(n, 0.0))}
                         for n in names])
    st.session_state.plan = pd.concat([current_plan(), rows], ignore_index=True)
    st.session_state.pop("plan_editor", None)      # the table is rebuilt from the new plan
    st.session_state.add_round = st.session_state.get("add_round", 0) + 1     # empties the pick lists
    st.rerun()


def last_session_text(exercise_id):
    history = api("GET", f"/me/exercise-history/{exercise_id}") or []
    if not history:
        return "First time logging this exercise."
    last = history[-1]
    sets = ", ".join(f"{s['reps']}×{s['weight_kg']:g} kg" for s in last["sets"])
    return f"Last time ({last['date']}): {sets}"


def log_workout_page():
    ui.page_header("Log a workout", "Build today's list of exercises, then save the whole session at once.")
    saved = st.session_state.pop("last_saved", None)
    if saved:
        kcal = f" · about {saved['estimated_kcal']} kcal" if saved["estimated_kcal"] else ""
        st.success(f"Workout saved: {len(saved['sets'])} sets, {saved['total_volume_kg']:,.0f} kg total "
                   f"volume{kcal}.", icon=":material/check_circle:")
        for ex in saved["new_records"]:
            st.success(f"New personal best: {ex}", icon=":material/emoji_events:")

    library = exercise_library()
    workouts = api("GET", "/me/workouts") or []
    last_weight, times_done = {}, {}
    for w in workouts:                                   # newest first: the first weight seen is the latest
        for s in w["sets"]:
            last_weight.setdefault(s["exercise"], s["weight_kg"])
            times_done[s["exercise"]] = times_done.get(s["exercise"], 0) + 1

    # ---- the session ----
    ui.section("Session")
    a, b, c, d = st.columns([3, 2, 2, 3])
    day = a.date_input("Date", date.today(), max_value=date.today())
    start = b.time_input("Start time", datetime.now().time().replace(second=0, microsecond=0), step=300)
    duration = c.number_input("Duration (min)", 1, 300, 60)
    rpe = d.slider("How hard was it? (RPE 1–10)", 1, 10, 7)
    focus = st.pills("Focus of the day", FOCUS_OPTIONS, selection_mode="multi", key="focus") or []

    # ---- adding exercises ----
    ui.section("Add exercises")
    suggest_tab, search_tab, copy_tab = st.tabs(["Suggestions", "Search all 876", "Copy a past workout"])
    with suggest_tab:
        muscles = {m for f in focus for m in ui.FOCUS_GROUPS.get(f, [])}
        if "full body" in focus:
            muscles = {m for group in ui.FOCUS_GROUPS.values() for m in group}
        if not muscles:
            st.caption("Pick the focus of the day above to see exercises for those muscles.")
        else:
            def trains(e):
                return any(m in muscles for m in e["primary_muscles"].split("; "))
            yours = sorted((n for n in times_done if n in library and trains(library[n])), key=lambda n: -times_done[n])
            common = [n for n, e in library.items() if trains(e) and n not in yours and e["category"] == "strength"
                      and e["equipment"] in ("barbell", "dumbbell", "cable", "machine", "body only")
                      and e["level"] in ("beginner", "intermediate")]
            picks = st.multiselect("Exercises for " + ", ".join(focus), yours + common,
                                   format_func=lambda n: f"★ {n}" if n in yours else n,
                                   placeholder="Choose one or more (★ = you did it before)",
                                   key=f"suggest_{st.session_state.get('add_round', 0)}")
            if len(picks) > MAX_PICKS:
                st.warning(f"That is {len(picks)} exercises. Add at most {MAX_PICKS} at a time.")
            if st.button("Add to workout", key="add_suggested", type="primary",
                         disabled=not picks or len(picks) > MAX_PICKS,
                         icon=":material/playlist_add:"):
                add_to_plan(picks, last_weight)
    with search_tab:
        query = st.text_input("Search exercise or muscle", placeholder="e.g. bench, squat, biceps")
        words = query.lower().split()
        hits = [n for n, e in library.items()
                if words and all(w in n or w in e["primary_muscles"] for w in words)][:60]
        picks = st.multiselect("Results", hits, placeholder="Choose one or more",
                               key=f"search_{st.session_state.get('add_round', 0)}") if words else []
        if len(picks) > MAX_PICKS:
            st.warning(f"That is {len(picks)} exercises. Add at most {MAX_PICKS} at a time.")
        if words and not hits:
            st.info("No exercise found. Try a shorter word.")
        if st.button("Add to workout", key="add_searched", type="primary",
                     disabled=not picks or len(picks) > MAX_PICKS,
                     icon=":material/playlist_add:"):
            add_to_plan(picks, last_weight)
    with copy_tab:
        if not workouts:
            st.caption("No earlier workouts yet.")
        else:
            past = st.selectbox("Earlier workout", workouts, format_func=lambda w: (
                f"{w['date']}{' ' + w['start_time'][:5] if w.get('start_time') else ''} · "
                f"{w.get('focus') or 'no focus'} · {len({s['exercise'] for s in w['sets']})} exercises"))
            if st.button("Copy its exercises", icon=":material/content_copy:"):
                grouped = pd.DataFrame(past["sets"]).groupby("exercise", sort=False).agg(
                    sets=("reps", "size"), reps=("reps", "first"), weight_kg=("weight_kg", "max")).reset_index()
                st.session_state.plan = pd.concat([current_plan(), grouped], ignore_index=True)
                st.session_state.pop("plan_editor", None)
                st.rerun()

    # ---- the list ----
    ui.section("Today's workout")
    plan = st.session_state.get("plan", empty_plan())
    edited = st.data_editor(plan, key="plan_editor", num_rows="dynamic", hide_index=True, width="stretch",
                            column_config={
                                "exercise": st.column_config.SelectboxColumn("Exercise", options=sorted(library),
                                                                             required=True, width="large"),
                                "sets": st.column_config.NumberColumn("Sets", min_value=1, max_value=10, step=1,
                                                                      default=3, required=True),
                                "reps": st.column_config.NumberColumn("Reps", min_value=1, max_value=100, step=1,
                                                                      default=8, required=True),
                                "weight_kg": st.column_config.NumberColumn("Weight (kg)", min_value=0.0,
                                                                           max_value=500.0, step=2.5, default=0.0,
                                                                           format="%.1f")})
    rows = edited.dropna(subset=["exercise"])
    rows = rows[rows["exercise"].isin(library)]
    if rows.empty:
        st.caption("Add exercises above, or click the empty row of the table to type one in. "
                   "Weight 0 means bodyweight; you can change every number in the table.")
        return
    n_sets = int(rows["sets"].fillna(0).sum())
    volume = float((rows["sets"].fillna(0) * rows["reps"].fillna(0) * rows["weight_kg"].fillna(0)).sum())
    kcal = estimate_kcal(me["weight_kg"], duration, rpe)
    ui.cards([("Exercises", len(rows), ", ".join(focus) or "no focus chosen", False),
              ("Sets", n_sets, "in this workout", False),
              ("Volume", f"{volume:,.0f} kg", "reps × weight", False),
              ("Calories", f"≈{kcal}" if kcal else "–", "MET-formula estimate", False)])

    with st.expander("About these exercises", expanded=True, icon=":material/info:"):
        names = list(dict.fromkeys(rows["exercise"]))
        cols = st.columns(2)
        for i, name in enumerate(names):
            e = library[name]
            cols[i % 2].markdown(ui.exercise_card(name, e["primary_muscles"], e["secondary_muscles"], e["equipment"],
                                                  e["level"], e["category"], last_session_text(e["id"]),
                                                  e.get("description")),
                                 unsafe_allow_html=True)

    a, b = st.columns([1, 3])
    if a.button("Clear list", icon=":material/delete_sweep:", width="stretch"):
        st.session_state.plan = empty_plan()
        st.session_state.pop("plan_editor", None)
        st.rerun()
    if n_sets > MAX_SETS:
        st.error(f"A workout can hold at most {MAX_SETS} sets; this one has {n_sets}. Remove some rows or sets.")
    if b.button(f"Save workout · {n_sets} sets", type="primary", icon=":material/save:", width="stretch",
                disabled=n_sets > MAX_SETS):
        sets = [{"exercise_id": library[r.exercise]["id"], "reps": int(r.reps), "weight_kg": float(r.weight_kg or 0)}
                for r in rows.itertuples() for _ in range(int(r.sets))]
        result = api("POST", "/me/workouts", json={
            "date": str(day), "start_time": start.strftime("%H:%M"), "focus": ", ".join(focus) or None,
            "duration_min": duration, "rpe": rpe, "sets": sets})
        if result:
            st.session_state.plan = empty_plan()
            st.session_state.pop("plan_editor", None)
            st.session_state.last_saved = result
            st.rerun()


def history_page():
    ui.page_header("Workout history", "Every session you logged. Calories are MET-formula estimates.")
    workouts = api("GET", "/me/workouts") or []
    if not workouts:
        st.info("No workouts yet. Log your first one on the Log workout page.")
        return
    total_volume = sum(w["total_volume_kg"] for w in workouts)
    total_kcal = sum(w["estimated_kcal"] or 0 for w in workouts)
    ui.cards([("Sessions", len(workouts), "logged in total", False),
              ("Total volume", f"{total_volume / 1000:,.1f} t", "reps × weight", False),
              ("Calories", f"≈{total_kcal:,}", "estimated with the MET formula", False)])
    for w in workouts:
        sets = pd.DataFrame(w["sets"])
        summary = (sets.groupby("exercise", sort=False)
                   .agg(sets=("reps", "size"), reps=("reps", "first"), weight_kg=("weight_kg", "max")))
        kcal = f" · ≈{w['estimated_kcal']} kcal" if w["estimated_kcal"] else ""
        when = f"{w['date']}{' ' + w['start_time'][:5] if w.get('start_time') else ''}"
        focus = f" · {w['focus']}" if w.get("focus") else ""
        title = (f"{when}{focus} · {len(summary)} exercises · {w['total_volume_kg']:,.0f} kg · "
                 f"{w['duration_min'] or '?'} min · RPE {w['rpe'] or '?'}{kcal}")
        with st.expander(title, icon=":material/fitness_center:"):
            st.dataframe(summary, width="stretch")
            if st.button("Delete workout", key=f"del{w['id']}", icon=":material/delete:"):
                api("DELETE", f"/me/workouts/{w['id']}")
                st.rerun()


FEEDBACK_REASONS = ["wrong facts", "not relevant", "unsafe advice", "unclear", "other"]


def answer_feedback(m: dict):
    """Thumbs up or down under an answer; a thumbs down asks why. Stored with the answer."""
    fb = m.get("feedback")
    if fb:
        why = f" ({fb['reason']})" if fb.get("reason") else ""
        icon = ":material/thumb_up:" if fb["rating"] > 0 else ":material/thumb_down:"
        st.caption(f"{icon} You rated this answer {'helpful' if fb['rating'] > 0 else 'not helpful'}{why}. Thanks!")
        return
    vote = st.feedback("thumbs", key=f"vote_{m['id']}")
    if vote == 1:
        if api("PUT", f"/me/coach/messages/{m['id']}/feedback", json={"rating": 1}):
            st.rerun()
    elif vote == 0:
        with st.form(f"why_{m['id']}", border=False):
            a, b = st.columns([1, 2])
            reason = a.selectbox("What was wrong?", FEEDBACK_REASONS)
            comment = b.text_input("Comment (optional)", max_chars=500)
            if st.form_submit_button("Send feedback"):
                if api("PUT", f"/me/coach/messages/{m['id']}/feedback",
                       json={"rating": -1, "reason": reason, "comment": comment or None}):
                    st.rerun()


def coach_page():
    ui.page_header("Coach", "Ask about your own training. The app calculates; the AI explains.")
    if not me["consent_ai_coach"]:
        st.info("The AI coach is switched off for your account, so none of your data is given to the model.")
        if st.button("Switch the AI coach on", type="primary", icon=":material/smart_toy:"):
            if api("PUT", "/me/consent", json={"ai_coach": True}):
                st.rerun()
        return
    avatars = {"user": ":material/person:", "assistant": ":material/fitness_center:"}
    convs = api("GET", "/me/conversations") or []
    cid = st.session_state.get("conv_id")
    if cid not in {c["id"] for c in convs}:
        cid = st.session_state.conv_id = None

    side, main = st.columns([1, 3], gap="large")
    with side:
        if st.button("New conversation", icon=":material/add_comment:", width="stretch", type="primary"):
            st.session_state.conv_id = None
            st.rerun()
        if convs:
            ui.section("Your conversations")
        for c in convs[:15]:
            title = c["title"] if len(c["title"]) <= 32 else c["title"][:31] + "…"
            if st.button(title, key=f"conv_{c['id']}", width="stretch",
                         icon=":material/chat:" if c["id"] == cid else ":material/chat_bubble_outline:"):
                st.session_state.conv_id = c["id"]
                st.rerun()

    with main:
        messages = api("GET", f"/me/conversations/{cid}") if cid else []
        if not messages:
            st.markdown('<div class="gc-panel">Your coach reads the progress numbers the app calculated for you: '
                        'neglected muscles, strength trends and recovery. It runs on this computer and does not give '
                        'medical advice. Pick a question or type your own.</div>', unsafe_allow_html=True)
            st.write("")
            for row in (SUGGESTED_QUESTIONS[:2], SUGGESTED_QUESTIONS[2:]):
                for col, q in zip(st.columns(2), row):
                    if col.button(q, width="stretch", icon=":material/chat_bubble:"):
                        st.session_state.ask = q
                        st.rerun()
        for m in messages or []:
            with st.chat_message(m["role"], avatar=avatars[m["role"]]):
                st.markdown(m["content"])
                if m["role"] == "assistant":
                    seconds = f" · {m['latency_ms'] / 1000:.1f} s" if m.get("latency_ms") is not None else ""
                    st.caption(f"{m.get('model') or '?'} · prompt {m.get('prompt_version') or '?'}{seconds}")
                    answer_feedback(m)
                    if m.get("context"):
                        with st.expander("What the coach saw", icon=":material/visibility:"):
                            st.caption("No username, age, height, weight or gender is sent to the model.")
                            st.json(m["context"], expanded=False)
        if cid and st.button("Delete this conversation", icon=":material/delete:"):
            if api("DELETE", f"/me/conversations/{cid}"):
                st.session_state.conv_id = None
                st.rerun()

        question = st.session_state.pop("ask", None)
        if question:
            with st.chat_message("user", avatar=avatars["user"]):
                st.markdown(question)
            with st.chat_message("assistant", avatar=avatars["assistant"]), \
                    st.spinner("Thinking… (the first answer can take a while)"):
                reply = api("POST", "/me/coach", timeout=300, json={"question": question, "conversation_id": cid})
            if reply:
                st.session_state.conv_id = reply["conversation_id"]
                st.rerun()
    st.caption("The coach can make mistakes. For pain or injuries, see a doctor or physiotherapist.")
    typed = st.chat_input("Ask your coach…")
    if typed:
        st.session_state.ask = typed
        st.rerun()


def profile_page():
    ui.page_header("Training profile", "Used for your calorie estimates; your goal and level also guide the coach.")
    with st.form("profile"):
        a, b = st.columns(2)
        age = a.number_input("Age", 16, 100, int(me["age"]))
        gender = b.selectbox("Gender", GENDERS, GENDERS.index(me["gender"]))
        height = a.number_input("Height (cm)", 100.0, 250.0, float(me["height_cm"]), step=1.0)
        weight = b.number_input("Weight (kg)", 30.0, 300.0, float(me["weight_kg"]), step=0.5)
        goal = a.selectbox("Goal", GOALS, GOALS.index(me["goal"]))
        level = b.selectbox("Experience", LEVELS, LEVELS.index(me["experience"]))
        if st.form_submit_button("Save", type="primary"):
            if api("PUT", "/me", json={"age": age, "gender": gender, "height_cm": height, "weight_kg": weight,
                                       "goal": goal, "experience": level}):
                st.success("Saved")


def privacy_page():
    ui.page_header("Privacy & account", "Your consent, your data and your password.")
    with st.expander("Privacy notice", icon=":material/policy:"):
        st.markdown(PRIVACY_NOTICE)

    if me["goal"]:
        ui.section("Consent")
        given = (me["consent_health_at"] or "")[:10]
        st.markdown(f'<div class="gc-panel">Training data: consent given on <b>{given}</b> (privacy notice version '
                    f'{me["consent_version"]}). To withdraw it, delete your account below.</div>',
                    unsafe_allow_html=True)
        st.write("")
        coach_on = st.toggle("Use the AI coach", value=me["consent_ai_coach"],
                             help="When off, the coach is disabled and none of your data is given to the model.")
        if coach_on != me["consent_ai_coach"]:
            if api("PUT", "/me/consent", json={"ai_coach": coach_on}):
                st.rerun()

    a, b = st.columns(2, gap="large")
    with a:
        ui.section("Your data")
        st.caption("Everything the app stores about you, as a JSON file (your right of access).")
        export = api("GET", "/me/export")
        if export:
            st.download_button("Download all my data", json.dumps(export, indent=2), icon=":material/download:",
                               file_name=f"gym_coach_{me['username']}.json", mime="application/json")
    with b:
        if not me["is_demo"]:
            ui.section("Change password")
            with st.form("password", clear_on_submit=True):
                current = st.text_input("Current password", type="password")
                new = st.text_input("New password", type="password")
                repeat = st.text_input("Repeat new password", type="password")
                if st.form_submit_button("Change password"):
                    if new != repeat:
                        st.error("The new passwords do not match.")
                    elif api("PUT", "/me/password", json={"current_password": current, "new_password": new}):
                        st.success("Password changed. Other devices have been signed out.")

    if not me["is_demo"]:
        ui.section("Delete account")
        with st.form("delete"):
            st.write("This permanently removes your account and every workout you logged. It cannot be undone.")
            password = st.text_input("Type your password to confirm", type="password")
            if st.form_submit_button("Delete my account", type="primary"):
                if api("POST", "/me/delete", json={"password": password}):
                    log_out_locally("Your account and all your data have been deleted.")
                    st.rerun()


def admin_page():
    ui.page_header("Admin", "Manage accounts. Admins cannot see anyone's workouts or body data.")
    stats = api("GET", "/admin/stats")
    if stats:
        ui.cards([(name.replace("_", " ").capitalize(), value, "", name == "active_sessions")
                  for name, value in stats.items()])

    users = api("GET", "/admin/users") or []
    ui.section("Accounts")
    st.dataframe(pd.DataFrame(users).set_index("id"), width="stretch")

    ui.section("Manage an account")
    others = [u for u in users if u["id"] != me["id"]]
    if not others:
        st.info("There are no other accounts yet.")
    else:
        target = st.selectbox("Account", others, format_func=lambda u: f"{u['username']} ({u['role']})")
        a, b, c = st.columns(3)
        new_role = "user" if target["role"] == "admin" else "admin"
        if a.button(f"Make {new_role}", width="stretch", icon=":material/manage_accounts:"):
            if api("PUT", f"/admin/users/{target['id']}/role", json={"role": new_role}):
                st.rerun()
        if b.button("Unlock", width="stretch", disabled=not target["locked"], icon=":material/lock_open:"):
            if api("POST", f"/admin/users/{target['id']}/unlock"):
                st.rerun()
        with c:
            confirm = st.checkbox(f"Yes, delete {target['username']}")
            if st.button("Delete account", width="stretch", disabled=not confirm, type="primary",
                         icon=":material/person_remove:"):
                if api("DELETE", f"/admin/users/{target['id']}"):
                    st.rerun()

    ui.section("Coach quality")
    st.caption("How users rate the coach's answers, per model and prompt version. Totals only: admins never see "
               "the questions, the answers or who asked them.")
    quality = api("GET", "/admin/coach-quality") or []
    if quality:
        q = pd.DataFrame(quality)
        q["helpful %"] = (q["helpful"] / q["rated"].where(q["rated"] > 0) * 100).round(0)
        q["reasons"] = q["reasons"].map(lambda r: ", ".join(f"{k}: {v}" for k, v in r.items()) or "–")
        st.dataframe(q[["model", "prompt_version", "answers", "rated", "helpful", "not_helpful", "helpful %",
                        "avg_latency_ms", "reasons"]], width="stretch", hide_index=True)
    else:
        st.info("No coach answers yet.")

    ui.section("Audit log")
    st.caption("Account events and admin actions. Contains usernames, never training data.")
    audit = api("GET", "/admin/audit") or []
    if audit:
        st.dataframe(pd.DataFrame(audit), width="stretch", hide_index=True)


# ---------------- navigation ----------------
st.logo(str(ROOT / "app" / "assets" / "logo.svg"), size="large")
training = [st.Page(progress_page, title="Progress", icon=":material/monitoring:", url_path="progress", default=True),
            st.Page(log_workout_page, title="Log workout", icon=":material/add_circle:", url_path="log"),
            st.Page(history_page, title="History", icon=":material/history:", url_path="history"),
            st.Page(coach_page, title="Coach", icon=":material/smart_toy:", url_path="coach")] if me["goal"] else []
account = ([st.Page(profile_page, title="Profile", icon=":material/person:", url_path="profile")] if me["goal"] else []) \
    + [st.Page(privacy_page, title="Privacy & account", icon=":material/shield_person:", url_path="privacy",
               default=not me["goal"])]
sections = {"Training": training, "Account": account} if training else {"Account": account}
if me["role"] == "admin":
    sections["Admin"] = [st.Page(admin_page, title="Admin", icon=":material/admin_panel_settings:", url_path="admin")]
page = st.navigation(sections)

with st.sidebar:
    ui.user_badge(me["username"], me["role"], me["is_demo"])
    if me["is_demo"]:
        st.caption("Demo account: deleted when you log out.")
    if st.button("Log out", width="stretch", icon=":material/logout:"):
        api("POST", "/auth/logout")
        log_out_locally("You are logged out.")
        st.rerun()

page.run()
