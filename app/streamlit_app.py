"""AI Gym Coach – screens. Double-click start_app.bat, or start the API first and then, from the project root:

    python -m uvicorn app.main:app --reload
    python -m streamlit run app/streamlit_app.py
"""
import json
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
SUGGESTED_QUESTIONS = ["Which muscles am I neglecting?", "Am I getting stronger?",
                       "What should I focus on next week?", "Which lift has stalled, and what can I change?"]

PRIVACY_NOTICE = """
**What is stored:** a username you choose, your password as a one-way hash (it cannot be read back), your training
profile (age, gender, height, weight, goal, experience) and the workouts you log. No name or e-mail address.

**Why:** to calculate your progress and coach you. Workout and body data can count as health data under the GDPR,
so the app only stores it with your explicit consent (GDPR art. 9(2)(a)).

**The AI coach (optional, separate consent):** only your goal, experience level and the progress numbers the app
calculated are given to a language model. The model runs on this computer, so nothing is sent to another company.
Questions and answers are saved without your username, to evaluate how well the coach works.

**Who can see your data:** only you. Admins see account details (username, role, dates, number of workouts), never
your workouts or body data.

**How long:** until you delete your account. Demo accounts are deleted when you log out.

**Your rights:** download all your data, correct your profile, switch the AI coach off at any time, and delete your
account and everything in it. Withdrawing consent for your training data means deleting your account.

**Security:** passwords are hashed with PBKDF2 (600,000 rounds), sessions end after 8 hours, an account locks for
15 minutes after 5 wrong passwords, and the app can only be opened from this computer.
"""

st.set_page_config(page_title="AI Gym Coach", page_icon="🏋️", layout="wide")


def log_out_locally(message: str | None = None):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    if message:
        st.session_state.flash = message


