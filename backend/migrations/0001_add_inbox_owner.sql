-- 0001_add_inbox_owner.sql
-- Safe migration to add owner_user_id to inbox_entries (and verify existence).
-- Instructions:
-- 1. Backup your DB (the runner script does this automatically):
--    python backend/scripts/migrate_inbox_owner.py --db ./data/memory/studyagent.db --dry-run
-- 2. Review the dry-run output. If okay, run with --apply to perform the change.
--
-- This SQL is intentionally simple and idempotent. It will add the column with a default
-- value 'default' so legacy rows remain accessible as public notifications.

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- Add column if not exists (SQLite: adding a column twice will error; the runner checks first)
ALTER TABLE inbox_entries ADD COLUMN owner_user_id TEXT NOT NULL DEFAULT 'default';

COMMIT;
PRAGMA foreign_keys = ON;

-- After applying, consider running:
-- SELECT COUNT(*) FROM inbox_entries WHERE owner_user_id = 'default';
-- to estimate how many notifications are public and whether a backfill is needed.
