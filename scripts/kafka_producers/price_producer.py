"""
Producer Kafka pour publier les prix en temps réel
(Version mise à jour pour utiliser confluent-kafka)
"""

from confluent_kafka import Producer
import json
import time
from datetime import datetime
from loguru import logger
import sys
import os

# Imports des extractors existants
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from extractors.binance_extractor import BinanceExtractor
from transformers.ticker_transformer import TickerTransformer


class CryptoPriceProducer:
    """
    Producer Kafka qui publie les prix de cryptos en temps réel

    Workflow :
    1. Extraire prix depuis Binance (toutes les secondes)
    2. Transformer les données
    3. Publier sur Kafka topic 'crypto-prices'
    """

    def __init__(self, kafka_bootstrap_servers='localhost:9092'):
        """
        Initialiser le producer Kafka (Confluent client)
        Args:
            kafka_bootstrap_servers: Adresse du broker Kafka
        """
        self.logger = logger.bind(component="kafka_producer")

        # Initialiser le producer Confluent Kafka
        self.producer = Producer({
            'bootstrap.servers': kafka_bootstrap_servers,
            'compression.type': 'gzip',      # Compression
            'acks': 'all',                   # Attente de confirmation
            'retries': 3,                    # Tentatives en cas d’échec
            'linger.ms': 10,                 # Attente batch
            'batch.size': 16384,             # 16KB
        })

        # Initialiser extractor et transformer
        self.extractor = BinanceExtractor()
        self.transformer = TickerTransformer()

        self.logger.info("✅ Kafka Producer initialized (Confluent)")

    def delivery_report(self, err, msg):
        """
        Callback appelé à la livraison du message
        """
        if err is not None:
            self.logger.error(f"❌ Delivery failed: {err}")
        else:
            self.logger.info(
                f"✅ Message delivered to {msg.topic()} "
                f"[partition={msg.partition()}] offset={msg.offset()}"
            )

    def publish_ticker(self, symbol: str, topic='crypto-prices'):
        """
        Extraire et publier le ticker d'un symbole
        Args:
            symbol: Symbole crypto (ex: 'BTC/USDT')
            topic: Kafka topic où publier
        """
        try:
            # 1. Extraire depuis Binance
            raw_ticker = self.extractor.get_ticker(symbol)
            raw_ticker['exchange'] = 'binance'

            # 2. Transformer les données
            ticker = self.transformer.transform(raw_ticker)

            # 3. Ajouter métadonnées
            ticker['published_at'] = datetime.now().isoformat()
            ticker['producer'] = 'crypto-price-producer'

            # 4. Publier sur Kafka
            self.producer.produce(
                topic=topic,
                key=symbol.encode('utf-8'),
                value=json.dumps(ticker).encode('utf-8'),
                callback=self.delivery_report
            )

            # Poll pour exécuter les callbacks
            self.producer.poll(0)

        except Exception as e:
            self.logger.error(f"❌ Error publishing {symbol}: {e}")

    def publish_multiple(self, symbols: list, topic='crypto-prices', interval=1):
        """
        Publier plusieurs symboles en continu
        Args:
            symbols: Liste de symboles
            topic: Kafka topic
            interval: Délai entre publications (secondes)
        """
        self.logger.info(f"🚀 Starting continuous publishing for {len(symbols)} symbols")

        try:
            while True:
                for symbol in symbols:
                    try:
                        self.publish_ticker(symbol, topic)
                    except Exception as e:
                        self.logger.error(f"Error with {symbol}: {e}")
                        continue

                # Attendre avant le prochain cycle
                time.sleep(interval)

        except KeyboardInterrupt:
            self.logger.info("⏹️  Stopping producer...")
            self.close()

    def publish_arbitrage_alert(self, opportunity: dict, topic='arbitrage-alerts'):
        """
        Publier une alerte d'arbitrage
        Args:
            opportunity: Dict avec détails de l'opportunité
            topic: Kafka topic pour alertes
        """
        try:
            opportunity['alert_time'] = datetime.now().isoformat()

            self.producer.produce(
                topic=topic,
                key=opportunity['symbol'].encode('utf-8'),
                value=json.dumps(opportunity).encode('utf-8'),
                callback=self.delivery_report
            )
            self.producer.poll(0)

            self.logger.warning(
                f"🚨 ARBITRAGE ALERT: {opportunity['symbol']} - "
                f"{opportunity.get('spread_percent', 0):.2f}% spread"
            )

        except Exception as e:
            self.logger.error(f"Error publishing arbitrage alert: {e}")

    def close(self):
        """
        Fermer proprement le producer
        """
        self.logger.info("Flushing remaining messages...")
        self.producer.flush()  # Envoie tous les messages en attente
        self.logger.info("✅ Producer closed")


# ============================================================
# SCRIPT D'EXÉCUTION
# ============================================================
if __name__ == "__main__":
    # Symboles à tracker
    SYMBOLS = [
        'BTC/USDT',
        'ETH/USDT',
        'BNB/USDT',
        'SOL/USDT',
        'ADA/USDT'
    ]

    # Initialiser le producer
    producer = CryptoPriceProducer(kafka_bootstrap_servers='localhost:9092')

    try:
        # Mode 1 : Publier une fois (batch unique)
        print("📊 Publishing single batch...")
        for symbol in SYMBOLS:
            producer.publish_ticker(symbol)

        print("\n" + "=" * 60)
        print("✅ Single batch published successfully!")
        print("=" * 60)

        # Mode 2 : Streaming continu (décommenter pour activer)
        # print("\n🔄 Starting continuous streaming (Ctrl+C to stop)...")
        # producer.publish_multiple(SYMBOLS, interval=2)

    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")

    finally:
        producer.close()
