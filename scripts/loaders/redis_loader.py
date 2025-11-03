"""
Loader pour Redis (cache temps réel)
"""
import redis
import json
from typing import Dict, Any, Optional
from loguru import logger

class RedisLoader:
    """
    Gestionnaire Redis pour données temps réel
    
    Redis = In-memory data store (stockage en RAM)
    
    Use cases :
    1. Cache : Prix actuels pour dashboard
    2. Pub/Sub : Streaming de prix en temps réel
    3. Rate limiting : Limiter les appels API
    4. Session storage : États utilisateur
    """
    
    def __init__(self, host='redis', port=6379, db=0, 
                 decode_responses=True):
        """
        Initialiser la connexion Redis
        
        Args:
            host: Adresse Redis (redis si Docker)
            port: Port (6379 par défaut)
            db: Numéro de database (0-15)
            decode_responses: Auto-décoder bytes → str
        """
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=decode_responses
        )
        
        self.logger = logger.bind(component="redis_loader")
        
        # Tester la connexion
        try:
            self.client.ping()
            self.logger.info("✅ Connexion Redis établie")
        except redis.ConnectionError as e:
            self.logger.error(f"❌ Erreur connexion Redis : {e}")
            raise
    
    def set_ticker(self, ticker: Dict, ttl: int = 60):
        """
        Stocker un ticker dans Redis avec expiration
        
        Key pattern : ticker:{exchange}:{symbol}
        
        TTL (Time To Live) : Durée de vie de la clé
        → Après TTL secondes, Redis supprime automatiquement
        
        Args:
            ticker: Dict avec données ticker
            ttl: Durée de vie en secondes (défaut: 60s)
        """
        key = f"ticker:{ticker['exchange']}:{ticker['symbol']}"
        
        # Sérialiser en JSON
        value = json.dumps(ticker)
        
        # Stocker avec expiration
        self.client.setex(key, ttl, value)
        
        self.logger.debug(f"Ticker cached : {key} (TTL: {ttl}s)")
    
    def get_ticker(self, exchange: str, symbol: str) -> Optional[Dict]:
        """
        Récupérer un ticker depuis le cache
        
        Args:
            exchange: Nom de l'exchange
            symbol: Symbole de la paire
            
        Returns:
            Dict avec ticker ou None si expiré/inexistant
        """
        key = f"ticker:{exchange}:{symbol}"
        value = self.client.get(key)
        
        if value:
            return json.loads(value)
        return None
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Récupérer le dernier prix connu (multi-exchange)
        
        Cherche sur tous les exchanges et retourne le plus récent
        
        Args:
            symbol: Symbole (ex: 'BTC/USDT')
            
        Returns:
            Prix le plus récent ou None
        """
        # Pattern matching : tous les tickers de ce symbole
        pattern = f"ticker:*:{symbol}"
        keys = self.client.keys(pattern)
        
        if not keys:
            return None
        
        # Récupérer tous les tickers
        tickers = []
        for key in keys:
            value = self.client.get(key)
            if value:
                ticker = json.loads(value)
                tickers.append(ticker)
        
        # Trier par timestamp (plus récent en premier)
        tickers.sort(key=lambda t: t['timestamp'], reverse=True)
        
        return tickers[0]['last'] if tickers else None
    
    def set_multiple_tickers(self, tickers: list, ttl: int = 60):
        """
        Stocker plusieurs tickers en batch (pipeline)
        
        Pipeline Redis : Grouper plusieurs commandes en une seule
        → Beaucoup plus rapide que des SET individuels
        
        Args:
            tickers: Liste de dicts ticker
            ttl: Durée de vie
        """
        pipe = self.client.pipeline()
        
        for ticker in tickers:
            key = f"ticker:{ticker['exchange']}:{ticker['symbol']}"
            value = json.dumps(ticker)
            pipe.setex(key, ttl, value)
        
        pipe.execute()
        self.logger.info(f"✅ {len(tickers)} tickers cached en batch")
    
    def publish_ticker(self, channel: str, ticker: Dict):
        """
        Publier un ticker sur un channel Pub/Sub
        
        Pub/Sub = Pattern publisher/subscriber
        - Publisher : Envoie des messages sur un channel
        - Subscribers : Reçoivent tous les messages du channel
        
        Use case : Dashboard temps réel
        → Backend publie les prix
        → Frontend subscribe et met à jour l'UI
        
        Args:
            channel: Nom du channel (ex: 'prices')
            ticker: Données à publier
        """
        message = json.dumps(ticker)
        num_subscribers = self.client.publish(channel, message)
        
        self.logger.debug(
            f"Message publié sur {channel} → {num_subscribers} subscribers"
        )
    
    def subscribe_to_channel(self, channel: str, callback):
        """
        S'abonner à un channel et exécuter callback à chaque message
        
        Args:
            channel: Channel à écouter
            callback: Fonction à appeler (prend message en param)
        """
        pubsub = self.client.pubsub()
        pubsub.subscribe(channel)
        
        self.logger.info(f"📡 Subscribed to channel: {channel}")
        
        for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                callback(data)
    
    def set_arbitrage_alert(self, opportunity: Dict, ttl: int = 300):
        """
        Stocker une alerte d'arbitrage
        
        Key pattern : arbitrage:{symbol}:{timestamp}
        
        Args:
            opportunity: Dict avec détails arbitrage
            ttl: Durée de vie (5 min par défaut)
        """
        timestamp = int(opportunity.get('timestamp', 0))
        key = f"arbitrage:{opportunity['symbol']}:{timestamp}"
        
        value = json.dumps(opportunity)
        self.client.setex(key, ttl, value)
        
        # Ajouter à une sorted set pour classement par spread
        self.client.zadd(
            'arbitrage:rankings',
            {key: opportunity['spread_percent']}
        )
        
        self.logger.info(f"🚨 Alerte arbitrage : {opportunity['symbol']}")
    
    def get_top_arbitrage_opportunities(self, limit: int = 10) -> list:
        """
        Récupérer les meilleures opportunités d'arbitrage
        
        Utilise Sorted Set pour tri automatique par spread
        
        Args:
            limit: Nombre d'opportunités à retourner
            
        Returns:
            Liste des meilleures opportunités
        """
        # Récupérer les clés avec les meilleurs spreads
        keys = self.client.zrevrange('arbitrage:rankings', 0, limit - 1)
        
        opportunities = []
        for key in keys:
            value = self.client.get(key)
            if value:
                opportunities.append(json.loads(value))
        
        return opportunities
    
    def increment_api_call_count(self, api_name: str, ttl: int = 3600) -> int:
        """
        Incrémenter le compteur d'appels API (rate limiting)
        
        Use case : Limiter à 100 appels/heure par API
        
        Args:
            api_name: Nom de l'API (ex: 'binance')
            ttl: Fenêtre de temps (1h = 3600s)
            
        Returns:
            Nombre d'appels actuel
        """
        key = f"api_calls:{api_name}"
        
        # Incrémenter
        count = self.client.incr(key)
        
        # Définir expiration seulement au premier appel
        if count == 1:
            self.client.expire(key, ttl)
        
        return count
    
    def check_rate_limit(self, api_name: str, max_calls: int = 100) -> bool:
        """
        Vérifier si limite d'appels API atteinte
        
        Args:
            api_name: Nom de l'API
            max_calls: Limite d'appels
            
        Returns:
            True si limite atteinte
        """
        key = f"api_calls:{api_name}"
        count = self.client.get(key)
        
        if count and int(count) >= max_calls:
            ttl = self.client.ttl(key)
            self.logger.warning(
                f"⚠️ Rate limit atteint pour {api_name} "
                f"({count}/{max_calls}). Réessayer dans {ttl}s"
            )
            return True
        
        return False
    
    def cache_query_result(self, query_hash: str, result: Any, ttl: int = 300):
        """
        Cacher le résultat d'une requête SQL
        
        Use case : Dashboard affiche même graphique plusieurs fois
        → Éviter de refaire la requête SQL à chaque fois
        
        Args:
            query_hash: Hash unique de la requête
            result: Résultat à cacher (sérialisable en JSON)
            ttl: Durée de vie du cache
        """
        key = f"query_cache:{query_hash}"
        value = json.dumps(result, default=str)  # default=str pour datetime
        
        self.client.setex(key, ttl, value)
        self.logger.debug(f"Query cached : {query_hash[:16]}... (TTL: {ttl}s)")
    
    def get_cached_query(self, query_hash: str) -> Optional[Any]:
        """
        Récupérer résultat d'une requête depuis le cache
        
        Args:
            query_hash: Hash de la requête
            
        Returns:
            Résultat caché ou None
        """
        key = f"query_cache:{query_hash}"
        value = self.client.get(key)
        
        if value:
            self.logger.debug(f"Cache hit : {query_hash[:16]}...")
            return json.loads(value)
        
        self.logger.debug(f"Cache miss : {query_hash[:16]}...")
        return None
    
    def flush_db(self):
        """
        Vider toute la base Redis (ATTENTION : destructif)
        
        Utile pour :
        - Reset pendant développement
        - Nettoyage de test
        """
        self.client.flushdb()
        self.logger.warning("⚠️ Redis database flushed")
    
    def get_stats(self) -> Dict:
        """
        Récupérer les statistiques Redis
        
        Returns:
            Dict avec métriques
        """
        info = self.client.info()
        
        return {
            'total_keys': self.client.dbsize(),
            'memory_used_mb': info['used_memory'] / 1024 / 1024,
            'connected_clients': info['connected_clients'],
            'uptime_seconds': info['uptime_in_seconds'],
            'hit_rate': info.get('keyspace_hits', 0) / max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 1), 1)
        }
