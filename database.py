import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    async with db_pool.acquire() as conn:
        # Создаём таблицу, если её нет (только базовые поля)
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
        # Добавляем недостающие колонки (если их нет)
        # guests
        res = await conn.fetchrow("SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='guests'")
        if not res:
            await conn.execute("ALTER TABLE bookings ADD COLUMN guests INTEGER DEFAULT 0 NOT NULL")
        # total_price
        res = await conn.fetchrow("SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='total_price'")
        if not res:
            await conn.execute("ALTER TABLE bookings ADD COLUMN total_price INTEGER DEFAULT 0 NOT NULL")
        # cleaning_fee
        res = await conn.fetchrow("SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='cleaning_fee'")
        if not res:
            await conn.execute("ALTER TABLE bookings ADD COLUMN cleaning_fee INTEGER DEFAULT 0 NOT NULL")
        # extra_guests_fee
        res = await conn.fetchrow("SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='extra_guests_fee'")
        if not res:
            await conn.execute("ALTER TABLE bookings ADD COLUMN extra_guests_fee INTEGER DEFAULT 0 NOT NULL")

        await conn.execute("CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date)")

def time_to_minutes(time_str):
    h, m = map(int, time_str.split(':'))
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

async def add_booking(user_id, name, phone, date, time, hours, guests, total_price, cleaning_fee, extra_guests_fee):
    if await check_overlap(date, time, hours):
        return None
    async with db_pool.acquire() as conn:
        booking_id = await conn.fetchval(
            """
            INSERT INTO bookings 
                (user_id, name, phone, date, time, hours, guests, total_price, cleaning_fee, extra_guests_fee) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
            """,
            user_id, name, phone, date, time, hours, guests, total_price, cleaning_fee, extra_guests_fee
        )

        return booking_id

async def get_user_bookings(user_id: int):
    """Возвращает список броней пользователя, отсортированных по дате и времени"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, date, time, hours, guests, total_price, status
            FROM bookings
            WHERE user_id = $1
            ORDER BY date, time
            """,
            user_id
        )
        return rows

async def close_db():
    if db_pool:
        await db_pool.close()