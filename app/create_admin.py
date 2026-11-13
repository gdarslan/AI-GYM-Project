"""Create the first admin, or make an existing account admin. Run from the project root:

    python -m app.create_admin

There is deliberately no way to become admin through the website: the first admin is made here, on the
computer that runs the app. After that, admins can promote other users on the Admin page.
"""
import getpass
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app import security
from app.db import AuditLog, User, init_db, make_engine
from app.main import now
from app.schemas import USERNAME_PATTERN


def main() -> int:
    engine = make_engine()
    init_db(engine)
    with sessionmaker(engine)() as s:
        username = input("Username of the admin: ").strip()
        user = s.scalar(select(User).where(func.lower(User.username) == username.lower()))
        if user:
            if user.role == "admin":
                print(f"{user.username} is already an admin.")
                return 0
            user.role = "admin"
            print(f"{user.username} is now an admin.")
        else:
            import re
            if not re.fullmatch(USERNAME_PATTERN, username):
                print("Use 3-30 letters, digits, '.', '_' or '-'.")
                return 1
            password = getpass.getpass("New password (not shown): ")
            if getpass.getpass("Repeat password: ") != password:
                print("The passwords do not match.")
                return 1
            problem = security.password_problem(password, username)
            if problem:
                print(problem)
                return 1
            # an admin-only account: no training profile and no consent, so it cannot log workouts
            user = User(username=username, password_hash=security.hash_password(password), role="admin")
            s.add(user)
            print(f"Admin account {username} created.")
        s.add(AuditLog(time=now(), actor="command line", action="set_role_admin", target=user.username))
        s.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
