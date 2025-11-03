"""
Transformer spécialisé pour les données de ticker
"""
from typing import Dict, List
from .base_transformer import BaseTransformer
import pandas as pd

class TickerTransformer(BaseTransformer):
    """
    Transforme les données de ticker (prix actuel)
    
    Input : Données brutes de différents exchanges
    Output : Format unifié + calculs enrichis
    """
    
    def transform(self, raw_data: Dict) -> Dict:
        """
        Transformer un ticker individuel
        
        Args:
            raw_data: Ticker brut d'un exchange
            
        Returns:
            Ticker normalisé et enrichi
        """
        # Normaliser les champs de base
        transformed = {
            'exchange': raw_data.get('exchange', 'unknown'),
            'symbol': self.normalize_symbol(raw_data.get('symbol', '')),
            'timestamp': self.normalize_timestamp(raw_data.get('timestamp')),
            'last': float(raw_data.get('last', 0)),
            'bid': float(raw_data.get('bid', 0)),
            'ask': float(raw_data.get('ask', 0)),
            'high_24h': float(raw_data.get('high', 0)),
            'low_24h': float(raw_data.get('low', 0)),
            'volume_24h': float(raw_data.get('volume', 0)),
            'quote_volume_24h': float(raw_data.get('quoteVolume', 0))
        }
        
        # Enrichissement : Calculer le spread
        if transformed['bid'] and transformed['ask']:
            spread = self.calculate_spread(transformed['bid'], transformed['ask'])
            transformed.update({
                'spread_absolute': spread['absolute'],
                'spread_relative': spread['relative'],
                'mid_price': spread['mid_price']
            })
        
        # Enrichissement : Calculer le changement 24h
        if transformed['high_24h'] and transformed['low_24h']:
            price_range = transformed['high_24h'] - transformed['low_24h']
            current_position = (transformed['last'] - transformed['low_24h']) / price_range
            
            transformed.update({
                'range_24h': price_range,
                'range_position': current_position  # 0 = au plus bas, 1 = au plus haut
            })
        
        return transformed
    
    def transform_batch(self, tickers: List[Dict]) -> pd.DataFrame:
        """
        Transformer plusieurs tickers en DataFrame
        
        Pourquoi DataFrame ?
        - Facilite l'analyse (groupby, filtering)
        - Export facile vers CSV/SQL
        - Calculs vectorisés (rapides)
        
        Args:
            tickers: Liste de tickers bruts
            
        Returns:
            DataFrame avec tous les tickers normalisés
        """
        transformed_list = []
        
        for ticker in tickers:
            try:
                transformed = self.transform(ticker)
                transformed_list.append(transformed)
            except Exception as e:
                self.logger.error(f"Erreur transformation ticker {ticker.get('symbol')}: {e}")
                continue
        
        df = pd.DataFrame(transformed_list)
        
        # Ajouter un index temporel
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('datetime', inplace=True)
        
        return df
    
    def merge_multi_exchange(self, tickers: List[Dict]) -> pd.DataFrame:
        """
        Fusionner les tickers de plusieurs exchanges pour le même symbole
        
        Use case : Comparer les prix BTC/USDT sur Binance, Coinbase, Kraken
        
        Args:
            tickers: Liste de tickers du même symbole sur différents exchanges
            
        Returns:
            DataFrame avec une ligne par exchange + statistiques
        """
        df = self.transform_batch(tickers)
        
        # Vérifier qu'on a bien plusieurs exchanges
        if df['exchange'].nunique() < 2:
            return df
        
        # Calculer les stats agrégées
        summary = {
            'symbol': df['symbol'].iloc[0],
            'timestamp': df['timestamp'].max(),
            'avg_price': df['last'].mean(),
            'min_price': df['last'].min(),
            'max_price': df['last'].max(),
            'price_std': df['last'].std(),
            'exchanges_count': df['exchange'].nunique()
        }
        
        # Détecter opportunités d'arbitrage
        if summary['price_std'] > 0:
            # Spread inter-exchanges
            arbitrage_spread = (summary['max_price'] - summary['min_price']) / summary['min_price'] * 100
            summary['arbitrage_opportunity'] = arbitrage_spread
            
            if arbitrage_spread > 0.5:  # Plus de 0.5% de différence
                min_ex = df.loc[df['last'].idxmin(), 'exchange']
                max_ex = df.loc[df['last'].idxmax(), 'exchange']
                
                summary['arbitrage_buy'] = min_ex
                summary['arbitrage_sell'] = max_ex
                
                self.logger.info(
                    f"🚨 Arbitrage détecté : {summary['symbol']} - "
                    f"Acheter sur {min_ex} à {summary['min_price']:.2f}, "
                    f"vendre sur {max_ex} à {summary['max_price']:.2f} "
                    f"({arbitrage_spread:.2f}% profit)"
                )
        
        return df, summary