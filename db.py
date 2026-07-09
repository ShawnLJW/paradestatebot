import sqlite3
from datetime import date, timedelta


def _connect(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: str = "bot.db") -> None:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS personnel (
                id INTEGER PRIMARY KEY,
                rank TEXT NOT NULL,
                name TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                chat_id INTEGER PRIMARY KEY
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS absences (
                id INTEGER PRIMARY KEY,
                personnel_id INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                FOREIGN KEY (personnel_id) REFERENCES personnel(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_absences_dates ON absences(start_date, end_date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_absences_personnel ON absences(personnel_id, end_date)"
        )
        connection.commit()


def add_personnel(db_path: str, rank: str, name: str) -> None:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO personnel (rank, name) VALUES (?, ?)",
            (rank, name),
        )
        connection.commit()


def remove_personnel(db_path: str, rank: str, name: str) -> bool:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM personnel WHERE rank = ? AND name = ?",
            (rank, name),
        )
        connection.commit()
        return cursor.rowcount > 0


def list_personnel(db_path: str) -> list[tuple[int, str, str]]:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        rows = cursor.execute("SELECT id, rank, name FROM personnel ORDER BY id")
        return [(row[0], row[1], row[2]) for row in rows.fetchall()]


def get_personnel_id(db_path: str, rank: str, name: str) -> int | None:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        row = cursor.execute(
            "SELECT id FROM personnel WHERE rank = ? AND name = ?",
            (rank, name),
        ).fetchone()
        return None if row is None else row[0]


def add_absence(
    db_path: str, personnel_id: int, start_date: str, end_date: str, reason: str
) -> None:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        # Fetch ranges that overlap the new one, plus adjacent ones so
        # same-reason neighbours can be merged into a single row.
        rows = cursor.execute(
            """
            SELECT id, start_date, end_date, reason FROM absences
            WHERE personnel_id = ? AND start_date <= ? AND end_date >= ?
            """,
            (
                personnel_id,
                (end + timedelta(days=1)).isoformat(),
                (start - timedelta(days=1)).isoformat(),
            ),
        ).fetchall()

        new_start, new_end = start, end
        for row_id, row_start_text, row_end_text, row_reason in rows:
            row_start = date.fromisoformat(row_start_text)
            row_end = date.fromisoformat(row_end_text)
            if row_reason == reason:
                cursor.execute("DELETE FROM absences WHERE id = ?", (row_id,))
                new_start = min(new_start, row_start)
                new_end = max(new_end, row_end)
            elif row_start <= end and row_end >= start:
                # The new absence overrides the overlapping days; keep any
                # part of the old range that sticks out on either side.
                cursor.execute("DELETE FROM absences WHERE id = ?", (row_id,))
                if row_start < start:
                    cursor.execute(
                        """
                        INSERT INTO absences (personnel_id, start_date, end_date, reason)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            personnel_id,
                            row_start.isoformat(),
                            (start - timedelta(days=1)).isoformat(),
                            row_reason,
                        ),
                    )
                if row_end > end:
                    cursor.execute(
                        """
                        INSERT INTO absences (personnel_id, start_date, end_date, reason)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            personnel_id,
                            (end + timedelta(days=1)).isoformat(),
                            row_end.isoformat(),
                            row_reason,
                        ),
                    )
        cursor.execute(
            """
            INSERT INTO absences (personnel_id, start_date, end_date, reason)
            VALUES (?, ?, ?, ?)
            """,
            (personnel_id, new_start.isoformat(), new_end.isoformat(), reason),
        )
        connection.commit()


def list_absences_for_date(
    db_path: str, absent_date: str
) -> dict[int, tuple[str, str, str]]:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        rows = cursor.execute(
            """
            SELECT personnel_id, reason, start_date, end_date FROM absences
            WHERE start_date <= ? AND end_date >= ?
            """,
            (absent_date, absent_date),
        )
        return {row[0]: (row[1], row[2], row[3]) for row in rows.fetchall()}


def list_absences_for_personnel(
    db_path: str, personnel_id: int, from_date: str
) -> list[tuple[int, str, str, str]]:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        rows = cursor.execute(
            """
            SELECT id, start_date, end_date, reason FROM absences
            WHERE personnel_id = ? AND end_date >= ?
            ORDER BY start_date
            """,
            (personnel_id, from_date),
        )
        return [(row[0], row[1], row[2], row[3]) for row in rows.fetchall()]


def remove_absence(db_path: str, absence_id: int) -> bool:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM absences WHERE id = ?", (absence_id,))
        connection.commit()
        return cursor.rowcount > 0


def save_job(db_path: str, chat_id: int) -> None:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO jobs (chat_id) VALUES (?)",
            (chat_id,),
        )
        connection.commit()


def list_job_chat_ids(db_path: str) -> list[int]:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        rows = cursor.execute("SELECT chat_id FROM jobs")
        return [row[0] for row in rows.fetchall()]
