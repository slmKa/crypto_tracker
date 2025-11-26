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

# Ajouter le path des scripts - essayer plusieurs chemins
TimescaleLoader = None
RedisLoader = None

# Essayer différents chemins possibles
# En Docker: /app/scripts
# En local: ../../../scripts depuis Dashboard/utils/
possible_paths = [
    '/app/scripts',  # Docker path (PRIORITÉ)
    os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'),  # Relatif local
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts')),  # Absolu local
]

scripts_path = None
for path in possible_paths:
    if os.path.exists(path):
        scripts_path = path
        print(f"✅ Found scripts at: {path}")
        if path not in sys.path:
            sys.path.insert(0, path)
        break

if not scripts_path:
    print(f"⚠️ Scripts path not found. Tried: {possible_paths}")
    # Utiliser le chemin Docker par défaut
    scripts_path = '/app/scripts'
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)

print(f"📁 Using scripts path: {scripts_path}")
print(f"📁 Path exists: {os.path.exists(scripts_path)}")
print(f"📁 sys.path[0]: {sys.path[0]}")

try:
    from loaders.timescale_loader import TimescaleLoader
    print("✅ TimescaleLoader imported successfully")
except ImportError as e:
    print(f"⚠️ TimescaleLoader import error: {e}")
    # Essayer import direct
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("timescale_loader", 
                                                       os.path.join(scripts_path, 'loaders', 'timescale_loader.py'))
        if spec and spec.loader:
            timescale_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(timescale_module)
            TimescaleLoader = timescale_module.TimescaleLoader
            print("✅ TimescaleLoader imported via direct path")
    except Exception as e2:
        print(f"❌ Direct import also failed: {e2}")

try:
    from loaders.redis_loader import RedisLoader
    print("✅ RedisLoader imported successfully")
except ImportError as e:
    print(f"⚠️ RedisLoader import error: {e}")
    # Essayer import direct
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("redis_loader", 
                                                       os.path.join(scripts_path, 'loaders', 'redis_loader.py'))
        if spec and spec.loader:
            redis_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(redis_module)
            RedisLoader = redis_module.RedisLoader
            print("✅ RedisLoader imported via direct path")
    except Exception as e2:
        print(f"❌ Direct import also failed: {e2}")


