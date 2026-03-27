import sqlite3


def _connect(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: str = "bot.db") -> None:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        personnel_columns = [
            row[1] for row in cursor.execute("PRAGMA table_info(personnel)")
        ]
        if personnel_columns and "id" not in personnel_columns:
            cursor.execute("ALTER TABLE personnel RENAME TO personnel_old")
            cursor.execute(
                """
                CREATE TABLE personnel (
                    id INTEGER PRIMARY KEY,
                    rank TEXT NOT NULL,
                    name TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO personnel (id, rank, name)
                SELECT rowid, rank, name FROM personnel_old
                """
            )
            cursor.execute("DROP TABLE personnel_old")
        else:
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
                absent_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                FOREIGN KEY (personnel_id) REFERENCES personnel(id) ON DELETE CASCADE,
                UNIQUE (personnel_id, absent_date)
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_absences_date ON absences(absent_date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_absences_personnel_date ON absences(personnel_id, absent_date)"
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


def add_absence(db_path: str, personnel_id: int, absent_date: str, reason: str) -> None:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO absences (personnel_id, absent_date, reason)
            VALUES (?, ?, ?)
            """,
            (personnel_id, absent_date, reason),
        )
        connection.commit()


def list_absences_for_date(db_path: str, absent_date: str) -> dict[int, str]:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        rows = cursor.execute(
            "SELECT personnel_id, reason FROM absences WHERE absent_date = ?",
            (absent_date,),
        )
        return {row[0]: row[1] for row in rows.fetchall()}


def remove_absence(db_path: str, personnel_id: int, absent_date: str) -> bool:
    with _connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM absences WHERE personnel_id = ? AND absent_date = ?",
            (personnel_id, absent_date),
        )
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
