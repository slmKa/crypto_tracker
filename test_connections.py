import psycopg2
import redis
from dotenv import load_dotenv
import os

load_dotenv()

# Test TimescaleDB
try:
    conn = psycopg2.connect(
        host=os.getenv("TIMESCALE_DB_HOST"),
        port=int(os.getenv("TIMESCALE_DB_PORT")),
        user=os.getenv("TIMESCALE_DB_USER"),
        password=os.getenv("TIMESCALE_DB_PASSWORD"),
        dbname=os.getenv("TIMESCALE_DB_NAME")
    )
    print("✅ TimescaleDB OK")
    conn.close()
except Exception as e:
    print("❌ TimescaleDB Error:", e)

# Test Redis
try:
    r = redis.Redis(host=os.getenv("REDIS_HOST"), port=int(os.getenv("REDIS_PORT")))
    r.ping()
    print("✅ Redis OK")
except Exception as e:
    print("❌ Redis Error:", e)
