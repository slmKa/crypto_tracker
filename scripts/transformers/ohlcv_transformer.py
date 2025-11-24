"""
Transformer pour les données OHLCV (bougies)
"""
from typing import Dict, List
from .base_transformer import BaseTransformer
import pandas as pd
import numpy as np

class OHLCVTransformer(BaseTransformer):
    """
    Transforme les données OHLCV (bougies japonaises)
    
    Enrichissements :
    - Indicateurs techniques (moyennes mobiles, RSI, MACD)
    - Détection de patterns
    - Signaux de trading
    """
    
    def transform(self, raw_data: Dict) -> pd.DataFrame:
        """
        Transformer des données OHLCV brutes
        
        Args:
            raw_data: Dict avec 'data' (liste de bougies) et métadonnées
            
        Returns:
            DataFrame avec bougies normalisées + indicateurs
        """
        # Extraire les données
        ohlcv_list = raw_data.get('data', [])
        
        # Créer le DataFrame
        df = pd.DataFrame(ohlcv_list, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Normaliser timestamp
        df['timestamp'] = df['timestamp'].apply(self.normalize_timestamp)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('datetime', inplace=True)
        
        # Ajouter métadonnées
        df['exchange'] = raw_data.get('exchange')
        df['symbol'] = self.normalize_symbol(raw_data.get('symbol', ''))
        df['timeframe'] = raw_data.get('timeframe')
        
        # Valider chaque bougie
        df['is_valid'] = df.apply(
            lambda row: self.validate_price_data(row.to_dict()), 
            axis=1
        )
        
        # Filtrer les bougies invalides
        invalid_count = (~df['is_valid']).sum()
        if invalid_count > 0:
            self.logger.warning(f"Suppression de {invalid_count} bougies invalides")
            df = df[df['is_valid']]
        
        df.drop('is_valid', axis=1, inplace=True)
        
        # Enrichir avec des indicateurs
        df = self.add_technical_indicators(df)
        
        return df
    
    def add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ajouter des indicateurs techniques classiques
        
        Indicateurs calculés :
        1. SMA (Simple Moving Average) - Moyenne mobile simple
        2. EMA (Exponential Moving Average) - Moyenne mobile exponentielle
        3. RSI (Relative Strength Index) - Force relative
        4. MACD (Moving Average Convergence Divergence)
        5. Bollinger Bands - Bandes de Bollinger
        
        Args:
            df: DataFrame avec OHLCV
            
        Returns:
            DataFrame enrichi
        """
        # 1. SMA (Simple Moving Average)
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['sma_200'] = df['close'].rolling(window=200).mean()
        
        # 2. EMA (Exponential Moving Average)
        df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
        
        # 3. RSI (Relative Strength Index)
        df['rsi_14'] = self.calculate_rsi(df['close'], period=14)
        
        # 4. MACD
        macd = self.calculate_macd(df['close'])
        df['macd'] = macd['macd']
        df['macd_signal'] = macd['signal']
        df['macd_histogram'] = macd['histogram']
        
        # 5. Bollinger Bands
        bb = self.calculate_bollinger_bands(df['close'], period=20, std_dev=2)
        df['bb_upper'] = bb['upper']
        df['bb_middle'] = bb['middle']
        df['bb_lower'] = bb['lower']
        
        # 6. Volume analysis
        df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20']  # Volume relatif
        
        # 7. Price changes
        df['price_change'] = df['close'].pct_change()  # Changement en %
        df['price_change_abs'] = df['close'].diff()    # Changement absolu
        
        return df
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculer le RSI (Relative Strength Index)
        
        RSI = Indicateur de momentum qui mesure la vitesse et l'amplitude
              des mouvements de prix
        
        Interprétation :
        - RSI > 70 : Surachat (overbought) → Potentielle baisse
        - RSI < 30 : Survente (oversold) → Potentielle hausse
        - RSI = 50 : Neutre
        
        Formule :
        RSI = 100 - (100 / (1 + RS))
        où RS = Moyenne des gains / Moyenne des pertes
        
        Args:
            prices: Série de prix de clôture
            period: Période de calcul (défaut: 14)
            
        Returns:
            Série avec les valeurs RSI
        """
        # Calculer les variations
        delta = prices.diff()
        
        # Séparer gains et pertes
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        # Moyennes mobiles exponentielles
        avg_gains = gains.ewm(span=period, adjust=False).mean()
        avg_losses = losses.ewm(span=period, adjust=False).mean()
        
        # RS = Ratio gain/perte
        rs = avg_gains / avg_losses
        
        # RSI final
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_macd(self, prices: pd.Series, fast=12, slow=26, signal=9) -> Dict:
        """
        Calculer le MACD (Moving Average Convergence Divergence)
        
        MACD = Indicateur de tendance basé sur la convergence/divergence
               de deux moyennes mobiles exponentielles
        
        Composantes :
        1. MACD Line = EMA(12) - EMA(26)
        2. Signal Line = EMA(9) du MACD
        3. Histogram = MACD - Signal
        
        Interprétation :
        - MACD > Signal : Signal d'achat (bullish)
        - MACD < Signal : Signal de vente (bearish)
        - Histogram positif croissant : Momentum haussier
        - Histogram négatif décroissant : Momentum baissier
        
        Args:
            prices: Série de prix
            fast: Période EMA rapide (défaut: 12)
            slow: Période EMA lente (défaut: 26)
            signal: Période signal line (défaut: 9)
            
        Returns:
            Dict avec macd, signal, histogram
        """
        # EMAs
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        
        # Histogram
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    def calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2) -> Dict:
        """
        Calculer les Bandes de Bollinger
        
        Bollinger Bands = Bandes de volatilité autour d'une moyenne mobile
        
        Composantes :
        1. Middle Band = SMA(20)
        2. Upper Band = SMA(20) + 2 * σ (écart-type)
        3. Lower Band = SMA(20) - 2 * σ
        
        Interprétation :
        - Prix touche upper band : Potentiel surachat
        - Prix touche lower band : Potentiel survente
        - Bandes resserrées : Faible volatilité → Breakout imminent
        - Bandes élargies : Haute volatilité
        
        Args:
            prices: Série de prix
            period: Période moyenne mobile (défaut: 20)
            std_dev: Nombre d'écarts-types (défaut: 2)
            
        Returns:
            Dict avec upper, middle, lower bands
        """
        # Middle band = SMA
        middle = prices.rolling(window=period).mean()
        
        # Standard deviation
        std = prices.rolling(window=period).std()
        
        # Bands
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }
    
    def detect_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Détecter des patterns de bougies classiques
        
        Patterns implémentés :
        1. Doji : Open ≈ Close (indécision)
        2. Hammer : Long lower wick (potentiel renversement haussier)
        3. Shooting Star : Long upper wick (potentiel renversement baissier)
        4. Engulfing : Bougie englobe la précédente
        
        Args:
            df: DataFrame avec OHLCV
            
        Returns:
            DataFrame avec colonnes de patterns (bool)
        """
        # 1. Doji : |close - open| < 0.1% du range
        body = abs(df['close'] - df['open'])
        candle_range = df['high'] - df['low']
        df['pattern_doji'] = body < (0.001 * candle_range)
        
        # 2. Hammer : lower wick > 2x body, upper wick minimal
        lower_wick = df[['open', 'close']].min(axis=1) - df['low']
        upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
        df['pattern_hammer'] = (lower_wick > 2 * body) & (upper_wick < body)
        
        # 3. Shooting Star : upper wick > 2x body, lower wick minimal
        df['pattern_shooting_star'] = (upper_wick > 2 * body) & (lower_wick < body)
        
        # 4. Bullish Engulfing : green candle englobe red précédente
        prev_open = df['open'].shift(1)
        prev_close = df['close'].shift(1)
        
        # Conditions pour Bullish Engulfing
        current_green = df['close'] > df['open']  # Bougie verte actuelle
        prev_red = prev_close < prev_open         # Bougie rouge précédente
        engulfs = (df['open'] < prev_close) & (df['close'] > prev_open)
        
        df['pattern_bullish_engulfing'] = current_green & prev_red & engulfs
        
        # 5. Bearish Engulfing : red candle englobe green précédente
        current_red = df['close'] < df['open']
        prev_green = prev_close > prev_open
        engulfs_bear = (df['open'] > prev_close) & (df['close'] < prev_open)
        
        df['pattern_bearish_engulfing'] = current_red & prev_green & engulfs_bear
        
        return df
    
    def generate_trading_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Générer des signaux de trading basés sur les indicateurs
        
        Signaux :
        - BUY : Conditions favorables à l'achat
        - SELL : Conditions favorables à la vente
        - HOLD : Neutre
        
        Stratégie combinée :
        1. MACD crossover
        2. RSI oversold/overbought
        3. Prix vs Bollinger Bands
        4. Volume analysis
        
        Args:
            df: DataFrame avec indicateurs
            
        Returns:
            DataFrame avec colonne 'signal'
        """
        # Initialiser les signaux
        df['signal'] = 'HOLD'
        df['signal_strength'] = 0  # Score de -3 à +3
        
        # Signal 1 : MACD Crossover
        # MACD croise Signal vers le haut = BUY
        macd_cross_up = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
        macd_cross_down = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))
        
        df.loc[macd_cross_up, 'signal_strength'] += 1
        df.loc[macd_cross_down, 'signal_strength'] -= 1
        
        # Signal 2 : RSI
        # RSI < 30 = Oversold = BUY
        # RSI > 70 = Overbought = SELL
        df.loc[df['rsi_14'] < 30, 'signal_strength'] += 1
        df.loc[df['rsi_14'] > 70, 'signal_strength'] -= 1
        
        # Signal 3 : Bollinger Bands
        # Prix touche lower band = BUY
        # Prix touche upper band = SELL
        df.loc[df['close'] <= df['bb_lower'], 'signal_strength'] += 1
        df.loc[df['close'] >= df['bb_upper'], 'signal_strength'] -= 1
        
        # Signal 4 : Volume confirmation
        # Volume élevé renforce le signal
        high_volume = df['volume_ratio'] > 1.5
        df.loc[high_volume & (df['signal_strength'] > 0), 'signal_strength'] += 0.5
        df.loc[high_volume & (df['signal_strength'] < 0), 'signal_strength'] -= 0.5
        
        # Convertir score en signal final
        df.loc[df['signal_strength'] >= 2, 'signal'] = 'BUY'
        df.loc[df['signal_strength'] <= -2, 'signal'] = 'SELL'
        
        # Logger les signaux
        buy_signals = (df['signal'] == 'BUY').sum()
        sell_signals = (df['signal'] == 'SELL').sum()
        
        if buy_signals > 0 or sell_signals > 0:
            self.logger.info(f"Signaux générés : {buy_signals} BUY, {sell_signals} SELL")
        
        return df