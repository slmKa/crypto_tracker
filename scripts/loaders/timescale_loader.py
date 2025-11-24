"""
Loader pour TimescaleDB (stockage long terme)
"""
import psycopg2
from psycopg2.extras import execute_batch
from typing import Dict, List
import pandas as pd
from loguru import logger
from contextlib import contextmanager
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

class TimescaleLoader:
    """
    Gestionnaire de connexion et insertion dans TimescaleDB
    TimescaleDB = Extension PostgreSQL pour séries temporelles
    """

    def __init__(self):
        # Charger le .env
        load_dotenv()

        # Paramètres DB
        self.host = os.getenv("TIMESCALE_DB_HOST", "timescaledb")
        self.port = int(os.getenv("TIMESCALE_DB_PORT", 5432))
        self.database = os.getenv("TIMESCALE_DB_NAME", "crypto_db")
        self.user = os.getenv("TIMESCALE_DB_USER", "crypto_user")
        self.password = os.getenv("TIMESCALE_DB_PASSWORD", "crypto_pass")

        self.logger = logger.bind(component="timescale_loader")

        # Créer les tables au démarrage
        self.create_tables()

    @contextmanager
    def get_connection(self):
        """
        Connexion sécurisée à TimescaleDB
        """
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            yield conn
        except Exception as e:
            self.logger.error(f"Erreur connexion : {e}")
            raise
        finally:
            if conn:
                conn.close()

    # ----------------- Insertion OHLCV -----------------
    def insert_ohlcv_dataframe(self, df: pd.DataFrame, timeframe: str = '1h'):
        if df.empty:
            self.logger.warning("DataFrame OHLCV vide, rien à insérer.")
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                INSERT INTO ohlcv (
                    time, exchange, symbol,
                    open, high, low, close, volume,
                    rsi_14, signal, timeframe
                ) VALUES (
                    to_timestamp(%s / 1000.0), %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
            """
            values_list = [
                (
                    int(row['timestamp']), row['exchange'], row['symbol'],
                    row['open'], row['high'], row['low'], row['close'], row['volume'],
                    row.get('rsi_14'), row.get('signal'), row.get('timeframe', timeframe)
                )
                for _, row in df.iterrows()
            ]
            execute_batch(cursor, query, values_list, page_size=1000)
            conn.commit()
            self.logger.info(f"✅ {len(values_list)} bougies OHLCV insérées")

    # ----------------- Insertion ticker -----------------
    def insert_ticker(self, ticker_data: Dict):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                INSERT INTO tickers (
                    time, exchange, symbol, last, bid, ask,
                    spread_absolute, spread_relative, mid_price,
                    high_24h, low_24h, volume_24h, range_24h, range_position
                ) VALUES (
                    to_timestamp(%s / 1000.0), %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            values = (
                ticker_data['timestamp'], ticker_data['exchange'], ticker_data['symbol'],
                ticker_data['last'], ticker_data.get('bid'), ticker_data.get('ask'),
                ticker_data.get('spread_absolute'), ticker_data.get('spread_relative'), ticker_data.get('mid_price'),
                ticker_data.get('high_24h'), ticker_data.get('low_24h'), ticker_data.get('volume_24h'),
                ticker_data.get('range_24h'), ticker_data.get('range_position')
            )
            cursor.execute(query, values)
            conn.commit()
            self.logger.debug(f"Ticker inséré : {ticker_data['symbol']} @ {ticker_data['last']}")

    def insert_tickers_batch(self, tickers_list: List[Dict]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                INSERT INTO tickers (
                    time, exchange, symbol, last, bid, ask,
                    spread_absolute, spread_relative, mid_price,
                    high_24h, low_24h, volume_24h, range_24h, range_position
                ) VALUES (
                    to_timestamp(%s / 1000.0), %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            values_list = [
                (
                    t['timestamp'], t['exchange'], t['symbol'],
                    t['last'], t.get('bid'), t.get('ask'),
                    t.get('spread_absolute'), t.get('spread_relative'), t.get('mid_price'),
                    t.get('high_24h'), t.get('low_24h'), t.get('volume_24h'),
                    t.get('range_24h'), t.get('range_position')
                )
                for t in tickers_list
            ]
            execute_batch(cursor, query, values_list, page_size=1000)
            conn.commit()
            self.logger.info(f"✅ {len(tickers_list)} tickers insérés en batch")

    # ----------------- Insertion arbitrage -----------------
    def insert_arbitrage_opportunity(self, opportunity: Dict):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                INSERT INTO arbitrage_opportunities (
                    time, symbol, buy_exchange, sell_exchange,
                    buy_price, sell_price, spread_percent, potential_profit
                ) VALUES (
                    NOW(), %s, %s, %s, %s, %s, %s, %s
                )
            """
            values = (
                opportunity['symbol'], opportunity['buy_exchange'], opportunity['sell_exchange'],
                opportunity['buy_price'], opportunity['sell_price'], opportunity['spread_percent'],
                opportunity.get('potential_profit', 0)
            )
            cursor.execute(query, values)
            conn.commit()
            self.logger.info(f"🚨 Arbitrage enregistré : {opportunity['symbol']} - {opportunity['spread_percent']:.2f}% profit")

    # ----------------- Requêtes -----------------
    def query_latest_prices(self, symbol: str, limit: int = 10) -> pd.DataFrame:
        with self.get_connection() as conn:
            query = """
                SELECT time, exchange, last, bid, ask, volume_24h
                FROM tickers
                WHERE symbol = %s
                ORDER BY time DESC
                LIMIT %s
            """
            df = pd.read_sql_query(query, conn, params=(symbol, limit))
            return df

    def query_ohlcv(self, symbol: str, timeframe: str, hours: int = 24) -> pd.DataFrame:
        with self.get_connection() as conn:
            query = """
                SELECT *
                FROM ohlcv
                WHERE symbol = %s
                  AND timeframe = %s
                  AND time >= NOW() - INTERVAL '%s hours'
                ORDER BY time ASC
            """
            df = pd.read_sql_query(query, conn, params=(symbol, timeframe, hours))
            return df

    def query_arbitrage_opportunities(self, hours: int = 24) -> pd.DataFrame:
        with self.get_connection() as conn:
            query = """
                SELECT *
                FROM arbitrage_opportunities
                WHERE time >= NOW() - INTERVAL '%s hours'
                ORDER BY spread_percent DESC
            """
            df = pd.read_sql_query(query, conn, params=(hours,))
            return df

    # ----------------- Création tables -----------------
    def create_tables(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

            # Table tickers
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickers (
                    time TIMESTAMPTZ NOT NULL,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    last DOUBLE PRECISION,
                    bid DOUBLE PRECISION,
                    ask DOUBLE PRECISION,
                    spread_absolute DOUBLE PRECISION,
                    spread_relative DOUBLE PRECISION,
                    mid_price DOUBLE PRECISION,
                    high_24h DOUBLE PRECISION,
                    low_24h DOUBLE PRECISION,
                    volume_24h DOUBLE PRECISION,
                    range_24h DOUBLE PRECISION,
                    range_position DOUBLE PRECISION
                );
            """)
            try:
                cursor.execute("SELECT create_hypertable('tickers', 'time', if_not_exists => TRUE);")
            except Exception as e:
                self.logger.warning(f"Hypertable tickers existe déjà : {e}")

            # Table ohlcv
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv (
                    time TIMESTAMPTZ NOT NULL,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    rsi_14 DOUBLE PRECISION,
                    signal TEXT,
                    signal_strength DOUBLE PRECISION
                );
            """)
            try:
                cursor.execute("SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE);")
            except Exception as e:
                self.logger.warning(f"Hypertable ohlcv existe déjà : {e}")

            # Table arbitrage_opportunities
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    buy_exchange TEXT NOT NULL,
                    sell_exchange TEXT NOT NULL,
                    buy_price DOUBLE PRECISION,
                    sell_price DOUBLE PRECISION,
                    spread_percent DOUBLE PRECISION,
                    potential_profit DOUBLE PRECISION
                );
            """)
            try:
                cursor.execute("SELECT create_hypertable('arbitrage_opportunities', 'time', if_not_exists => TRUE);")
            except Exception as e:
                self.logger.warning(f"Hypertable arbitrage existe déjà : {e}")

            conn.commit()
            self.logger.info("✅ Tables créées avec succès")
