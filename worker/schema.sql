CREATE TABLE IF NOT EXISTS players (
  username  TEXT    NOT NULL,
  year      INTEGER NOT NULL,
  joined_at TEXT    NOT NULL,          -- UTC ISO 8601, server-assigned
  picks     TEXT    NOT NULL,          -- JSON: {"ranked": [10 titles], "dark_horses": [3 titles]}
  PRIMARY KEY (username, year)
);
