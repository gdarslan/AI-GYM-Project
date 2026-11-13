"""Gym Coach API. Run from the project root:  python -m uvicorn app.main:app --reload

Interactive docs: http://localhost:8000/docs
Every endpoint except /health, /exercises, /auth/register, /auth/login and /auth/demo needs a login token
("Authorization: Bearer <token>").
Users only ever reach their own data through /me/...; admins manage accounts but cannot see training data.
"""
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app import security
from app.db import (DB_URL, EXERCISES_CSV, AuditLog, AuthSession, Exercise, User, Workout, WorkoutSet, init_db,
                    make_engine)
from app.schemas import (CONSENT_VERSION, AccountOut, AuditOut, CoachIn, CoachOut, ConsentIn, ExerciseOut, LoginIn,
                         MeOut, PasswordChangeIn, PasswordConfirmIn, ProfileIn, RegisterIn, RoleIn, SetOut, TokenOut,
                         WorkoutIn, WorkoutOut)
from src import coach
from src.calories import estimate_kcal
from src.personas import legs_neglected
from src.progress import exercise_history, new_records, progress_summary

LOG_COLUMNS = ["date", "exercise", "reps", "weight_kg"]
SESSION_HOURS = 8
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)      # stored as naive UTC


def create_app(db_url: str = DB_URL, exercises_csv: Path = EXERCISES_CSV, llm: coach.LLMClient | None = None,
               coach_log: Path | None = coach.LOG_FILE) -> FastAPI:
    engine = make_engine(db_url)

    @asynccontextmanager
    async def lifespan(_):
        init_db(engine, exercises_csv)     # tables + exercise library, on startup
        yield

    api = FastAPI(title="AI Gym Coach", lifespan=lifespan)
    api.state.Session = sessionmaker(engine)
    api.state.llm = llm or coach.OllamaClient()
    api.state.coach_log = coach_log
    add_routes(api)
    return api


# ---------------- dependencies ----------------
def get_session(request: Request):
    with request.app.state.Session() as s:
        yield s


bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                 s: Session = Depends(get_session)) -> User:
    if creds is None:
        raise HTTPException(401, "Please log in.")
    session = s.scalar(select(AuthSession).where(AuthSession.token_hash == security.token_hash(creds.credentials)))
    if session is None or session.expires_at < now():
        if session is not None:
            s.delete(session)
            s.commit()
        raise HTTPException(401, "Your session has expired. Please log in again.")
    return session.user


def current_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admins only.")
    return user


def require_profile(user: User) -> None:
    if user.consent_health_at is None:
        raise HTTPException(403, "Consent to process your training data is needed for this.")
    if not user.has_profile:
        raise HTTPException(409, "Complete your training profile first.")


# ---------------- helpers ----------------
def audit(s: Session, actor: str, action: str, target: str = "") -> None:
    s.add(AuditLog(time=now(), actor=actor, action=action, target=target))


def start_session(s: Session, user: User) -> TokenOut:
    token = security.new_token()
    expires = now() + timedelta(hours=SESSION_HOURS)
    s.add(AuthSession(user=user, token_hash=security.token_hash(token), created_at=now(), expires_at=expires))
    user.last_login_at = now()
    s.commit()
    return TokenOut(token=token, expires_at=expires, user=MeOut.model_validate(user))


def check_new_password(password: str, username: str) -> None:
    problem = security.password_problem(password, username)
    if problem:
        raise HTTPException(422, problem)


def admin_count(s: Session) -> int:
    return s.scalar(select(func.count()).select_from(User).where(User.role == "admin"))


def delete_account(s: Session, user: User) -> None:
    """Right to erasure: the account, its sessions, workouts and sets."""
    if user.role == "admin" and admin_count(s) == 1:
        raise HTTPException(409, "This is the last admin account. Make another user admin first.")
    s.delete(user)


def account_out(user: User, workouts: int) -> AccountOut:
    return AccountOut(id=user.id, username=user.username, role=user.role, is_demo=user.is_demo,
                      created_at=user.created_at, last_login_at=user.last_login_at,
                      locked=bool(user.locked_until and user.locked_until > now()), workouts=workouts)


def workout_out(w: Workout, records: list[str] | None = None) -> WorkoutOut:
    kcal = estimate_kcal(w.user.weight_kg, w.duration_min, w.rpe) if w.user.weight_kg else None
    return WorkoutOut(id=w.id, date=w.date, duration_min=w.duration_min, rpe=w.rpe,
                      sets=[SetOut(exercise_id=st.exercise_id, exercise=st.exercise.name, set_number=st.set_number,
                                   reps=st.reps, weight_kg=st.weight_kg) for st in w.sets],
                      total_volume_kg=sum(st.reps * st.weight_kg for st in w.sets),
                      estimated_kcal=kcal, new_records=records or [])


