import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Configuration centralisée pour tous les environnements"""
    
    # Redis
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    
    # TimescaleDB
    TIMESCALE_HOST = os.getenv('TIMESCALE_HOST', 'localhost')
    TIMESCALE_PORT = int(os.getenv('TIMESCALE_PORT', 5432))
    TIMESCALE_DB = os.getenv('TIMESCALE_DB', 'crypto_db')
    TIMESCALE_USER = os.getenv('TIMESCALE_USER', 'crypto_user')
    TIMESCALE_PASSWORD = os.getenv('TIMESCALE_PASSWORD', 'crypto_pass')
    
    # Binance API
    BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
    BINANCE_SECRET = os.getenv('BINANCE_SECRET', '')

settings = Settings()