def api(method: str, path: str, timeout: float = 30, **kwargs):
    """Call the backend with the login token; show a readable error instead of a crash."""
    if "token" in st.session_state:
        kwargs.setdefault("headers", {})["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        r = httpx.request(method, API + path, timeout=timeout, **kwargs)
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


# ---------------- login screen ----------------
def login_screen():
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        st.title("🏋️ AI Gym Coach")
        st.caption("Log your workouts, see your progress, and ask an AI coach about your own training.")
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
            st.write("A temporary account with 4 weeks of made-up training: legs skipped for the last two weeks, "
                     "bench press going up, shoulder press stuck. It is deleted when you log out.")
            if st.button("Start the demo", type="primary", width="stretch"):
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

# ---------------- sidebar ----------------
st.sidebar.title("🏋️ AI Gym Coach")
badge = " · admin" if me["role"] == "admin" else ""
st.sidebar.markdown(f"Signed in as **{me['username']}**{badge}")
if me["is_demo"]:
    st.sidebar.caption("Demo account: deleted when you log out.")
pages = (["Progress", "Log workout", "History", "Coach", "Profile"] if me["goal"] else []) + ["Privacy & account"]
if me["role"] == "admin":
    pages.append("Admin")
page = st.sidebar.radio("Go to", pages, key="page")
if st.sidebar.button("Log out", width="stretch"):
    api("POST", "/auth/logout")
    log_out_locally("You are logged out.")
    st.rerun()


# ---------------- pages ----------------
def profile_page():
    st.header("Training profile")
    st.caption("Used for your calorie estimates; your goal and experience level are also given to the coach.")
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
    st.header("Privacy & account")
    with st.expander("Privacy notice", expanded=False):
        st.markdown(PRIVACY_NOTICE)

    if me["goal"]:
        st.subheader("Consent")
        given = (me["consent_health_at"] or "")[:10]
        st.write(f"Training data: consent given on {given} (privacy notice version {me['consent_version']}). "
                 "To withdraw it, delete your account below.")
        coach_on = st.toggle("Use the AI coach", value=me["consent_ai_coach"],
                             help="When off, the coach is disabled and none of your data is given to the model.")
        if coach_on != me["consent_ai_coach"]:
            if api("PUT", "/me/consent", json={"ai_coach": coach_on}):
                st.rerun()

    a, b = st.columns(2)
    with a:
        st.subheader("Your data")
        export = api("GET", "/me/export")
        if export:
            st.download_button("Download all my data (JSON)", json.dumps(export, indent=2),
                               file_name=f"gym_coach_{me['username']}.json", mime="application/json")
    with b:
        if not me["is_demo"]:
            st.subheader("Change password")
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
        st.subheader("Delete account")
        with st.form("delete"):
            st.write("This permanently removes your account and every workout you logged. It cannot be undone.")
            password = st.text_input("Type your password to confirm", type="password")
            if st.form_submit_button("Delete my account", type="primary"):
                if api("POST", "/me/delete", json={"password": password}):
                    log_out_locally("Your account and all your data have been deleted.")
                    st.rerun()


def last_session_text(exercise_id):
    history = api("GET", f"/me/exercise-history/{exercise_id}") or []
    if not history:
        return "First time logging this exercise."
    last = history[-1]
    sets = ", ".join(f"{s['reps']}×{s['weight_kg']:g} kg" for s in last["sets"])
    return f"Last time ({last['date']}): {sets}"


def log_workout_page():
    st.header("Log a workout")
    pending = st.session_state.setdefault("pending_sets", [])
    a, b, c = st.columns(3)
    day = a.date_input("Date", date.today(), max_value=date.today())
    duration = b.number_input("Duration (min)", 1, 300, 60)
    rpe = c.slider("How hard was it? (RPE 1–10)", 1, 10, 7)

    workouts = api("GET", "/me/workouts") or []
    if workouts and not pending and st.button(f"Repeat last workout ({workouts[0]['date']})"):
        pending += [{k: s[k] for k in ("exercise_id", "exercise", "reps", "weight_kg")} for s in workouts[0]["sets"]]
        st.rerun()

    st.subheader("Add sets")
    search = st.text_input("Search exercise or muscle", placeholder="e.g. bench, squat, biceps")
    found = api("GET", "/exercises", params={"search": search, "limit": 30}) or []
    if found:
        ex = st.selectbox("Exercise", found, format_func=lambda e: f"{e['name']}  —  {e['primary_muscles']}")
        st.caption(last_session_text(ex["id"]))
        a, b, c, d = st.columns(4)
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
        a, b, c = st.columns(3)
        if a.button("Remove last set"):
            pending.pop()
            st.rerun()
        if b.button("Clear all"):
            pending.clear()
            st.rerun()
        if c.button("Save workout", type="primary"):
            body = {"date": str(day), "duration_min": duration, "rpe": rpe,
                    "sets": [{k: s[k] for k in ("exercise_id", "reps", "weight_kg")} for s in pending]}
            saved = api("POST", "/me/workouts", json=body)
            if saved:
                st.session_state.pending_sets = []
                st.session_state.last_saved = saved
                st.rerun()
    saved = st.session_state.pop("last_saved", None)
    if saved:
        kcal = f", about {saved['estimated_kcal']} kcal" if saved["estimated_kcal"] else ""
        st.success(f"Workout saved: {saved['total_volume_kg']:,.0f} kg total volume{kcal}.")
        for ex in saved["new_records"]:
            st.success(f"🏆 New personal best: {ex}")


def history_page():
    st.header("Workout history")
    workouts = api("GET", "/me/workouts") or []
    if not workouts:
        st.info("No workouts yet. Log your first one on the Log workout page.")
        return
    st.caption("Calories are estimated with the MET formula (MET × body weight × hours), using your RPE to pick "
               "the MET value. They are estimates, not measurements.")
    for w in workouts:
        sets = pd.DataFrame(w["sets"])
        summary = (sets.groupby("exercise", sort=False)
                   .agg(sets=("reps", "size"), reps=("reps", "first"), weight_kg=("weight_kg", "max")))
        kcal = f" · ≈{w['estimated_kcal']} kcal" if w["estimated_kcal"] else ""
        title = (f"{w['date']} · {len(summary)} exercises · {w['total_volume_kg']:,.0f} kg volume · "
                 f"{w['duration_min'] or '?'} min · RPE {w['rpe'] or '?'}{kcal}")
        with st.expander(title):
            st.dataframe(summary, width="stretch")
            if st.button("Delete workout", key=f"del{w['id']}"):
                api("DELETE", f"/me/workouts/{w['id']}")
                st.rerun()


TREND_ICON = {"improving": "↑ improving", "stalled": "→ stalled",
              "not done recently": "· not done recently", "too little data": "· too little data"}


def progress_page():
    st.header("Your progress")
    weeks = st.radio("Period", [4, 8, 12], horizontal=True, format_func=lambda w: f"Last {w} weeks")
    p = api("GET", "/me/progress", params={"weeks": weeks})
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

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Share of training volume per muscle group")
        vol = pd.DataFrame({f"Last {weeks} weeks": p["volume_share_pct"],
                            "Last 2 weeks": p["volume_share_pct_last_2_weeks"]})
        st.bar_chart(vol, horizontal=True, stack=False, y_label="% of volume")
        st.caption("Volume = reps × weight. The main muscle of an exercise counts fully, helper muscles count half.")
    with right:
        st.subheader("Recovery")
        rec = pd.DataFrame({"days since trained": {m: d for m, d in days.items() if d is not None},
                            "status": p["recovery_guideline"]})
        rec["status"] = rec["status"].map({"ready": "✅ ready", "recovering": "⏳ recovering"})
        st.dataframe(rec.sort_values("days since trained"), width="stretch")
        st.caption("Guideline: about 48 hours of rest per muscle group. A general rule, not a prediction.")

    st.subheader("Strength per exercise")
    st.caption("Estimated 1-rep max (Epley formula), first vs. last week the exercise was done.")
    trends = pd.DataFrame(p["strength_trends"]).T
    if not trends.empty:
        shown = trends.assign(trend=trends["trend"].map(TREND_ICON)).rename(columns={
            "est_1rm_first_week_kg": "first (kg)", "est_1rm_last_week_kg": "latest (kg)",
            "change_pct": "change %", "last_done_days_ago": "last done (days ago)"})
        st.dataframe(shown, width="stretch")

        workouts = api("GET", "/me/workouts") or []
        ids = {s["exercise"]: s["exercise_id"] for w in workouts for s in w["sets"]}
        exercise = st.selectbox("Show progress over time for", list(trends.index))
        history = api("GET", f"/me/exercise-history/{ids[exercise]}") or []
        if history:
            chart = pd.DataFrame(history).set_index("date")[["best_est_1rm_kg"]]
            st.line_chart(chart.rename(columns={"best_est_1rm_kg": "estimated 1-rep max (kg)"}))


def coach_page():
    st.header("Coach")
    if not me["consent_ai_coach"]:
        st.info("The AI coach is switched off for your account, so none of your data is given to the model.")
        if st.button("Switch the AI coach on", type="primary"):
            if api("PUT", "/me/consent", json={"ai_coach": True}):
                st.rerun()
        return
    st.caption("Ask about your own training. The app calculates your progress; the AI explains it. "
               "The coach can make mistakes and does not give medical advice.")
    chat = st.session_state.setdefault("chat", [])

    for turn in chat:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    question = st.chat_input("Ask your coach…")
    if not chat:
        cols = st.columns(len(SUGGESTED_QUESTIONS))
        for col, q in zip(cols, SUGGESTED_QUESTIONS):
            if col.button(q, width="stretch"):
                question = q

    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"), st.spinner("Thinking… (the first answer can take a while)"):
            reply = api("POST", "/me/coach", timeout=300,
                        json={"question": question, "history": [{"role": t["role"], "content": t["content"]}
                                                                for t in chat]})
        if reply:
            chat += [{"role": "user", "content": question}, {"role": "assistant", "content": reply["answer"]}]
            st.session_state.coach_meta = reply
            st.rerun()

    meta = st.session_state.get("coach_meta")
    if chat and st.button("New conversation"):
        chat.clear()
        st.rerun()
    if meta:
        with st.expander("What the coach sees"):
            st.caption(f"Model: {meta['model']} · prompt {meta['prompt_version']}. "
                       "No username, age, height, weight or gender is sent.")
            st.json(meta["context"], expanded=False)


def admin_page():
    st.header("Admin")
    st.caption("Admins manage accounts. They cannot see anyone's workouts or body data.")
    stats = api("GET", "/admin/stats")
    if stats:
        cols = st.columns(len(stats))
        for col, (name, value) in zip(cols, stats.items()):
            col.metric(name.replace("_", " ").capitalize(), value)

    users = api("GET", "/admin/users") or []
    st.subheader("Accounts")
    st.dataframe(pd.DataFrame(users).set_index("id"), width="stretch")

    st.subheader("Manage an account")
    others = [u for u in users if u["id"] != me["id"]]
    if not others:
        st.info("There are no other accounts yet.")
    else:
        target = st.selectbox("Account", others, format_func=lambda u: f"{u['username']} ({u['role']})")
        a, b, c = st.columns(3)
        new_role = "user" if target["role"] == "admin" else "admin"
        if a.button(f"Make {new_role}", width="stretch"):
            if api("PUT", f"/admin/users/{target['id']}/role", json={"role": new_role}):
                st.rerun()
        if b.button("Unlock", width="stretch", disabled=not target["locked"]):
            if api("POST", f"/admin/users/{target['id']}/unlock"):
                st.rerun()
        with c:
            confirm = st.checkbox(f"Yes, delete {target['username']}")
            if st.button("Delete account", width="stretch", disabled=not confirm, type="primary"):
                if api("DELETE", f"/admin/users/{target['id']}"):
                    st.rerun()

    st.subheader("Audit log")
    st.caption("Account events and admin actions. Contains usernames, never training data.")
    audit = api("GET", "/admin/audit") or []
    if audit:
        st.dataframe(pd.DataFrame(audit), width="stretch", hide_index=True)


{"Profile": profile_page, "Privacy & account": privacy_page, "Log workout": log_workout_page,
 "History": history_page, "Progress": progress_page, "Coach": coach_page, "Admin": admin_page}[page]()
