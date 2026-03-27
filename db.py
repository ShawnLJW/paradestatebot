import sqlite3


def init_db(db_path: str = "bot.db") -> None:
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS personnel (
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


def add_personnel(db_path: str, rank: str, name: str) -> None:
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO personnel (rank, name) VALUES (?, ?)",
            (rank, name),
        )
        connection.commit()


def list_personnel(db_path: str) -> list[tuple[str, str]]:
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        rows = cursor.execute("SELECT rank, name FROM personnel")
        return [(row[0], row[1]) for row in rows.fetchall()]


def save_job(db_path: str, chat_id: int) -> None:
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO jobs (chat_id) VALUES (?)",
            (chat_id,),
        )
        connection.commit()


def list_job_chat_ids(db_path: str) -> list[int]:
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        rows = cursor.execute("SELECT chat_id FROM jobs")
        return [row[0] for row in rows.fetchall()]
