import sqlite3
import hashlib
from datetime import datetime

import os
if os.path.exists("pip.db"):
    os.remove("pip.db")

conn = sqlite3.connect("pip.db", check_same_thread=False)
conn.row_factory = sqlite3.Row

def init_db():
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT,
        token TEXT,
        expired_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS siswa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nipd TEXT UNIQUE,
        nama TEXT,

        jenis_tinggal TEXT,
        kepemilikan_rumah TEXT,
        alat_transportasi TEXT,
        kondisi_keluarga TEXT,
        jumlah_tanggungan TEXT,
        pekerjaan_ayah TEXT,
        penghasilan_ayah TEXT,
        pekerjaan_ibu TEXT,
        penghasilan_ibu TEXT,
        penerima_kip TEXT,
        penerima_kps TEXT,

        hasil TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS password_reset (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        token TEXT,
        expired_at TEXT
    )
    """)

    admin = c.execute("SELECT * FROM admin WHERE username='admin'").fetchone()
    if not admin:
        c.execute("""
        INSERT INTO admin (username, password, email)
        VALUES (?,?,?)
        """, (
            "admin",
            hashlib.sha256("admin123".encode()).hexdigest(),
            "rahelsimanjuntak12@gmail.com"
        ))

    conn.commit()

init_db()
