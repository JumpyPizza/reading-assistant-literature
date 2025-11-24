"""
Quick inspection utility for the parsing SQLite DB.

Usage:
    python tests/inspect_db.py --db data/reading_assistant.db --limit 5

Prefers pandas for nice tabular output; falls back to sqlite3-only if pandas
isn't installed.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import List, Tuple


def quote_ident(identifier: str) -> str:
    """Escape a SQLite identifier using double quotes."""
    return '"' + identifier.replace('"', '""') + '"'


def list_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def get_count(conn: sqlite3.Connection, table: str) -> int:
    table_sql = quote_ident(table)
    row = conn.execute(f"SELECT COUNT(*) FROM {table_sql}").fetchone()
    return int(row[0]) if row else 0


def get_columns(conn: sqlite3.Connection, table: str) -> List[Tuple[str, str]]:
    """Return (name, type) for each column in the given table."""
    table_sql = quote_ident(table)
    rows = conn.execute(f"PRAGMA table_info({table_sql})").fetchall()
    return [(r[1], r[2]) for r in rows]


def preview_table_with_pandas(conn: sqlite3.Connection, table: str, limit: int) -> str:
    import pandas as pd  # type: ignore

    table_sql = quote_ident(table)
    df = pd.read_sql_query(f"SELECT * FROM {table_sql} LIMIT {limit}", conn)
    return df.to_string(index=False)


def preview_table_basic(conn: sqlite3.Connection, table: str, limit: int) -> str:
    table_sql = quote_ident(table)
    cursor = conn.execute(f"SELECT * FROM {table_sql} LIMIT {limit}")
    cols = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    lines = [" | ".join(cols)]
    for row in rows:
        lines.append(" | ".join(str(v) for v in row))
    return "\n".join(lines)


def inspect_db(db_path: Path, limit: int = 5) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found at {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        tables = list_tables(conn)
        if not tables:
            print("No tables found.")
            return
        print(f"Found tables: {', '.join(tables)}\n")

        try:
            import pandas as pd  # noqa: F401

            use_pandas = True
        except Exception:
            use_pandas = False

        for table in tables:
            count = get_count(conn, table)
            print(f"Table '{table}' (rows: {count})")
            columns = get_columns(conn, table)
            if columns:
                columns_desc = ", ".join(
                    f"{name} ({col_type})" if col_type else name for name, col_type in columns
                )
            else:
                columns_desc = "No columns found"
            print(f"Columns: {columns_desc}")
            if count > 0:
                preview = (
                    preview_table_with_pandas(conn, table, limit)
                    if use_pandas
                    else preview_table_basic(conn, table, limit)
                )
                print(preview)
            print("-" * 40)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect parsing SQLite DB")
    parser.add_argument("--db", type=Path, default=Path("data/reading_assistant.db"), help="Path to SQLite DB")
    parser.add_argument("--limit", type=int, default=5, help="Rows to preview per table")
    args = parser.parse_args()
    inspect_db(args.db, limit=args.limit)


if __name__ == "__main__":
    main()
