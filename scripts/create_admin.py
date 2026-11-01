#!/usr/bin/env python3
"""Create (or promote) an Admin account securely. Admin accounts cannot be self-registered in the app.

    CREATE_ADMIN_PASSWORD='...' python scripts/create_admin.py --email dean@your-college.edu --name "Dean's Office"

The password is read from CREATE_ADMIN_PASSWORD or an interactive prompt (never from the command line history).
Run it against production by setting DATABASE_URL first. Existing accounts are not overwritten.
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.models.db import User, init_db, session_scope  # noqa: E402
from app.services import accounts  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", required=True)
    a = ap.parse_args()
    email = a.email.strip().lower()
    pw = os.environ.get("CREATE_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    for problem in (accounts.email_problem(email), accounts.password_problem(pw)):
        if problem:
            print("error:", problem)
            return 2
    init_db()
    with session_scope() as s:
        if s.get(User, email):
            print("error: an account with this email already exists; nothing changed")
            return 3
        s.add(User(id=email, email=email, name=a.name, role="admin", status="active", password_hash=accounts.hash_password(pw)))
    print(f"admin account created for {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
