"""AI Gym Coach – screens. Start the API first, then from the project root:

    python -m uvicorn app.main:app --reload
    python -m streamlit run app/streamlit_app.py
"""
import os
import sys
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.progress import neglected_muscles  # noqa: E402

API = os.environ.get("GYM_API_URL", "http://localhost:8000")
GOALS = ["build muscle", "get stronger", "lose fat", "general fitness"]
LEVELS = ["beginner", "intermediate", "advanced"]
GENDERS = ["male", "female", "other"]

st.set_page_config(page_title="AI Gym Coach", page_icon="🏋️", layout="wide")


def api(method: str, path: str, **kwargs):
    """Call the backend; show a readable error instead of a crash."""
    try:
        r = httpx.request(method, API + path, timeout=30, **kwargs)
    except httpx.ConnectError:
        st.error(f"Cannot reach the API at {API}. Start it with: `python -m uvicorn app.main:app --reload` (or double-click start_app.bat)")
        st.stop()
    if r.status_code >= 400:
        detail = r.json().get("detail", r.text)
        if isinstance(detail, list):        # validation errors from FastAPI
            detail = "; ".join(f"{'.'.join(map(str, d['loc'][1:]))}: {d['msg']}" for d in detail)
        st.error(f"{detail}")
        return None
    return r.json() if r.content else True


def user_label(u):
    return f"User {u['id']} · {u['goal']} · {u['experience']}"


# ---------------- sidebar: who is training ----------------
st.sidebar.title("🏋️ AI Gym Coach")
users = api("GET", "/users") or []
if users:
    ids = [u["id"] for u in users]
    current = st.session_state.get("user_id")
    index = ids.index(current) if current in ids else len(ids) - 1
    choice = st.sidebar.selectbox("Profile", users, index=index, format_func=user_label)
    st.session_state.user_id = choice["id"]
else:
    st.session_state.user_id = None

c1, c2 = st.sidebar.columns(2)
if c1.button("New profile", width="stretch"):
    st.session_state.user_id = None
    st.session_state.page = "Profile"
if c2.button("Demo user", width="stretch", help="Made-up user with 4 weeks of training"):
    demo = api("POST", "/demo-users/legs_neglected")
    if demo:
        st.session_state.user_id = demo["id"]
        st.rerun()

PAGES = ["Progress", "Log workout", "History", "Coach", "Profile"]
if st.session_state.user_id is None:
    st.session_state.page = "Profile"
page = st.sidebar.radio("Go to", PAGES, key="page")
uid = st.session_state.user_id
user = next((u for u in users if u["id"] == uid), None)


# ---------------- pages ----------------
def profile_page():
    st.header("Profile" if user else "Create your profile")
    st.caption("No name or e-mail needed: the app only stores what it uses for your progress and coaching.")
    u = user or {"age": 25, "gender": "male", "height_cm": 175.0, "weight_kg": 75.0,
                 "goal": "build muscle", "experience": "beginner"}
    with st.form("profile"):
        a, b = st.columns(2)
        age = a.number_input("Age", 16, 100, int(u["age"]))
        gender = b.selectbox("Gender", GENDERS, GENDERS.index(u["gender"]))
        height = a.number_input("Height (cm)", 100.0, 250.0, float(u["height_cm"]), step=1.0)
        weight = b.number_input("Weight (kg)", 30.0, 300.0, float(u["weight_kg"]), step=0.5)
        goal = a.selectbox("Goal", GOALS, GOALS.index(u["goal"]))
        level = b.selectbox("Experience", LEVELS, LEVELS.index(u["experience"]))
        if st.form_submit_button("Save", type="primary"):
            body = {"age": age, "gender": gender, "height_cm": height, "weight_kg": weight,
                    "goal": goal, "experience": level}
            saved = api("PUT", f"/users/{uid}", json=body) if user else api("POST", "/users", json=body)
            if saved:
                st.session_state.user_id = saved["id"]
                st.success("Saved")
                st.rerun()
    if user:
        with st.expander("Delete my data"):
            st.write("This permanently removes your profile and every workout you logged.")
            if st.checkbox("I understand") and st.button("Delete everything", type="primary"):
                if api("DELETE", f"/users/{uid}"):
                    st.session_state.user_id = None
                    st.rerun()


