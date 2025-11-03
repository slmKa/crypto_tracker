"""
DataLoader - Fusion Timescale, Redis et Binance (CORRIGÉ)
"""

import pandas as pd
import numpy as np
import streamlit as st
import ccxt
from datetime import datetime, timedelta
import sys
import os

# Ajouter le path des scripts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))

try:
    from loaders.timescale_loader import TimescaleLoader
    from loaders.redis_loader import RedisLoader
except ImportError as e:
    st.error(f"⚠️ Import error: {e}")
    TimescaleLoader = None
    RedisLoader = None


class DataLoader:
    """Classe unifiée : Redis + TimescaleDB + Binance"""

    def __init__(self):
        # Binance
        try:
            self.exchange = ccxt.binance({'enableRateLimit': True})
            st.success("✅ Binance connected")
        except Exception as e:
            st.warning(f"⚠️ Binance init error: {e}")
            self.exchange = None

        # TimescaleDB
        try:
            self.timescale = TimescaleLoader() if TimescaleLoader else None
            if self.timescale:
                st.success("✅ TimescaleDB connected")
        except Exception as e:
            st.warning(f"⚠️ TimescaleDB init error: {e}")
            self.timescale = None

        # Redis
        try:
            self.redis = RedisLoader() if RedisLoader else None
            if self.redis:
                st.success("✅ Redis connected")
        except Exception as e:
            st.warning(f"⚠️ Redis init error: {e}")
            self.redis = None

    # ============================================================
    # 🔹 Binance - OHLCV et indicateurs techniques
    # ============================================================

    def get_ohlcv_data(self, symbol: str, timeframe: str = '1h', hours: int = 168) -> pd.DataFrame:
        """Récupère les données OHLCV depuis Binance avec indicateurs"""
        if not self.exchange:
            st.error("❌ Binance not initialized")
            return pd.DataFrame()

        try:
            limit = min(hours, 1000)
            since = self.exchange.milliseconds() - hours * 60 * 60 * 1000
            
            data = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)

            if not data:
                st.warning(f"⚠️ No OHLCV data returned for {symbol}")
                return pd.DataFrame()

            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # -------------------- Indicateurs techniques --------------------
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
            df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()

            df['bb_middle'] = df['sma_20']
            df['bb_upper'] = df['sma_20'] + 2 * df['close'].rolling(window=20).std()
            df['bb_lower'] = df['sma_20'] - 2 * df['close'].rolling(window=20).std()

            delta = df['close'].diff()
            gain = np.where(delta > 0, delta, 0)
            loss = np.where(delta < 0, -delta, 0)
            avg_gain = pd.Series(gain).rolling(window=14).mean()
            avg_loss = pd.Series(loss).rolling(window=14).mean()
            rs = avg_gain / (avg_loss + 1e-10)  # Éviter division par zéro
            df['rsi_14'] = 100 - (100 / (1 + rs))

            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']

            df['signal'] = 'HOLD'
            df.loc[(df['macd'] > df['macd_signal']) & (df['rsi_14'] < 30), 'signal'] = 'BUY'
            df.loc[(df['macd'] < df['macd_signal']) & (df['rsi_14'] > 70), 'signal'] = 'SELL'

            df['signal_strength'] = 0
            df.loc[df['signal'] == 'BUY', 'signal_strength'] = (70 - df['rsi_14']).clip(lower=0)
            df.loc[df['signal'] == 'SELL', 'signal_strength'] = (df['rsi_14'] - 30).clip(lower=0)

            return df.dropna()

        except Exception as e:
            st.error(f"❌ Error fetching OHLCV data: {str(e)}")
            return pd.DataFrame()

    # ============================================================
    # 🔹 Latest Prices (Redis → Binance → TimescaleDB)
    # ============================================================

    def get_latest_prices(self, symbols: list) -> pd.DataFrame:
        """Récupérer les derniers prix (priorité: Redis > Binance > TimescaleDB)"""
        prices = []
        
        # Essayer Redis d'abord
        if self.redis:
            for symbol in symbols:
                try:
                    ticker = self.redis.get_ticker('binance', symbol)
                    if ticker:
                        prices.append({
                            'symbol': symbol,
                            'price': ticker.get('last', np.nan),
                            'change_24h': ticker.get('percentage', 0),
                            'volume_24h': ticker.get('quoteVolume', 0),
                            'high_24h': ticker.get('high', 0),
                            'low_24h': ticker.get('low', 0),
                            'timestamp': datetime.fromtimestamp(ticker.get('timestamp', 0) / 1000)
                        })
                except Exception as e:
                    st.warning(f"⚠️ Redis error for {symbol}: {e}")
        
        # Si Redis vide, essayer Binance direct
        if not prices and self.exchange:
            for symbol in symbols:
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    if ticker:
                        prices.append({
                            'symbol': symbol,
                            'price': ticker.get('last', np.nan),
                            'change_24h': ticker.get('percentage', 0),
                            'volume_24h': ticker.get('quoteVolume', 0),
                            'high_24h': ticker.get('high', 0),
                            'low_24h': ticker.get('low', 0),
                            'timestamp': datetime.fromtimestamp(ticker.get('timestamp', 0) / 1000)
                        })
                except Exception as e:
                    st.warning(f"⚠️ Binance error for {symbol}: {e}")

        # Si toujours vide, fallback TimescaleDB
        if not prices and self.timescale:
            return self._get_latest_from_db(symbols)

        return pd.DataFrame(prices) if prices else pd.DataFrame(columns=[
            'symbol', 'price', 'change_24h', 'volume_24h', 'high_24h', 'low_24h', 'timestamp'
        ])

    def _get_latest_from_db(self, symbols: list) -> pd.DataFrame:
        """Fallback vers TimescaleDB"""
        all_data = []
        for symbol in symbols:
            try:
                df = self.timescale.query_latest_prices(symbol, limit=1)
                if not df.empty:
                    row = df.iloc[0]
                    all_data.append({
                        'symbol': symbol,
                        'price': row.get('last', np.nan),
                        'change_24h': row.get('percentage', 0),
                        'volume_24h': row.get('quoteVolume', 0),
                        'high_24h': row.get('high', 0),
                        'low_24h': row.get('low', 0),
                        'timestamp': row.get('time', datetime.now())
                    })
            except Exception as e:
                st.warning(f"⚠️ DB error for {symbol}: {e}")

        return pd.DataFrame(all_data) if all_data else pd.DataFrame(columns=[
            'symbol', 'price', 'change_24h', 'volume_24h', 'high_24h', 'low_24h', 'timestamp'
        ])

    # ============================================================
    # 🔹 Price History
    # ============================================================

    def get_price_history(self, symbol: str, hours: int = 24) -> pd.DataFrame:
        """Récupère l'historique des prix"""
        if not self.timescale:
            st.warning("⚠️ TimescaleDB not available, using Binance")
            return self._get_price_history_binance(symbol, hours)

        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            # ✅ TESTER PLUSIEURS VARIANTES DE NOM DE COLONNE
            queries = [
                # Variante 1: quotevolume (minuscule)
                """
                SELECT time, last as price, quotevolume as volume_24h
                FROM tickers
                WHERE symbol = %s AND time >= %s AND time <= %s
                ORDER BY time ASC
                """,
                # Variante 2: quoteVolume (camelCase)
                """
                SELECT time, last as price, "quoteVolume" as volume_24h
                FROM tickers
                WHERE symbol = %s AND time >= %s AND time <= %s
                ORDER BY time ASC
                """,
                # Variante 3: volume (fallback)
                """
                SELECT time, last as price, volume as volume_24h
                FROM tickers
                WHERE symbol = %s AND time >= %s AND time <= %s
                ORDER BY time ASC
                """
            ]
            
            df = pd.DataFrame()
            last_error = None
            
            with self.timescale.get_connection() as conn:
                for query in queries:
                    try:
                        df = pd.read_sql_query(query, conn, params=(symbol, start_time, end_time))
                        if not df.empty:
                            break  # Succès, sortir de la boucle
                    except Exception as e:
                        last_error = e
                        continue
            
            if df.empty:
                st.warning(f"⚠️ No DB data for {symbol}, using Binance")
                return self._get_price_history_binance(symbol, hours)
            
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            
            # ✅ AJOUTER COLONNE 'volume' POUR COMPATIBILITÉ
            df['volume'] = df['volume_24h']
            
            return df

        except Exception as e:
            st.warning(f"⚠️ DB history error: {e}")
            return self._get_price_history_binance(symbol, hours)

    def _get_price_history_binance(self, symbol: str, hours: int) -> pd.DataFrame:
        """Fallback: récupérer l'historique depuis Binance"""
        if not self.exchange:
            return pd.DataFrame()

        try:
            timeframe = '1h'
            limit = min(hours, 1000)
            since = self.exchange.milliseconds() - hours * 60 * 60 * 1000
            
            data = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
            
            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['price'] = df['close']
            df['volume_24h'] = df['volume']
            df = df[['time', 'price', 'volume_24h']]
            df.set_index('time', inplace=True)
            
            return df

        except Exception as e:
            st.error(f"❌ Binance history error: {e}")
            return pd.DataFrame()

    # ============================================================
    # 🔹 Arbitrage
    # ============================================================

    def get_arbitrage_opportunities(self, hours: int = 24) -> pd.DataFrame:
        """Récupère les opportunités d'arbitrage depuis TimescaleDB"""
        if not self.timescale:
            return pd.DataFrame()

        try:
            df = self.timescale.query_arbitrage_opportunities(hours)
            if not df.empty:
                df = df.sort_values('spread_percent', ascending=False)
            return df
        except Exception as e:
            st.error(f"❌ Arbitrage DB error: {e}")
            return pd.DataFrame()

    def get_top_arbitrage_redis(self, limit: int = 10) -> list:
        """Retourne les top opportunités d'arbitrage depuis Redis"""
        if not self.redis:
            st.warning("⚠️ Redis not available")
            return []

        try:
            return self.redis.get_top_arbitrage_opportunities(limit)
        except Exception as e:
            st.error(f"❌ Redis arbitrage error: {e}")
            return []

    # ============================================================
    # 🔹 Volume Analysis
    # ============================================================

    def get_volume_analysis(self, symbol: str, hours: int = 24) -> dict:
        """Analyse du volume"""
        df = self.get_price_history(symbol, hours)
        
        if df.empty or 'volume_24h' not in df.columns:
            return {}

        return {
            'total_volume': df['volume_24h'].sum(),
            'avg_volume': df['volume_24h'].mean(),
            'max_volume': df['volume_24h'].max(),
            'min_volume': df['volume_24h'].min()
        }