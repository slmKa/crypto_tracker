# Dans un script Python
with open(".env", "w", encoding="utf-8") as f:
    f.write(
"""TIMESCALE_DB_HOST=localhost
TIMESCALE_DB_PORT=5432
TIMESCALE_DB_USER=crypto_user
TIMESCALE_DB_PASSWORD=crypto_pass
TIMESCALE_DB_NAME=crypto_db
REDIS_HOST=localhost
REDIS_PORT=6379
"""
    )
