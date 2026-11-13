"""AI Gym Coach – screens. Double-click start_app.bat, or start the API first and then, from the project root:

    python -m uvicorn app.main:app --reload
    python -m streamlit run app/streamlit_app.py
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

import altair as alt
import httpx
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import ui  # noqa: E402
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

st.set_page_config(page_title="AI Gym Coach", page_icon=":material/fitness_center:", layout="wide",
                   initial_sidebar_state="expanded" if "token" in st.session_state else "collapsed")
ui.apply_theme()


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


def last_session_text(exercise_id):
    history = api("GET", f"/me/exercise-history/{exercise_id}") or []
    if not history:
        return "First time logging this exercise."
    last = history[-1]
    sets = ", ".join(f"{s['reps']}×{s['weight_kg']:g} kg" for s in last["sets"])
    return f"Last time ({last['date']}): {sets}"


def log_workout_page():
    ui.page_header("Log a workout", "Add your sets, then save. Your progress updates straight away.")
    pending = st.session_state.setdefault("pending_sets", [])
    saved = st.session_state.pop("last_saved", None)
    if saved:
        kcal = f" · about {saved['estimated_kcal']} kcal" if saved["estimated_kcal"] else ""
        st.success(f"Workout saved: {saved['total_volume_kg']:,.0f} kg total volume{kcal}.")
        for ex in saved["new_records"]:
            st.success(f"New personal best: {ex}", icon=":material/emoji_events:")

    a, b, c = st.columns(3)
    day = a.date_input("Date", date.today(), max_value=date.today())
    duration = b.number_input("Duration (min)", 1, 300, 60)
    rpe = c.slider("How hard was it? (RPE 1–10)", 1, 10, 7)

    workouts = api("GET", "/me/workouts") or []
    if workouts and not pending and st.button(f"Repeat last workout ({workouts[0]['date']})",
                                              icon=":material/replay:"):
        pending += [{k: s[k] for k in ("exercise_id", "exercise", "reps", "weight_kg")} for s in workouts[0]["sets"]]
        st.rerun()

    ui.section("Add sets")
    search = st.text_input("Search exercise or muscle", placeholder="e.g. bench, squat, biceps")
    found = (api("GET", "/exercises", params={"search": search, "limit": 30}) or []) if search.strip() else []
    if not search.strip():
        st.caption("Type a name or a muscle to search the 876 exercises.")
    elif found:
        ex = st.selectbox("Exercise", found, format_func=lambda e: f"{e['name']}  —  {e['primary_muscles']}")
        st.caption(last_session_text(ex["id"]))
        a, b, c, d = st.columns(4)
        n_sets = a.number_input("Sets", 1, 10, 3)
        reps = b.number_input("Reps", 1, 100, 8)
        kg = c.number_input("Weight (kg, 0 = bodyweight)", 0.0, 500.0, 20.0, step=2.5)
        d.write("")
        if d.button("Add", width="stretch", icon=":material/add:"):
            pending += [{"exercise_id": ex["id"], "exercise": ex["name"], "reps": reps, "weight_kg": kg}
                        for _ in range(n_sets)]
            st.rerun()
    elif search:
        st.info("No exercise found. Try a shorter word.")

    if pending:
        ui.section(f"This workout · {len(pending)} sets")
        st.dataframe(pd.DataFrame(pending)[["exercise", "reps", "weight_kg"]], width="stretch", hide_index=True)
        a, b, c = st.columns(3)
        if a.button("Remove last set", icon=":material/undo:", width="stretch"):
            pending.pop()
            st.rerun()
        if b.button("Clear all", icon=":material/delete:", width="stretch"):
            pending.clear()
            st.rerun()
        if c.button("Save workout", type="primary", icon=":material/save:", width="stretch"):
            body = {"date": str(day), "duration_min": duration, "rpe": rpe,
                    "sets": [{k: s[k] for k in ("exercise_id", "reps", "weight_kg")} for s in pending]}
            result = api("POST", "/me/workouts", json=body)
            if result:
                st.session_state.pending_sets = []
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
        title = (f"{w['date']} · {len(summary)} exercises · {w['total_volume_kg']:,.0f} kg · "
                 f"{w['duration_min'] or '?'} min · RPE {w['rpe'] or '?'}{kcal}")
        with st.expander(title, icon=":material/fitness_center:"):
            st.dataframe(summary, width="stretch")
            if st.button("Delete workout", key=f"del{w['id']}", icon=":material/delete:"):
                api("DELETE", f"/me/workouts/{w['id']}")
                st.rerun()


def coach_page():
    ui.page_header("Coach", "Ask about your own training. The app calculates; the AI explains.")
    if not me["consent_ai_coach"]:
        st.info("The AI coach is switched off for your account, so none of your data is given to the model.")
        if st.button("Switch the AI coach on", type="primary", icon=":material/smart_toy:"):
            if api("PUT", "/me/consent", json={"ai_coach": True}):
                st.rerun()
        return
    chat = st.session_state.setdefault("chat", [])
    avatars = {"user": ":material/person:", "assistant": ":material/fitness_center:"}

    if not chat:
        st.markdown('<div class="gc-panel">Your coach reads the progress numbers the app calculated for you: '
                    'neglected muscles, strength trends and recovery. It runs on this computer and does not give '
                    'medical advice. Pick a question or type your own.</div>', unsafe_allow_html=True)
        st.write("")
    for turn in chat:
        with st.chat_message(turn["role"], avatar=avatars[turn["role"]]):
            st.markdown(turn["content"])

    question = st.chat_input("Ask your coach…")
    if not chat:
        for row in (SUGGESTED_QUESTIONS[:2], SUGGESTED_QUESTIONS[2:]):
            for col, q in zip(st.columns(2), row):
                if col.button(q, width="stretch", icon=":material/chat_bubble:"):
                    question = q

    if question:
        with st.chat_message("user", avatar=avatars["user"]):
            st.markdown(question)
        with st.chat_message("assistant", avatar=avatars["assistant"]), \
                st.spinner("Thinking… (the first answer can take a while)"):
            reply = api("POST", "/me/coach", timeout=300,
                        json={"question": question, "history": [{"role": t["role"], "content": t["content"]}
                                                                for t in chat]})
        if reply:
            chat += [{"role": "user", "content": question}, {"role": "assistant", "content": reply["answer"]}]
            st.session_state.coach_meta = reply
            st.rerun()

    meta = st.session_state.get("coach_meta")
    if chat and st.button("New conversation", icon=":material/refresh:"):
        chat.clear()
        st.rerun()
    if meta:
        with st.expander("What the coach sees", icon=":material/visibility:"):
            st.caption(f"Model: {meta['model']} · prompt {meta['prompt_version']}. "
                       "No username, age, height, weight or gender is sent.")
            st.json(meta["context"], expanded=False)
    st.caption("The coach can make mistakes. For pain or injuries, see a doctor or physiotherapist.")


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
