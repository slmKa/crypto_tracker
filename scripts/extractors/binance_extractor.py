"""
Extracteur pour Binance (plus gros exchange crypto au monde)
"""
import ccxt
from typing import Dict, List
from .base_extractor import BaseExtractor

class BinanceExtractor(BaseExtractor):
    """
    Extracteur spécialisé pour Binance
    
    Utilise la bibliothèque CCXT qui unifie les APIs de tous les exchanges
    """
    
    def __init__(self):
        super().__init__("binance")
        
        # Initialiser le client CCXT
        self.exchange = ccxt.binance({
            'enableRateLimit': True,  # Respecter les rate limits
            'options': {
                'defaultType': 'spot'  # Trading spot (pas futures)
            }
        })
        
    def get_ticker(self, symbol: str) -> Dict:
        """
        Récupérer le prix actuel + infos du ticker
        
        Exemple de réponse :
        {
            'symbol': 'BTC/USDT',
            'timestamp': 1234567890,
            'datetime': '2024-01-01T00:00:00.000Z',
            'high': 51000.00,
            'low': 49000.00,
            'bid': 50100.00,  # Prix d'achat
            'ask': 50150.00,  # Prix de vente
            'last': 50123.45, # Dernier prix tradé
            'volume': 12345.67
        }
        """
        def _fetch():
            return self.exchange.fetch_ticker(symbol)
        
        return self.retry_request(_fetch)
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[List]:
        """
        Récupérer les bougies OHLCV
        
        OHLCV = Open, High, Low, Close, Volume
        
        Exemple de réponse (une bougie) :
        [
            1609459200000,  # Timestamp (millisecondes)
            29000.00,       # Open (prix d'ouverture)
            29500.00,       # High (prix max)
            28800.00,       # Low (prix min)
            29200.00,       # Close (prix de clôture)
            1234.56         # Volume
        ]
        """
        def _fetch():
            return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        ohlcv = self.retry_request(_fetch)
        
        # Ajouter des métadonnées
        return {
            'exchange': self.exchange_name,
            'symbol': symbol,
            'timeframe': timeframe,
            'data': ohlcv
        }
    
    def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """
        Récupérer le carnet d'ordres (order book)
        
        Order book = Liste des ordres d'achat/vente en attente
        
        Structure :
        {
            'bids': [[50000, 1.5], [49990, 2.0]],  # [prix, quantité]
            'asks': [[50100, 1.2], [50110, 1.8]]
        }
        
        Utilité :
        - Voir la profondeur du marché
        - Détecter les murs d'achat/vente
        """
        def _fetch():
            return self.exchange.fetch_order_book(symbol, limit)
        
        return self.retry_request(_fetch)