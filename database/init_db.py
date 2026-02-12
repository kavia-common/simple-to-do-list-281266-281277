#!/usr/bin/env python3
"""Initialize SQLite database for the database container.

This script is designed to be safe for both init and re-init:
- It will create the DB file (if missing)
- It will create required tables if they do not exist
- It will not drop tables or delete user data
- It treats db_connection.txt as the source of truth for DB location
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DB_CONNECTION_FILE = "db_connection.txt"


def _parse_db_path_from_connection_file(connection_file_path: str) -> Path | None:
    """Parse an absolute SQLite DB file path from db_connection.txt.

    The repository's db_connection.txt contains a line like:
    # File path: /abs/path/to/myapp.db

    Returns:
        The parsed Path if found, otherwise None.
    """
    if not os.path.exists(connection_file_path):
        return None

    try:
        with open(connection_file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None

    match = re.search(r"^#\s*File path:\s*(.+)\s*$", content, flags=re.MULTILINE)
    if not match:
        return None

    path_str = match.group(1).strip()
    if not path_str:
        return None

    return Path(path_str)


def _write_connection_file(connection_file_path: str, db_path: Path) -> None:
    """Write db_connection.txt in the expected format."""
    # Keep consistent with existing format.
    connection_string = f"sqlite:///{db_path}"
    with open(connection_file_path, "w", encoding="utf-8") as f:
        f.write("# SQLite connection methods:\n")
        # Keep Python hint simple and local-file oriented
        f.write(f"# Python: sqlite3.connect('{db_path.name}')\n")
        f.write(f"# Connection string: {connection_string}\n")
        f.write(f"# File path: {db_path}\n")


def _ensure_visualizer_env(db_path: Path) -> None:
    """Ensure db_visualizer/sqlite.env exists and points at the DB path."""
    os.makedirs("db_visualizer", exist_ok=True)
    with open("db_visualizer/sqlite.env", "w", encoding="utf-8") as f:
        f.write(f'export SQLITE_DB="{db_path}"\n')


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure required tables exist (idempotent)."""
    cursor = conn.cursor()

    # app_info is kept for compatibility with the existing template.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS app_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # IMPORTANT: Create todos table required by the todo app.
    # Columns per task:
    # - id (INTEGER PK)
    # - title (TEXT, required)
    # - completed (INTEGER/BOOLEAN-like, required, default 0)
    # - created_at, updated_at (timestamps)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Helpful indexes for common access patterns.
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_todos_completed
        ON todos(completed)
        """
    )

    # Keep the template's initial metadata up to date (idempotent).
    cursor.execute(
        "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
        ("project_name", "simple-to-do-list"),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
        ("version", "0.1.0"),
    )

    conn.commit()


def main() -> None:
    """Entry point for database initialization."""
    print("Starting SQLite setup...")

    # db_connection.txt is the source of truth.
    db_path = _parse_db_path_from_connection_file(DB_CONNECTION_FILE)

    # If connection file is missing/unparseable, fall back to local myapp.db
    # and (re)write db_connection.txt to establish the canonical path.
    if db_path is None:
        db_path = Path(os.getcwd()) / "myapp.db"

    # Ensure parent directory exists (should already, but safe).
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db_exists = db_path.exists()
    if db_exists:
        print(f"SQLite database already exists at {db_path}")
    else:
        print(f"Creating new SQLite database at {db_path}...")

    # Connect using the canonical path from db_connection.txt.
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")

        _ensure_schema(conn)

        # Stats
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        table_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM app_info")
        app_info_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM todos")
        todos_count = cursor.fetchone()[0]
    finally:
        conn.close()

    # Persist the source of truth (canonical absolute path).
    _write_connection_file(DB_CONNECTION_FILE, db_path.resolve())
    _ensure_visualizer_env(db_path.resolve())

    print("Connection information saved to db_connection.txt")
    print("Environment variables saved to db_visualizer/sqlite.env")

    print("\nSQLite setup complete!")
    print(f"Database: {db_path.name}")
    print(f"Location: {db_path.resolve()}\n")

    print("Database statistics:")
    print(f"  Tables: {table_count}")
    print(f"  App info records: {app_info_count}")
    print(f"  Todos: {todos_count}")

    print("\nTo use with Node.js viewer, run: source db_visualizer/sqlite.env")
    print("\nScript completed successfully.")


if __name__ == "__main__":
    main()
