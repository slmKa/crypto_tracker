"""
Classe de base pour tous les transformers
"""
from abc import ABC, abstractmethod
from typing import Dict, List
from datetime import datetime
import pandas as pd
from loguru import logger

class BaseTransformer(ABC):
    """
    Transformer de base avec méthodes communes
    
    Responsabilités :
    - Normaliser les formats
    - Valider les données
    - Calculer des métriques dérivées
    """
    
    def __init__(self):
        self.logger = logger.bind(component="transformer")
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        Uniformiser le format des symboles
        
        Exemples :
        - 'BTCUSDT' → 'BTC/USDT'
        - 'BTC-USD' → 'BTC/USD'
        - 'XBT/USD' → 'BTC/USD' (Kraken utilise XBT pour Bitcoin)
        
        Args:
            symbol: Symbole brut
            
        Returns:
            Symbole normalisé au format 'BASE/QUOTE'
        """
        # Remplacer les séparateurs par '/'
        symbol = symbol.replace('-', '/').replace('_', '/')
        
        # Si pas de séparateur, insérer '/' au milieu (ex: BTCUSDT)
        if '/' not in symbol:
            # Heuristique : les 3-4 premiers caractères = base
            if len(symbol) >= 6:
                base = symbol[:3] if symbol[:3] != 'USDT' else symbol[:4]
                quote = symbol[len(base):]
                symbol = f"{base}/{quote}"
        
        # Normaliser les symboles spéciaux
        replacements = {
            'XBT': 'BTC',  # Kraken utilise XBT
            'USDT': 'USDT',
            'USD': 'USD'
        }
        
        base, quote = symbol.split('/')
        base = replacements.get(base, base)
        quote = replacements.get(quote, quote)
        
        return f"{base}/{quote}"
    
    def normalize_timestamp(self, timestamp) -> int:
        """
        Convertir tous les timestamps en millisecondes Unix
        
        Formats supportés :
        - Millisecondes : 1704067200000
        - Secondes : 1704067200
        - ISO string : '2024-01-01T00:00:00Z'
        
        Args:
            timestamp: Timestamp dans n'importe quel format
            
        Returns:
            Timestamp en millisecondes (int)
        """
        # Si c'est déjà un int
        if isinstance(timestamp, int):
            # Détecter si c'est en secondes (< 10 milliards)
            if timestamp < 10_000_000_000:
                return timestamp * 1000
            return timestamp
        
        # Si c'est un float
        if isinstance(timestamp, float):
            return int(timestamp * 1000) if timestamp < 10_000_000_000 else int(timestamp)
        
        # Si c'est une string ISO
        if isinstance(timestamp, str):
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        
        raise ValueError(f"Format de timestamp non supporté : {type(timestamp)}")
    
    def validate_price_data(self, data: Dict) -> bool:
        """
        Vérifier la cohérence des données de prix
        
        Validations :
        1. Prix > 0
        2. High >= Low
        3. High >= Open, Close
        4. Low <= Open, Close
        5. Volume >= 0
        
        Args:
            data: Dictionnaire avec les prix
            
        Returns:
            True si valide, False sinon
        """
        try:
            # Vérifier présence des champs obligatoires
            required = ['open', 'high', 'low', 'close', 'volume']
            if not all(k in data for k in required):
                self.logger.warning(f"Champs manquants : {set(required) - set(data.keys())}")
                return False
            
            # Extraire les valeurs
            o, h, l, c, v = data['open'], data['high'], data['low'], data['close'], data['volume']
            
            # Validation 1 : Prix positifs
            if any(x <= 0 for x in [o, h, l, c]):
                self.logger.warning("Prix négatif ou nul détecté")
                return False
            
            # Validation 2 : High >= Low
            if h < l:
                self.logger.warning(f"Incohérence : High ({h}) < Low ({l})")
                return False
            
            # Validation 3 & 4 : High/Low encadrent Open/Close
            if h < max(o, c) or l > min(o, c):
                self.logger.warning("Open/Close hors de la range High/Low")
                return False
            
            # Validation 5 : Volume positif
            if v < 0:
                self.logger.warning("Volume négatif")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur validation : {e}")
            return False
    
    def calculate_spread(self, bid: float, ask: float) -> Dict:
        """
        Calculer le spread (écart bid/ask)
        
        Spread = Différence entre prix d'achat et de vente
        
        Exemple :
        - Bid (achat) : 50,000$
        - Ask (vente) : 50,100$
        - Spread absolu : 100$
        - Spread relatif : 0.2%
        
        Args:
            bid: Prix d'achat (buy price)
            ask: Prix de vente (sell price)
            
        Returns:
            Dict avec spread absolu et relatif
        """
        absolute_spread = ask - bid
        relative_spread = (absolute_spread / bid) * 100  # En pourcentage
        
        return {
            'absolute': absolute_spread,
            'relative': relative_spread,
            'mid_price': (bid + ask) / 2  # Prix moyen
        }
    
    def detect_outliers(self, prices: List[float], threshold: float = 3.0) -> List[int]:
        """
        Détecter les valeurs aberrantes (outliers)
        
        Méthode : Z-score
        - Calculer la moyenne et l'écart-type
        - Si |valeur - moyenne| > threshold * écart-type → outlier
        
        Pourquoi ?
        - Filtrer les erreurs de données
        - Détecter les flash crashes
        
        Args:
            prices: Liste de prix
            threshold: Seuil en nombre d'écarts-types (défaut: 3)
            
        Returns:
            Indices des outliers
        """
        if len(prices) < 3:
            return []
        
        # Convertir en pandas Series pour faciliter
        series = pd.Series(prices)
        
        # Calculer moyenne et écart-type
        mean = series.mean()
        std = series.std()
        
        if std == 0:  # Si tous les prix sont identiques
            return []
        
        # Z-score = (valeur - moyenne) / écart-type
        z_scores = (series - mean) / std
        
        # Indices où |z-score| > threshold
        outliers = z_scores[abs(z_scores) > threshold].index.tolist()
        
        if outliers:
            self.logger.warning(f"Détecté {len(outliers)} outliers : indices {outliers}")
        
        return outliers

    @abstractmethod
    def transform(self, raw_data: Dict) -> Dict:
        """
        Méthode principale de transformation
        À implémenter par les sous-classes
        """
        pass