-- Records which run a failed/cancelled run was retried as. The retry route
-- claims a run by setting this from NULL in one UPDATE, so a double-click or
-- a second tab can't start two retries of the same run. Nullable and additive.
ALTER TABLE runs ADD COLUMN IF NOT EXISTS retried_as TEXT;
