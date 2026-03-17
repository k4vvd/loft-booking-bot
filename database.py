import os
import asyncpg
from datetime import datetime

DATABASE_URL = os.getenv("postgresql://postgres:38N.f9612312@db.ctmomcrdvrtyhzslxnih.supabase.co:5432/postgres")  # PostgreSQL URL

# Конвертируем время "HH:MM" в минуты
def time_to_minutes(time_str):
    h, m = map(int, time_str.split(":"))
    return h * 60 + m

async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        name TEXT,
        phone TEXT,
        date TEXT,
        time TEXT,
        hours INT,
        status TEXT DEFAULT 'new',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    await conn.close()

async def add_booking(user_id, name, phone, date, time, hours):
    if await check_overlap(date, time, hours):
        return None  # пересечение есть

    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow(
        """
        INSERT INTO bookings (user_id, name, phone, date, time, hours)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        user_id, name, phone, date, time, hours
    )
    await conn.close()
    return row["id"]

async def check_overlap(date, time, hours):
    new_start = time_to_minutes(time)
    new_end = new_start + hours * 60

    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT time, hours FROM bookings WHERE date=$1",
        date
    )
    await conn.close()

    for existing_time, existing_hours in rows:
        exist_start = time_to_minutes(existing_time)
        exist_end = exist_start + existing_hours * 60
        if new_start < exist_end and new_end > exist_start:
            return True  # пересечение есть
    return False  # пересечений нет