class DataLoader:
    """Classe unifiée : Redis + TimescaleDB + Binance"""

    def __init__(self):
        print("\n" + "="*60)
        print("🚀 DataLoader Initialization Started")
        print("="*60)
        
        # Binance
        try:
            print("📡 Initializing Binance...")
            self.exchange = ccxt.binance({'enableRateLimit': True})
            print("✅ Binance connected")
            st.success("✅ Binance connected")
        except Exception as e:
            print(f"⚠️ Binance init error: {e}")
            st.warning(f"⚠️ Binance init error: {e}")
            self.exchange = None

        # TimescaleDB
        try:
            print("📡 Initializing TimescaleDB...")
            self.timescale = TimescaleLoader() if TimescaleLoader else None
            if self.timescale and self.timescale.connected:
                print("✅ TimescaleDB connected")
                st.success("✅ TimescaleDB connected")
            elif self.timescale and not self.timescale.connected:
                print(f"⚠️ TimescaleDB not available (connected={self.timescale.connected})")
            else:
                print("⚠️ TimescaleDB loader is None")
        except Exception as e:
            print(f"❌ TimescaleDB init error: {type(e).__name__}: {e}")
            self.timescale = None

        # Redis
        try:
            print("📡 Initializing Redis...")
            self.redis = RedisLoader() if RedisLoader else None
            if self.redis and self.redis.connected:
                print("✅ Redis connected")
                st.success("✅ Redis connected")
            elif self.redis and not self.redis.connected:
                print(f"⚠️ Redis not available (connected={self.redis.connected})")
            else:
                print("⚠️ Redis loader is None")
        except Exception as e:
            print(f"❌ Redis init error: {type(e).__name__}: {e}")
            self.redis = None
        
        print("="*60)
        print("🚀 DataLoader Initialization Complete")
        print("="*60 + "\n")

    # ============================================================
    # 🔹 Binance - OHLCV et indicateurs techniques
    # ============================================================

    def get_ohlcv_data(self, symbol: str, timeframe: str = '1h', hours: int = 168) -> pd.DataFrame:
        """Récupère les données OHLCV depuis Binance avec indicateurs"""
        if not self.exchange:
            st.error("❌ Binance not initialized")
            return pd.DataFrame()

        try:
            # Convertir les heures en nombre de candles selon le timeframe
            timeframe_minutes = {
                '1m': 1, '5m': 5, '15m': 15, '30m': 30,
                '1h': 60, '4h': 240, '1d': 1440
            }
            minutes_per_candle = timeframe_minutes.get(timeframe, 60)
            limit = min(int(hours * 60 / minutes_per_candle), 1000)
            
            # Retry logic pour éviter les timeouts
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f"📊 Fetching {limit} candles for {symbol} ({timeframe}) - Attempt {attempt + 1}/{max_retries}")
                    data = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                    
                    if data:
                        print(f"✅ Successfully fetched {len(data)} candles")
                        break
                    else:
                        print(f"⚠️ No data returned, retrying...")
                        if attempt == max_retries - 1:
                            print(f"❌ Failed after {max_retries} attempts")
                            return pd.DataFrame()
                except Exception as e:
                    print(f"⚠️ Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == max_retries - 1:
                        raise
                    import time
                    time.sleep(1)  # Wait before retry

            if not data:
                print(f"⚠️ No OHLCV data returned for {symbol}")
                return pd.DataFrame()

            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # -------------------- Indicateurs techniques (OPTIMISÉS) --------------------
            print("📈 Calculating indicators...")
            
            # Moyennes mobiles simples
            df['sma_20'] = df['close'].rolling(window=20, min_periods=1).mean()
            df['sma_50'] = df['close'].rolling(window=50, min_periods=1).mean()
            df['sma_200'] = df['close'].rolling(window=200, min_periods=1).mean()
            
            # EMA pour MACD
            df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
            df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()

            # Bollinger Bands
            df['bb_middle'] = df['sma_20']
            std_20 = df['close'].rolling(window=20, min_periods=1).std()
            df['bb_upper'] = df['sma_20'] + 2 * std_20
            df['bb_lower'] = df['sma_20'] - 2 * std_20

            # RSI (Relative Strength Index)
            try:
                delta = df['close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                
                avg_gain = gain.rolling(window=14, min_periods=1).mean()
                avg_loss = loss.rolling(window=14, min_periods=1).mean()
                
                rs = avg_gain / (avg_loss + 1e-10)
                df['rsi_14'] = 100 - (100 / (1 + rs))
                df['rsi_14'] = df['rsi_14'].fillna(50)  # Remplir les NaN avec 50 (neutre)
                print(f"✅ RSI calculated: min={df['rsi_14'].min():.2f}, max={df['rsi_14'].max():.2f}, last={df['rsi_14'].iloc[-1]:.2f}")
            except Exception as e:
                print(f"⚠️ RSI calculation error: {e}")
                df['rsi_14'] = 50  # Valeur neutre par défaut

            # MACD (Moving Average Convergence Divergence)
            try:
                df['macd'] = df['ema_12'] - df['ema_26']
                df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
                df['macd_histogram'] = df['macd'] - df['macd_signal']
                
                # Vérifier les valeurs
                if df['macd'].abs().max() > 10000:  # Valeurs bizarres
                    print(f"⚠️ MACD values seem off: max={df['macd'].abs().max():.2f}")
                    # Recalculer avec adjust=True
                    df['ema_12'] = df['close'].ewm(span=12, adjust=True).mean()
                    df['ema_26'] = df['close'].ewm(span=26, adjust=True).mean()
                    df['macd'] = df['ema_12'] - df['ema_26']
                    df['macd_signal'] = df['macd'].ewm(span=9, adjust=True).mean()
                    df['macd_histogram'] = df['macd'] - df['macd_signal']
                
                print(f"✅ MACD calculated: min={df['macd'].min():.4f}, max={df['macd'].max():.4f}, last={df['macd'].iloc[-1]:.4f}")
            except Exception as e:
                print(f"⚠️ MACD calculation error: {e}")
                df['macd'] = 0
                df['macd_signal'] = 0
                df['macd_histogram'] = 0

            # -------------------- Indicateurs additionnels (OPTIMISÉS) --------------------
            # Stochastic Oscillator
            df = self._add_stochastic(df)
            
            # ATR (Average True Range)
            df = self._add_atr(df)
            
            # ADX (Average Directional Index) - OPTIONNEL (peut être lourd)
            if len(df) > 30:  # Seulement si assez de données
                df = self._add_adx(df)
            
            # CCI (Commodity Channel Index)
            df = self._add_cci(df)
            
            # Williams %R
            df = self._add_williams_r(df)
            
            # Support et Resistance
            df = self._add_support_resistance(df)
            
            # Pivot Points
            df = self._add_pivot_points(df)

            # Remplir les NaN avec forward fill puis backward fill
            print("🧹 Cleaning NaN values...")
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                df[col] = df[col].fillna(method='ffill').fillna(method='bfill').fillna(0)
            
            df['signal'] = 'HOLD'
            df.loc[(df['macd'] > df['macd_signal']) & (df['rsi_14'] < 30), 'signal'] = 'BUY'
            df.loc[(df['macd'] < df['macd_signal']) & (df['rsi_14'] > 70), 'signal'] = 'SELL'

            df['signal_strength'] = 0
            df.loc[df['signal'] == 'BUY', 'signal_strength'] = (70 - df['rsi_14']).clip(lower=0)
            df.loc[df['signal'] == 'SELL', 'signal_strength'] = (df['rsi_14'] - 30).clip(lower=0)

            print(f"✅ Indicators calculated successfully. Shape: {df.shape}")
            print(f"   RSI range: {df['rsi_14'].min():.2f} - {df['rsi_14'].max():.2f}")
            print(f"   MACD range: {df['macd'].min():.4f} - {df['macd'].max():.4f}")
            print(f"   ATR: {df['atr'].iloc[-1]:.2f}")
            return df

        except Exception as e:
            print(f"❌ Error fetching OHLCV data: {str(e)}")
            st.error(f"❌ Error fetching OHLCV data: {str(e)}")
            return pd.DataFrame()

    # ============================================================
    # 🔹 Latest Prices (Redis → Binance → TimescaleDB)
    # ============================================================

    def get_latest_prices(self, symbols: list) -> pd.DataFrame:
        """Récupérer les derniers prix (priorité: Redis > Binance > TimescaleDB)"""
        prices = []
        
        # Essayer Redis d'abord
        if self.redis and self.redis.connected:
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
        if not prices and self.timescale and self.timescale.connected:
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
        if not self.timescale or not self.timescale.connected:
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
                print(f"ℹ️ No historical data in DB for {symbol}, using Binance API")
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
        if not self.timescale or not self.timescale.connected:
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
        if not self.redis or not self.redis.connected:
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

    # ============================================================
    # 🔹 INDICATEURS TECHNIQUES AVANCÉS
    # ============================================================

    def _add_stochastic(self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
        """Ajouter Stochastic Oscillator (OPTIMISÉ)"""
        try:
            lowest_low = df['low'].rolling(window=k_period, min_periods=1).min()
            highest_high = df['high'].rolling(window=k_period, min_periods=1).max()
            df['stoch_k'] = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low + 1e-10)
            df['stoch_d'] = df['stoch_k'].rolling(window=d_period, min_periods=1).mean()
        except Exception as e:
            print(f"⚠️ Stochastic calculation error: {e}")
            df['stoch_k'] = np.nan
            df['stoch_d'] = np.nan
        return df

    def _add_atr(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Ajouter Average True Range (OPTIMISÉ)"""
        try:
            tr = np.maximum(
                df['high'] - df['low'],
                np.maximum(
                    abs(df['high'] - df['close'].shift()),
                    abs(df['low'] - df['close'].shift())
                )
            )
            df['atr'] = pd.Series(tr).rolling(window=period, min_periods=1).mean()
        except Exception as e:
            print(f"⚠️ ATR calculation error: {e}")
            df['atr'] = np.nan
        return df

    def _add_adx(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Ajouter Average Directional Index (OPTIMISÉ)"""
        try:
            high_diff = df['high'] - df['high'].shift()
            low_diff = df['low'].shift() - df['low']
            
            plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
            minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
            
            tr = np.maximum(
                df['high'] - df['low'],
                np.maximum(
                    abs(df['high'] - df['close'].shift()),
                    abs(df['low'] - df['close'].shift())
                )
            )
            atr = pd.Series(tr).rolling(window=period, min_periods=1).mean()
            
            plus_di = 100 * (pd.Series(plus_dm).rolling(window=period, min_periods=1).mean() / (atr + 1e-10))
            minus_di = 100 * (pd.Series(minus_dm).rolling(window=period, min_periods=1).mean() / (atr + 1e-10))
            
            di_diff = abs(plus_di - minus_di)
            di_sum = plus_di + minus_di
            df['adx'] = 100 * (di_diff / (di_sum + 1e-10)).rolling(window=period, min_periods=1).mean()
        except Exception as e:
            print(f"⚠️ ADX calculation error: {e}")
            df['adx'] = np.nan
        
        return df

    def _add_cci(self, df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """Ajouter Commodity Channel Index (OPTIMISÉ)"""
        try:
            tp = (df['high'] + df['low'] + df['close']) / 3
            sma_tp = tp.rolling(window=period, min_periods=1).mean()
            # Calcul MAD optimisé
            mad = tp.rolling(window=period, min_periods=1).apply(
                lambda x: np.abs(x - x.mean()).mean(), raw=False
            )
            df['cci'] = (tp - sma_tp) / (0.015 * mad + 1e-10)
        except Exception as e:
            print(f"⚠️ CCI calculation error: {e}")
            df['cci'] = np.nan
        return df

    def _add_williams_r(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Ajouter Williams %R (OPTIMISÉ)"""
        try:
            highest_high = df['high'].rolling(window=period, min_periods=1).max()
            lowest_low = df['low'].rolling(window=period, min_periods=1).min()
            df['williams_r'] = -100 * (highest_high - df['close']) / (highest_high - lowest_low + 1e-10)
        except Exception as e:
            print(f"⚠️ Williams %R calculation error: {e}")
            df['williams_r'] = np.nan
        return df

    def _add_support_resistance(self, df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """Ajouter niveaux de support et résistance (OPTIMISÉ)"""
        try:
            df['resistance'] = df['high'].rolling(window=period, min_periods=1).max()
            df['support'] = df['low'].rolling(window=period, min_periods=1).min()
        except Exception as e:
            print(f"⚠️ Support/Resistance calculation error: {e}")
            df['resistance'] = np.nan
            df['support'] = np.nan
        return df

    def _add_pivot_points(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ajouter Pivot Points (OPTIMISÉ)"""
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            df['pivot'] = (high + low + close) / 3
            df['r1'] = 2 * df['pivot'] - low
            df['r2'] = df['pivot'] + (high - low)
            df['s1'] = 2 * df['pivot'] - high
            df['s2'] = df['pivot'] - (high - low)
        except Exception as e:
            print(f"⚠️ Pivot Points calculation error: {e}")
            df['pivot'] = np.nan
            df['r1'] = np.nan
            df['r2'] = np.nan
            df['s1'] = np.nan
            df['s2'] = np.nan
        
        return df

    def detect_signals(self, df: pd.DataFrame) -> dict:
        """Détecter les signaux de trading avancés"""
        signals = {
            'golden_cross': False,
            'death_cross': False,
            'rsi_divergence': False,
            'macd_crossover': False,
            'support_breakout': False,
            'resistance_breakout': False
        }
        
        if len(df) < 2:
            return signals
        
        try:
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            
            # Golden Cross / Death Cross
            if 'sma_50' in df.columns and 'sma_200' in df.columns:
                if (pd.notna(prev_row['sma_50']) and pd.notna(prev_row['sma_200']) and
                    pd.notna(last_row['sma_50']) and pd.notna(last_row['sma_200'])):
                    if prev_row['sma_50'] < prev_row['sma_200'] and last_row['sma_50'] > last_row['sma_200']:
                        signals['golden_cross'] = True
                    elif prev_row['sma_50'] > prev_row['sma_200'] and last_row['sma_50'] < last_row['sma_200']:
                        signals['death_cross'] = True
            
            # MACD Crossover
            if 'macd' in df.columns and 'macd_signal' in df.columns:
                if (pd.notna(prev_row['macd']) and pd.notna(prev_row['macd_signal']) and
                    pd.notna(last_row['macd']) and pd.notna(last_row['macd_signal'])):
                    if prev_row['macd'] < prev_row['macd_signal'] and last_row['macd'] > last_row['macd_signal']:
                        signals['macd_crossover'] = True
            
            # Support/Resistance Breakout
            if 'support' in df.columns and 'resistance' in df.columns:
                if (pd.notna(last_row['close']) and pd.notna(last_row['resistance']) and 
                    pd.notna(last_row['support'])):
                    if last_row['close'] > last_row['resistance']:
                        signals['resistance_breakout'] = True
                    elif last_row['close'] < last_row['support']:
                        signals['support_breakout'] = True
        except Exception as e:
            print(f"⚠️ Signal detection error: {e}")
        
        return signals

    def backtest_strategy(self, df: pd.DataFrame, initial_capital: float = 10000) -> dict:
        """Backtester une stratégie simple RSI + MACD"""
        capital = initial_capital
        position = False
        entry_price = 0
        trades = []
        
        try:
            for i in range(1, len(df)):
                row = df.iloc[i]
                
                # Vérifier que les valeurs sont valides
                if pd.isna(row['rsi_14']) or pd.isna(row['macd']) or pd.isna(row['close']):
                    continue
                
                # Signal d'achat: RSI < 30 et MACD > Signal
                if not position:
                    if row['rsi_14'] < 30 and row['macd'] > row['macd_signal']:
                        entry_price = row['close']
                        position = True
                        print(f"📈 BUY signal at {row.name}: RSI={row['rsi_14']:.1f}, MACD={row['macd']:.4f}")
                
                # Signal de vente: RSI > 70 ou MACD < Signal
                elif position:
                    if row['rsi_14'] > 70 or row['macd'] < row['macd_signal']:
                        exit_price = row['close']
                        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                        capital *= (1 + pnl_pct / 100)
                        trades.append({
                            'entry': entry_price,
                            'exit': exit_price,
                            'pnl_pct': pnl_pct,
                            'timestamp': row.name
                        })
                        print(f"📉 SELL signal at {row.name}: P&L={pnl_pct:+.2f}%")
                        position = False
            
            total_return = ((capital - initial_capital) / initial_capital) * 100
            win_rate = len([t for t in trades if t['pnl_pct'] > 0]) / len(trades) if trades else 0
            
            print(f"✅ Backtest complete: {len(trades)} trades, {win_rate*100:.1f}% win rate, {total_return:+.2f}% return")
        except Exception as e:
            print(f"⚠️ Backtest error: {e}")
        
        return {
            'final_capital': capital,
            'total_return': total_return,
            'num_trades': len(trades),
            'win_rate': win_rate * 100,
            'trades': trades
        }

    # ============================================================
    # 🔹 ARBITRAGE AVANCÉ - CALCULS EN TEMPS RÉEL
    # ============================================================

    def calculate_arbitrage_opportunities(self, symbols: list = None, min_spread: float = 0.1) -> list:
        """
        Calculer les opportunités d'arbitrage en temps réel
        
        Args:
            symbols: Liste des symboles à analyser (None = top 50)
            min_spread: Spread minimum en %
            
        Returns:
            Liste des opportunités profitables
        """
        if not self.exchange:
            return []
        
        try:
            print("🔍 Scanning for arbitrage opportunities...")
            
            # Symboles par défaut si non spécifiés
            if not symbols:
                symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
                          'SOL/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT', 'LINK/USDT']
            
            opportunities = []
            
            # Pour chaque symbole, récupérer le ticker
            for symbol in symbols:
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    
                    if ticker and ticker.get('bid') and ticker.get('ask'):
                        bid = ticker['bid']
                        ask = ticker['ask']
                        
                        # Vérifier que bid et ask sont valides
                        if bid > 0 and ask > 0 and ask >= bid:
                            spread_pct = ((ask - bid) / bid) * 100
                            
                            # Vérifier si spread > minimum
                            if spread_pct >= min_spread:
                                opportunity = {
                                    'symbol': symbol,
                                    'buy_exchange': 'Binance',
                                    'sell_exchange': 'Binance',
                                    'buy_price': bid,
                                    'sell_price': ask,
                                    'spread_percent': spread_pct,
                                    'spread_absolute': ask - bid,
                                    'timestamp': ticker.get('timestamp', int(datetime.now().timestamp() * 1000)),
                                    'volume_24h': ticker.get('quoteVolume', 0),
                                    'last_price': ticker.get('last', 0)
                                }
                                opportunities.append(opportunity)
                            else:
                                print(f"  {symbol}: spread {spread_pct:.4f}% < {min_spread}%")
                        else:
                            print(f"  {symbol}: invalid bid/ask ({bid}/{ask})")
                    else:
                        print(f"  {symbol}: no bid/ask data")
                except Exception as e:
                    print(f"⚠️ Error fetching {symbol}: {e}")
                    continue
            
            print(f"✅ Found {len(opportunities)} opportunities with spread >= {min_spread}%")
            return sorted(opportunities, key=lambda x: x['spread_percent'], reverse=True)
        
        except Exception as e:
            print(f"❌ Arbitrage calculation error: {e}")
            return []

    def calculate_total_fees(self, exchange1: str, exchange2: str, symbol: str, 
                            amount: float, maker_fee: float = 0.1, taker_fee: float = 0.1,
                            withdrawal_fee: float = 0.0) -> dict:
        """
        Calculer tous les frais d'arbitrage
        
        Args:
            exchange1: Exchange d'achat
            exchange2: Exchange de vente
            symbol: Symbole de la paire
            amount: Montant en USD
            maker_fee: Frais maker en %
            taker_fee: Frais taker en %
            withdrawal_fee: Frais de retrait en %
            
        Returns:
            Dict avec détails des frais
        """
        try:
            # Frais de trading (buy = taker, sell = maker)
            buy_fee = amount * (taker_fee / 100)
            sell_fee = (amount - buy_fee) * (maker_fee / 100)
            
            # Frais de retrait
            withdrawal_cost = (amount - buy_fee) * (withdrawal_fee / 100)
            
            # Total
            total_fees = buy_fee + sell_fee + withdrawal_cost
            
            return {
                'buy_fee': buy_fee,
                'sell_fee': sell_fee,
                'withdrawal_fee': withdrawal_cost,
                'total_fees': total_fees,
                'total_fees_percent': (total_fees / amount) * 100,
                'net_amount': amount - total_fees
            }
        except Exception as e:
            print(f"⚠️ Fee calculation error: {e}")
            return {
                'buy_fee': 0, 'sell_fee': 0, 'withdrawal_fee': 0,
                'total_fees': 0, 'total_fees_percent': 0, 'net_amount': amount
            }

    def check_liquidity(self, exchange: str, symbol: str, amount: float) -> dict:
        """
        Vérifier la liquidité et estimer le slippage
        
        Args:
            exchange: Nom de l'exchange
            symbol: Symbole de la paire
            amount: Montant en USD
            
        Returns:
            Dict avec info de liquidité
        """
        try:
            if not self.exchange:
                return {'sufficient': False, 'slippage_percent': 0, 'message': 'Exchange not connected'}
            
            # Récupérer l'order book
            order_book = self.exchange.fetch_order_book(symbol, limit=20)
            
            if not order_book or 'bids' not in order_book:
                return {'sufficient': False, 'slippage_percent': 0, 'message': 'No order book data'}
            
            # Calculer la profondeur
            bids = order_book['bids']
            asks = order_book['asks']
            
            # Somme des volumes disponibles
            bid_volume = sum([bid[1] for bid in bids])
            ask_volume = sum([ask[1] for ask in asks])
            
            # Estimer le slippage (simple estimation)
            avg_volume = (bid_volume + ask_volume) / 2
            slippage_pct = (amount / (avg_volume * 100)) * 100 if avg_volume > 0 else 0
            slippage_pct = min(slippage_pct, 5.0)  # Cap à 5%
            
            sufficient = avg_volume > amount
            
            return {
                'sufficient': sufficient,
                'slippage_percent': slippage_pct,
                'bid_volume': bid_volume,
                'ask_volume': ask_volume,
                'message': 'Sufficient liquidity' if sufficient else 'Insufficient liquidity'
            }
        except Exception as e:
            print(f"⚠️ Liquidity check error: {e}")
            return {'sufficient': False, 'slippage_percent': 0, 'message': str(e)}

    def get_arbitrage_stats_by_exchange(self, hours: int = 24) -> dict:
        """
        Récupérer statistiques d'arbitrage par exchange
        
        Args:
            hours: Nombre d'heures à analyser
            
        Returns:
            Dict avec statistiques par exchange
        """
        try:
            df = pd.DataFrame()
            
            # Essayer TimescaleDB d'abord
            if self.timescale and self.timescale.connected:
                try:
                    df = self.timescale.query_arbitrage_opportunities(hours)
                except:
                    pass
            
            # Si pas de données, essayer Redis
            if df.empty and self.redis and self.redis.connected:
                try:
                    redis_opps = self.redis.get_top_arbitrage_opportunities(limit=100)
                    if redis_opps:
                        df = pd.DataFrame(redis_opps)
                except:
                    pass
            
            if df.empty:
                return {}
            
            stats = {}
            
            # Stats pour chaque exchange pair
            for _, row in df.iterrows():
                buy_ex = row.get('buy_exchange', 'Unknown')
                sell_ex = row.get('sell_exchange', 'Unknown')
                pair = f"{buy_ex} → {sell_ex}"
                
                if pair not in stats:
                    stats[pair] = {
                        'count': 0,
                        'avg_spread': 0,
                        'max_spread': 0,
                        'min_spread': float('inf'),
                        'total_profit': 0
                    }
                
                spread = row.get('spread_percent', 0)
                stats[pair]['count'] += 1
                stats[pair]['avg_spread'] += spread
                stats[pair]['max_spread'] = max(stats[pair]['max_spread'], spread)
                stats[pair]['min_spread'] = min(stats[pair]['min_spread'], spread)
                stats[pair]['total_profit'] += row.get('potential_profit', 0)
            
            # Calculer moyennes
            for pair in stats:
                if stats[pair]['count'] > 0:
                    stats[pair]['avg_spread'] /= stats[pair]['count']
                if stats[pair]['min_spread'] == float('inf'):
                    stats[pair]['min_spread'] = 0
            
            print(f"✅ Exchange stats calculated: {len(stats)} pairs")
            return stats
        except Exception as e:
            print(f"⚠️ Exchange stats error: {e}")
            return {}

    def get_arbitrage_stats_by_symbol(self, hours: int = 24) -> dict:
        """
        Récupérer statistiques d'arbitrage par symbole
        
        Args:
            hours: Nombre d'heures à analyser
            
        Returns:
            Dict avec statistiques par symbole
        """
        try:
            df = pd.DataFrame()
            
            # Essayer TimescaleDB d'abord
            if self.timescale and self.timescale.connected:
                try:
                    df = self.timescale.query_arbitrage_opportunities(hours)
                except:
                    pass
            
            # Si pas de données, essayer Redis
            if df.empty and self.redis and self.redis.connected:
                try:
                    redis_opps = self.redis.get_top_arbitrage_opportunities(limit=100)
                    if redis_opps:
                        df = pd.DataFrame(redis_opps)
                except:
                    pass
            
            if df.empty:
                return {}
            
            stats = {}
            
            # Stats pour chaque symbole
            for _, row in df.iterrows():
                symbol = row.get('symbol', 'Unknown')
                
                if symbol not in stats:
                    stats[symbol] = {
                        'count': 0,
                        'avg_spread': 0,
                        'max_spread': 0,
                        'min_spread': float('inf'),
                        'total_profit': 0,
                        'exchanges': set()
                    }
                
                spread = row.get('spread_percent', 0)
                stats[symbol]['count'] += 1
                stats[symbol]['avg_spread'] += spread
                stats[symbol]['max_spread'] = max(stats[symbol]['max_spread'], spread)
                stats[symbol]['min_spread'] = min(stats[symbol]['min_spread'], spread)
                stats[symbol]['total_profit'] += row.get('potential_profit', 0)
                stats[symbol]['exchanges'].add(row.get('buy_exchange', 'Unknown'))
                stats[symbol]['exchanges'].add(row.get('sell_exchange', 'Unknown'))
            
            # Calculer moyennes et convertir sets en listes
            for symbol in stats:
                if stats[symbol]['count'] > 0:
                    stats[symbol]['avg_spread'] /= stats[symbol]['count']
                if stats[symbol]['min_spread'] == float('inf'):
                    stats[symbol]['min_spread'] = 0
                stats[symbol]['exchanges'] = list(stats[symbol]['exchanges'])
                stats[symbol]['num_exchanges'] = len(stats[symbol]['exchanges'])
            
            print(f"✅ Symbol stats calculated: {len(stats)} symbols")
            return stats
        except Exception as e:
            print(f"⚠️ Symbol stats error: {e}")
            return {}