def set_rows(workouts) -> pd.DataFrame:
    """One row per set, the input format of src/progress.py."""
    return pd.DataFrame([{"date": w.date, "exercise": st.exercise.name, "reps": st.reps, "weight_kg": st.weight_kg}
                         for w in workouts for st in w.sets], columns=LOG_COLUMNS)


def user_progress(s: Session, user: User, today: date | None = None, weeks: int = 4) -> dict:
    log = set_rows(user.workouts)
    exercises = pd.DataFrame(
        [(e.name, e.primary_muscles, e.secondary_muscles)
         for e in s.scalars(select(Exercise).where(Exercise.name.in_(set(log["exercise"]))))],
        columns=["name", "primary_muscles", "secondary_muscles"])
    return progress_summary(log, exercises, today or date.today(), weeks)


def add_workout(s: Session, user: User, data: WorkoutIn) -> Workout:
    ids = {st.exercise_id for st in data.sets}
    known = set(s.scalars(select(Exercise.id).where(Exercise.id.in_(ids))))
    if ids - known:
        raise HTTPException(422, f"Unknown exercise ids: {sorted(ids - known)}")
    workout = Workout(user=user, date=data.date, duration_min=data.duration_min, rpe=data.rpe,
                      sets=[WorkoutSet(exercise_id=st.exercise_id, set_number=i + 1, reps=st.reps,
                                       weight_kg=st.weight_kg) for i, st in enumerate(data.sets)])
    s.add(workout)
    return workout


