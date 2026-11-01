BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('student','admin','worker')),
 demo INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
 csrf TEXT NOT NULL, expires REAL NOT NULL, failures INTEGER NOT NULL DEFAULT 0, blocked_until REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tickets (
 id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id), assignee_id INTEGER REFERENCES users(id),
 title TEXT NOT NULL, location TEXT NOT NULL, original_description TEXT NOT NULL, description TEXT NOT NULL,
 category TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'waiting', version INTEGER NOT NULL DEFAULT 1,
 demo INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
 actor_id INTEGER NOT NULL REFERENCES users(id), action TEXT NOT NULL, before_status TEXT, after_status TEXT NOT NULL,
 note TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS attachments (
 id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
 actor_id INTEGER NOT NULL REFERENCES users(id), filename TEXT NOT NULL, mime TEXT NOT NULL, content BLOB NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS reviews (
 ticket_id INTEGER PRIMARY KEY REFERENCES tickets(id) ON DELETE CASCADE,
 rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), comment TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS idempotency (
 actor_id INTEGER NOT NULL REFERENCES users(id), operation TEXT NOT NULL, key TEXT NOT NULL,
 fingerprint TEXT NOT NULL, response TEXT NOT NULL, expires REAL NOT NULL,
 PRIMARY KEY(actor_id,operation,key)
);
CREATE INDEX IF NOT EXISTS tickets_owner ON tickets(owner_id,created_at DESC,id DESC);
CREATE INDEX IF NOT EXISTS tickets_assignee ON tickets(assignee_id,created_at DESC,id DESC);
PRAGMA user_version=1;
COMMIT;
