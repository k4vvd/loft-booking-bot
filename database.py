import asyncpg
import os

# Railway автоматически подставит DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                hours INTEGER NOT NULL,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Индекс для быстрого поиска по дате
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date)")

def time_to_minutes(time_str):
    h, m = map(int, time_str.split(":"))
    return h * 60 + m

async def check_overlap(date: str, time: str, hours: int) -> bool:
    new_start = time_to_minutes(time)
    new_end = new_start + hours * 60
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT time, hours FROM bookings WHERE date = $1", date)
        for row in rows:
            exist_start = time_to_minutes(row['time'])
            exist_end = exist_start + row['hours'] * 60
            if new_start < exist_end and new_end > exist_start:
                return True
    return False

async def add_booking(user_id, name, phone, date, time, hours):
    if await check_overlap(date, time, hours):
        return None
    async with db_pool.acquire() as conn:
        booking_id = await conn.fetchval(
            "INSERT INTO bookings (user_id, name, phone, date, time, hours) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
            user_id, name, phone, date, time, hours
        )
        return booking_id

async def close_db():
    if db_pool:
        await db_pool.close()