# ---------------- routes ----------------
def add_routes(api: FastAPI) -> None:
    @api.get("/health")
    def health():
        return {"status": "ok"}

    @api.get("/exercises", response_model=list[ExerciseOut])
    def search_exercises(search: str = Query("", max_length=100), limit: int = Query(20, ge=1, le=100),
                         s: Session = Depends(get_session)):
        q = select(Exercise).order_by(Exercise.name).limit(limit)
        for word in search.lower().split():
            q = q.where(or_(Exercise.name.contains(word), Exercise.primary_muscles.contains(word)))
        return s.scalars(q).all()

    # ---- authentication ----
    @api.post("/auth/register", response_model=TokenOut, status_code=201)
    def register(data: RegisterIn, s: Session = Depends(get_session)):
        if not data.consent_health_data:
            raise HTTPException(422, "You must agree to the processing of your training data to use the app.")
        check_new_password(data.password, data.username)
        if s.scalar(select(User).where(func.lower(User.username) == data.username.lower())):
            raise HTTPException(409, "This username is taken.")
        profile = ProfileIn.model_validate(data.model_dump()).model_dump()
        user = User(username=data.username, password_hash=security.hash_password(data.password), role="user",
                    consent_health_at=now(), consent_ai_coach=data.consent_ai_coach,
                    consent_version=CONSENT_VERSION, **profile)
        s.add(user)
        audit(s, data.username, "account_created")
        return start_session(s, user)

    @api.post("/auth/login", response_model=TokenOut)
    def login(data: LoginIn, s: Session = Depends(get_session)):
        user = s.scalar(select(User).where(func.lower(User.username) == data.username.lower()))
        if user and user.locked_until and user.locked_until > now():
            raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
        # a missing username is checked against a dummy hash, so it takes as long as a wrong password
        password_ok = security.verify_password(data.password, user.password_hash if user else security.DUMMY_HASH)
        if user is None or not password_ok:
            if user:
                user.failed_logins += 1
                if user.failed_logins >= MAX_FAILED_LOGINS:
                    user.locked_until = now() + timedelta(minutes=LOCK_MINUTES)
                    user.failed_logins = 0
                    audit(s, user.username, "account_locked")
                s.commit()
            raise HTTPException(401, "Wrong username or password.")
        user.failed_logins, user.locked_until = 0, None
        s.execute(AuthSession.__table__.delete().where(AuthSession.expires_at < now()))   # tidy up old sessions
        return start_session(s, user)

    @api.post("/auth/demo", response_model=TokenOut, status_code=201)
    def demo_login(s: Session = Depends(get_session)):
        """A throwaway account with 4 weeks of made-up training (src/personas.py). Deleted at logout."""
        persona = legs_neglected()
        user = User(username=f"demo-{secrets.token_hex(3)}", password_hash=security.hash_password(security.new_token()),
                    is_demo=True, consent_health_at=now(), consent_ai_coach=True, consent_version=CONSENT_VERSION,
                    **persona["profile"])
        s.add(user)
        names = {st["exercise"] for w in persona["workouts"] for st in w["sets"]}
        ids = {e.name: e.id for e in s.scalars(select(Exercise).where(Exercise.name.in_(names)))}
        for w in persona["workouts"]:
            add_workout(s, user, WorkoutIn(
                date=w["date"], duration_min=w["duration_min"], rpe=w["rpe"],
                sets=[{"exercise_id": ids[st["exercise"]], "reps": st["reps"], "weight_kg": st["weight_kg"]}
                      for st in w["sets"]]))
        return start_session(s, user)

    @api.post("/auth/logout", status_code=204)
    def logout(creds: HTTPAuthorizationCredentials | None = Depends(bearer), user: User = Depends(current_user),
               s: Session = Depends(get_session)):
        if user.is_demo:
            s.delete(user)                       # demo accounts leave nothing behind
        else:
            s.execute(AuthSession.__table__.delete().where(
                AuthSession.token_hash == security.token_hash(creds.credentials)))
        s.commit()

    # ---- my account ----
    @api.get("/me", response_model=MeOut)
    def me(user: User = Depends(current_user)):
        return user

    @api.put("/me", response_model=MeOut)
    def update_profile(data: ProfileIn, user: User = Depends(current_user), s: Session = Depends(get_session)):
        if user.consent_health_at is None:
            raise HTTPException(403, "Consent to process your training data is needed for this.")
        for field, value in data.model_dump().items():
            setattr(user, field, value)
        s.commit()
        return user

    @api.put("/me/password", status_code=204)
    def change_password(data: PasswordChangeIn, creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                        user: User = Depends(current_user), s: Session = Depends(get_session)):
        if not security.verify_password(data.current_password, user.password_hash):
            raise HTTPException(403, "Your current password is wrong.")
        check_new_password(data.new_password, user.username)
        user.password_hash = security.hash_password(data.new_password)
        # sign out every other session, e.g. a forgotten login on another computer
        s.execute(AuthSession.__table__.delete().where(
            AuthSession.user_id == user.id, AuthSession.token_hash != security.token_hash(creds.credentials)))
        audit(s, user.username, "password_changed")
        s.commit()

    @api.put("/me/consent", response_model=MeOut)
    def change_consent(data: ConsentIn, user: User = Depends(current_user), s: Session = Depends(get_session)):
        user.consent_ai_coach = data.ai_coach
        audit(s, user.username, "ai_coach_consent_" + ("given" if data.ai_coach else "withdrawn"))
        s.commit()
        return user

    @api.get("/me/export")
    def export_me(user: User = Depends(current_user)):
        """Right of access / data portability: everything stored about you, as JSON. No password hash."""
        return {"exported_at": now().isoformat(timespec="seconds") + "Z",
                "account": MeOut.model_validate(user).model_dump(mode="json"),
                "workouts": [workout_out(w).model_dump(mode="json", exclude={"new_records"})
                             for w in sorted(user.workouts, key=lambda w: w.date)]}

    @api.post("/me/delete", status_code=204)
    def delete_me(data: PasswordConfirmIn, user: User = Depends(current_user), s: Session = Depends(get_session)):
        """Right to erasure. The password is asked again so nobody can do this from an unlocked screen."""
        if not security.verify_password(data.password, user.password_hash):
            raise HTTPException(403, "Wrong password.")
        delete_account(s, user)
        audit(s, user.username, "account_deleted_by_user")
        s.commit()

    # ---- my workouts ----
    @api.post("/me/workouts", response_model=WorkoutOut, status_code=201)
    def log_workout(data: WorkoutIn, user: User = Depends(current_user), s: Session = Depends(get_session)):
        require_profile(user)
        earlier = set_rows([w for w in user.workouts if w.date < data.date])
        workout = add_workout(s, user, data)
        s.commit()
        return workout_out(workout, new_records(earlier, set_rows([workout])))

    @api.get("/me/workouts", response_model=list[WorkoutOut])
    def list_workouts(user: User = Depends(current_user)):
        return [workout_out(w) for w in sorted(user.workouts, key=lambda w: w.date, reverse=True)]

    @api.delete("/me/workouts/{workout_id}", status_code=204)
    def delete_workout(workout_id: int, user: User = Depends(current_user), s: Session = Depends(get_session)):
        workout = s.get(Workout, workout_id)
        if workout is None or workout.user_id != user.id:      # someone else's workout looks the same as none
            raise HTTPException(404, "Workout not found")
        s.delete(workout)
        s.commit()

    # ---- my progress ----
    @api.get("/me/progress")
    def progress(today: date | None = None, weeks: int = Query(4, ge=1, le=52), user: User = Depends(current_user),
                 s: Session = Depends(get_session)):
        return user_progress(s, user, today, weeks)

    @api.get("/me/exercise-history/{exercise_id}")
    def history_of_exercise(exercise_id: str, user: User = Depends(current_user), s: Session = Depends(get_session)):
        """Every session of one exercise, oldest first: sets, best estimated 1RM and volume."""
        exercise = s.get(Exercise, exercise_id)
        if exercise is None:
            raise HTTPException(404, "Exercise not found")
        return exercise_history(set_rows(user.workouts), exercise.name)

    # ---- AI coach ----
    @api.post("/me/coach", response_model=CoachOut)
    def ask_coach(data: CoachIn, request: Request, user: User = Depends(current_user),
                  s: Session = Depends(get_session)):
        """The code calculates the progress; the language model explains it. No personal details are sent."""
        require_profile(user)
        if not user.consent_ai_coach:
            raise HTTPException(403, "You have not agreed to use the AI coach. You can switch it on under Privacy.")
        context = coach.build_context(user.goal, user.experience, user_progress(s, user))
        llm = request.app.state.llm
        try:
            answer = coach.ask(data.question, context, llm, [t.model_dump() for t in data.history],
                               log_file=request.app.state.coach_log)
        except coach.CoachUnavailable as e:
            raise HTTPException(503, str(e))
        return CoachOut(answer=answer, model=llm.model, prompt_version=coach.PROMPT_VERSION, context=context)

    # ---- admin: accounts only, never training data ----
    def target_user(s: Session, user_id: int) -> User:
        user = s.get(User, user_id)
        if user is None:
            raise HTTPException(404, "Account not found")
        return user

    def workout_counts(s: Session) -> dict:
        return dict(s.execute(select(Workout.user_id, func.count()).group_by(Workout.user_id)).all())

    @api.get("/admin/users", response_model=list[AccountOut])
    def admin_users(admin: User = Depends(current_admin), s: Session = Depends(get_session)):
        counts = workout_counts(s)
        return [account_out(u, counts.get(u.id, 0)) for u in s.scalars(select(User).order_by(User.id))]

    @api.get("/admin/stats")
    def admin_stats(admin: User = Depends(current_admin), s: Session = Depends(get_session)):
        def count(model, *where):
            return s.scalar(select(func.count()).select_from(model).where(*where))
        return {"accounts": count(User), "admins": count(User, User.role == "admin"),
                "demo_accounts": count(User, User.is_demo), "workouts": count(Workout),
                "active_sessions": count(AuthSession, AuthSession.expires_at > now())}

    @api.put("/admin/users/{user_id}/role", response_model=AccountOut)
    def admin_set_role(user_id: int, data: RoleIn, admin: User = Depends(current_admin),
                       s: Session = Depends(get_session)):
        user = target_user(s, user_id)
        if user.role == "admin" and data.role != "admin" and admin_count(s) == 1:
            raise HTTPException(409, "There must always be at least one admin.")
        user.role = data.role
        audit(s, admin.username, f"set_role_{data.role}", user.username)
        s.commit()
        return account_out(user, workout_counts(s).get(user.id, 0))

    @api.post("/admin/users/{user_id}/unlock", status_code=204)
    def admin_unlock(user_id: int, admin: User = Depends(current_admin), s: Session = Depends(get_session)):
        user = target_user(s, user_id)
        user.locked_until, user.failed_logins = None, 0
        audit(s, admin.username, "unlock", user.username)
        s.commit()

    @api.delete("/admin/users/{user_id}", status_code=204)
    def admin_delete(user_id: int, admin: User = Depends(current_admin), s: Session = Depends(get_session)):
        user = target_user(s, user_id)
        if user.id == admin.id:
            raise HTTPException(409, "Delete your own account from the Privacy page.")
        delete_account(s, user)
        audit(s, admin.username, "delete_account", user.username)
        s.commit()

    @api.get("/admin/audit", response_model=list[AuditOut])
    def admin_audit(limit: int = Query(100, ge=1, le=500), admin: User = Depends(current_admin),
                    s: Session = Depends(get_session)):
        return s.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()


app = create_app()