def log_workout_page():
    st.header("Log a workout")
    pending = st.session_state.setdefault("pending_sets", [])
    a, b, c = st.columns(3)
    day = a.date_input("Date", date.today(), max_value=date.today())
    duration = b.number_input("Duration (min)", 1, 300, 60)
    rpe = c.slider("How hard was it? (RPE 1–10)", 1, 10, 7)

    st.subheader("Add sets")
    search = st.text_input("Search exercise or muscle", placeholder="e.g. bench, squat, biceps")
    found = api("GET", "/exercises", params={"search": search, "limit": 30}) or []
    if found:
        ex = st.selectbox("Exercise", found,
                          format_func=lambda e: f"{e['name']}  —  {e['primary_muscles']}")
        a, b, c, d = st.columns([1, 1, 1, 1])
        n_sets = a.number_input("Sets", 1, 10, 3)
        reps = b.number_input("Reps", 1, 100, 8)
        kg = c.number_input("Weight (kg, 0 = bodyweight)", 0.0, 500.0, 20.0, step=2.5)
        d.write("")
        if d.button("Add", width="stretch"):
            pending += [{"exercise_id": ex["id"], "exercise": ex["name"], "reps": reps, "weight_kg": kg}
                        for _ in range(n_sets)]
            st.rerun()
    elif search:
        st.info("No exercise found. Try a shorter word.")

    if pending:
        st.dataframe(pd.DataFrame(pending)[["exercise", "reps", "weight_kg"]], width="stretch")
        a, b = st.columns(2)
        if a.button("Remove last set"):
            pending.pop()
            st.rerun()
        if b.button("Save workout", type="primary"):
            body = {"date": str(day), "duration_min": duration, "rpe": rpe,
                    "sets": [{k: s[k] for k in ("exercise_id", "reps", "weight_kg")} for s in pending]}
            if api("POST", f"/users/{uid}/workouts", json=body):
                st.session_state.pending_sets = []
                st.success("Workout saved")


def history_page():
    st.header("Workout history")
    workouts = api("GET", f"/users/{uid}/workouts") or []
    if not workouts:
        st.info("No workouts yet. Log one, or try the demo user.")
    for w in workouts:
        sets = pd.DataFrame(w["sets"])
        summary = (sets.groupby("exercise", sort=False)
                   .agg(sets=("reps", "size"), reps=("reps", "first"), weight_kg=("weight_kg", "max")))
        title = f"{w['date']} · {len(summary)} exercises · {w['duration_min'] or '?'} min · RPE {w['rpe'] or '?'}"
        with st.expander(title):
            st.dataframe(summary, width="stretch")
            if st.button("Delete workout", key=f"del{w['id']}"):
                api("DELETE", f"/users/{uid}/workouts/{w['id']}")
                st.rerun()


TREND_ICON = {"improving": "↑ improving", "stalled": "→ stalled",
              "not done recently": "· not done recently", "too little data": "· too little data"}


def progress_page():
    st.header("Your progress")
    weeks = st.radio("Period", [4, 8, 12], horizontal=True, format_func=lambda w: f"Last {w} weeks")
    p = api("GET", f"/users/{uid}/progress", params={"weeks": weeks})
    if not p or p["workouts"] == 0:
        st.info("No workouts in this period yet.")
        return
    a, b, c = st.columns(3)
    a.metric("Workouts", p["workouts"])
    b.metric("Per week", p["workouts_per_week"])
    improving = sum(t["trend"] == "improving" for t in p["strength_trends"].values())
    c.metric("Lifts improving", f"{improving} of {len(p['strength_trends'])}")

    days = p["days_since_last_trained"]
    gaps = neglected_muscles(p)
    if gaps:
        st.warning("**Not trained for 10+ days:** " + ", ".join(
            f"{m} ({days[m]} days)" if days[m] is not None else f"{m} (not in this period)" for m in gaps))

    st.subheader("Share of training volume per muscle group")
    vol = pd.DataFrame({f"Last {weeks} weeks": p["volume_share_pct"],
                        "Last 2 weeks": p["volume_share_pct_last_2_weeks"]})
    st.bar_chart(vol, horizontal=True, stack=False, y_label="% of volume")
    st.caption("Volume = reps × weight. The main muscle of an exercise counts fully, helper muscles count half.")

    st.subheader("Strength per exercise")
    st.caption("Estimated 1-rep max (Epley formula), first vs. last week the exercise was done.")
    trends = pd.DataFrame(p["strength_trends"]).T
    if not trends.empty:
        trends["trend"] = trends["trend"].map(TREND_ICON)
        st.dataframe(trends.rename(columns={
            "est_1rm_first_week_kg": "first (kg)", "est_1rm_last_week_kg": "latest (kg)",
            "change_pct": "change %", "last_done_days_ago": "last done (days ago)"}),
            width="stretch")


def coach_page():
    st.header("Coach")
    st.info("The AI coach is the next step of the project. It will answer questions like these using the "
            "progress numbers on the Progress page, so its answers are based on your own training.")
    for q in ["Which muscles am I neglecting?", "Am I getting stronger?", "What should I focus on next week?"]:
        st.markdown(f"- *{q}*")
    st.chat_input("Ask your coach…", disabled=True)


{"Profile": profile_page, "Log workout": log_workout_page, "History": history_page,
 "Progress": progress_page, "Coach": coach_page}[page]()
