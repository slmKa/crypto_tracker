"""
Module de base pour tous les extracteurs
"""
from abc import ABC, abstractmethod
from typing import Dict, List
from loguru import logger
import time

class BaseExtractor(ABC):
    """
    Classe abstraite définissant l'interface pour tous les extracteurs
    
    Pourquoi une classe abstraite ?
    - Forcer tous les extracteurs à implémenter certaines méthodes
    - Garantir une structure cohérente
    """
    
    def __init__(self, exchange_name: str):
        self.exchange_name = exchange_name
        self.logger = logger.bind(exchange=exchange_name)
        
    @abstractmethod
    def get_ticker(self, symbol: str) -> Dict:
        """
        Récupérer le prix actuel d'un symbole
        
        Args:
            symbol: Paire de trading (ex: 'BTC/USDT')
            
        Returns:
            Dict avec les infos du ticker
        """
        pass
    
    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[List]:
        """
        Récupérer les données OHLCV (Open, High, Low, Close, Volume)
        
        Args:
            symbol: Paire de trading
            timeframe: Intervalle ('1m', '5m', '1h', etc.)
            limit: Nombre de bougies à récupérer
            
        Returns:
            Liste de [timestamp, open, high, low, close, volume]
        """
        pass
    
    def retry_request(self, func, max_retries=3, delay=1):
        """
        Réessayer une requête en cas d'échec
        
        Pourquoi ?
        - Les APIs peuvent être temporairement indisponibles
        - Gestion des rate limits (limite de requêtes/seconde)
        """
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))  # Délai exponentiel
                else:
                    raise