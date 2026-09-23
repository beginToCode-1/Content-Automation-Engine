-- Adds 'cancelled' as a valid runs.status value, for mid-run cancellation.
-- schema.sql's inline CHECK already includes it for fresh databases; this
-- migration brings an existing database's runs table up to the same shape.
ALTER TABLE runs DROP CONSTRAINT IF EXISTS runs_status_check;
ALTER TABLE runs ADD CONSTRAINT runs_status_check
    CHECK (status IN ('pending','running','succeeded','failed','cancelled'));
