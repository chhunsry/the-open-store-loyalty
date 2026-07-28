import argparse
import getpass

from app.auth import hash_password
from app.database import connect, init_db


def main():
    parser = argparse.ArgumentParser(description="Create or reset a store admin.")
    parser.add_argument("username")
    args = parser.parse_args()
    password = getpass.getpass("New password (minimum 10 characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match.")
    init_db()
    hashed = hash_password(password)
    with connect() as db:
        existing = db.execute(
            "SELECT id FROM admins WHERE username = ?", (args.username,)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE admins SET password_hash = ? WHERE id = ?",
                (hashed, existing["id"]),
            )
            print("Admin password updated.")
        else:
            db.execute(
                "INSERT INTO admins(username, password_hash) VALUES (?, ?)",
                (args.username, hashed),
            )
            print("Admin created.")


if __name__ == "__main__":
    main()

