#!/usr/bin/env python3
"""Migration runner for adding owner_user_id to inbox_entries.

Usage:
  python backend/scripts/migrate_inbox_owner.py --db <path-to-db> [--dry-run|--apply]

The script will:
 - verify the DB file exists
 - create a timestamped backup under the same folder (unless --no-backup)
 - check whether the column already exists (and skip if so)
 - in --dry-run mode: show planned SQL and exit
 - in --apply mode: execute the ALTER TABLE statement inside a transaction and verify

This runner is intentionally minimal and safe for local/staging use. For production,
perform an offline backup and test the script on a staging copy first.
"""

import argparse
import datetime
import os
import shutil
import sqlite3
import sys

SQL = "ALTER TABLE inbox_entries ADD COLUMN owner_user_id TEXT NOT NULL DEFAULT 'default';"


def backup_db(db_path: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = f"{db_path}.backup.{ts}"
    print(f"Creating backup: {dest}")
    shutil.copy2(db_path, dest)
    return dest


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    return column in cols


def apply_migration(db_path: str, do_backup: bool = True) -> None:
    if not os.path.exists(db_path):
        print(f"DB file not found: {db_path}")
        sys.exit(2)

    if do_backup:
        backup_db(db_path)

    conn = sqlite3.connect(db_path)
    try:
        if column_exists(conn, 'inbox_entries', 'owner_user_id'):
            print("Column owner_user_id already exists on inbox_entries. Nothing to do.")
            return
        print("Applying ALTER TABLE to add owner_user_id to inbox_entries...")
        conn.execute("BEGIN")
        conn.execute(SQL)
        conn.commit()
        if column_exists(conn, 'inbox_entries', 'owner_user_id'):
            print("Migration applied successfully.")
        else:
            print("Migration failed: column still missing after ALTER TABLE.")
            sys.exit(3)
    except Exception as e:
        print(f"Error during migration: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        sys.exit(4)
    finally:
        conn.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--db', required=True, help='Path to SQLite DB file')
    group = p.add_mutually_exclusive_group()
    group.add_argument('--dry-run', action='store_true', help='Show planned actions without applying')
    group.add_argument('--apply', action='store_true', help='Apply the migration')
    p.add_argument('--no-backup', action='store_true', help='Do not create a backup (use with caution)')

    args = p.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        sys.exit(2)

    conn = sqlite3.connect(db_path)
    if column_exists(conn, 'inbox_entries', 'owner_user_id'):
        print('Column owner_user_id already exists on inbox_entries. Nothing to do.')
        conn.close()
        sys.exit(0)
    conn.close()

    print(f"Planned SQL:\n{SQL}\n")
    if args.dry_run:
        print("Dry run mode — no changes will be made. Create a backup and run with --apply to execute.")
        sys.exit(0)

    if args.apply:
        print("Applying migration...")
        apply_migration(db_path, do_backup=not args.no_backup)
        sys.exit(0)

    print("No action specified. Use --dry-run to preview or --apply to execute the migration.")
    sys.exit(0)
