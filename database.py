import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

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
    conn = await asyncpg.connect(DATABASE_URL)

    # Проверка пересечений
    new_start = int(time.split(":")[0])*60 + int(time.split(":")[1])
    new_end = new_start + hours*60

    rows = await conn.fetch("SELECT time, hours FROM bookings WHERE date=$1", date)
    for r in rows:
        exist_start = int(r['time'].split(":")[0])*60 + int(r['time'].split(":")[1])
        exist_end = exist_start + r['hours']*60
        if new_start < exist_end and new_end > exist_start:
            await conn.close()
            return None

    # Добавляем бронь
    booking_id = await conn.fetchval(
        "INSERT INTO bookings(user_id, name, phone, date, time, hours) VALUES($1,$2,$3,$4,$5,$6) RETURNING id",
        user_id, name, phone, date, time, hours
    )

    await conn.close()
    return booking_id