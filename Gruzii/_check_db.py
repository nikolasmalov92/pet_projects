import sqlite3
conn = sqlite3.connect("database.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([r[0] for r in c.fetchall()])
c.execute("PRAGMA table_info(FilterPresets)")
print("FilterPresets columns:", [r[1] for r in c.fetchall()])
conn.close()
