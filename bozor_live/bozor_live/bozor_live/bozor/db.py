"""SQLite connection and non-destructive schema initialization.

Legacy tables and columns intentionally stay unchanged so an existing bozor.db
can be used without destructive migrations. Back up the database before deploys.
"""
import sqlite3
from flask import current_app, g

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS listings (
  id INTEGER PRIMARY KEY,
  owner_id INTEGER NOT NULL REFERENCES users(id),
  title TEXT NOT NULL,
  category TEXT NOT NULL,
  city TEXT NOT NULL,
  price INTEGER NOT NULL,
  description TEXT NOT NULL,
  photo TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS favorites (
  user_id INTEGER REFERENCES users(id),
  listing_id INTEGER REFERENCES listings(id) ON DELETE CASCADE,
  PRIMARY KEY(user_id,listing_id)
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY,
  listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  sender_id INTEGER NOT NULL REFERENCES users(id),
  recipient_id INTEGER NOT NULL REFERENCES users(id),
  body TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS car_details (
  listing_id INTEGER PRIMARY KEY REFERENCES listings(id) ON DELETE CASCADE,
  brand TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',
  year INTEGER, mileage INTEGER, transmission TEXT NOT NULL DEFAULT '',
  fuel TEXT NOT NULL DEFAULT '', drive TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '', engine TEXT NOT NULL DEFAULT '',
  color TEXT NOT NULL DEFAULT '', steering TEXT NOT NULL DEFAULT '',
  car_condition TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS listing_photos (
  id INTEGER PRIMARY KEY,
  listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  url TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_car_brand_model ON car_details(brand,model,year);
CREATE INDEX IF NOT EXISTS idx_listing_photos ON listing_photos(listing_id,position);
CREATE INDEX IF NOT EXISTS idx_listings_created ON listings(id DESC);
CREATE INDEX IF NOT EXISTS idx_listings_category_city ON listings(category,city);
CREATE INDEX IF NOT EXISTS idx_listings_owner ON listings(owner_id);
CREATE INDEX IF NOT EXISTS idx_messages_listing ON messages(listing_id,id);
CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id,id);
'''


def get_db():
    if 'db' not in g:
        conn = sqlite3.connect(current_app.config['DATABASE_PATH'], timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA busy_timeout = 20000')
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop('db', None)
    if conn is not None:
        conn.close()


def init_db():
    get_db().executescript(SCHEMA)
    get_db().commit()
