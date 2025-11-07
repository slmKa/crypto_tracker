"""
Consumer Kafka pour consommer les prix en temps réel
(Version Confluent Kafka)
"""
from confluent_kafka import Consumer, KafkaException
import json
from datetime import datetime
from loguru import logger
import sys
import os

# Import des loaders existants
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from loaders.timescale_loader import TimescaleLoader
from loaders.redis_loader import RedisLoader


class CryptoPriceConsumer:
    """
    Consumer Kafka qui lit les prix et les stocke
    Workflow :
    1. Subscribe au topic 'crypto-prices'
    2. Consommer les messages en continu
    3. Stocker dans TimescaleDB + Redis
    4. Publier sur Redis Pub/Sub pour le dashboard
    """

    def __init__(self, kafka_bootstrap_servers='localhost:9093',
                 group_id='crypto-storage-group'):
        self.logger = logger.bind(component="kafka_consumer")

        # Configuration du consumer Confluent Kafka
        conf = {
            'bootstrap.servers': kafka_bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': 'latest',  # latest = lire les nouveaux messages
            'enable.auto.commit': True
        }

        self.consumer = Consumer(conf)
        self.timescale_loader = TimescaleLoader()
        self.redis_loader = RedisLoader()

        self.logger.info("✅ Kafka Consumer initialized (Confluent version)")

    def consume_prices(self, topic='crypto-prices'):
        """Consommer les prix en continu depuis Kafka"""
        self.consumer.subscribe([topic])

        self.logger.info(f"📥 Subscribed to topic: {topic}")
        self.logger.info("🔄 Starting consumption loop (Ctrl+C to stop)...")

        message_count = 0

        try:
            while True:
                msg = self.consumer.poll(1.0)  # Attente max 1s
                if msg is None:
                    continue
                if msg.error():
                    raise KafkaException(msg.error())

                message_count += 1
                key = msg.key().decode('utf-8') if msg.key() else None
                value = json.loads(msg.value().decode('utf-8'))

                self.logger.info(f"📨 [{message_count}] Received {key}")

                # Traiter le message
                self.process_ticker(value)

        except KeyboardInterrupt:
            self.logger.info("⏹️  Stopping consumer...")
        except Exception as e:
            self.logger.error(f"❌ Consumer error: {e}")
        finally:
            self.close()

    def process_ticker(self, ticker: dict):
        """
        Traiter un ticker reçu
        1. Stocker dans TimescaleDB
        2. Cacher dans Redis
        3. Publier sur Redis Pub/Sub
        """
        try:
            symbol = ticker['symbol']
            price = ticker['last']

            # 1️⃣ Stocker dans TimescaleDB
            self.timescale_loader.insert_ticker(ticker)
            self.logger.debug(f"  ✓ Stored in TimescaleDB: {symbol}")

            # 2️⃣ Cacher dans Redis
            self.redis_loader.set_ticker(ticker, ttl=60)
            self.logger.debug(f"  ✓ Cached in Redis: {symbol}")

            # 3️⃣ Publier sur Redis Pub/Sub
            self.redis_loader.publish_ticker('prices', ticker)
            self.logger.debug(f"  ✓ Published to Pub/Sub: {symbol}")

            self.logger.success(f"✅ Processed {symbol}: ${price:,.2f}")

        except Exception as e:
            self.logger.error(f"❌ Error processing ticker {ticker.get('symbol')}: {e}")

    def close(self):
        """Fermer proprement le consumer"""
        self.logger.info("Closing consumer...")
        self.consumer.close()
        self.logger.info("✅ Consumer closed")


# ============================================================
# CONSUMER POUR ALERTES D'ARBITRAGE
# ============================================================

class ArbitrageAlertConsumer:
    """Consumer spécialisé pour les alertes d'arbitrage"""

    def __init__(self, kafka_bootstrap_servers='localhost:9093'):
        self.logger = logger.bind(component="arbitrage_consumer")

        conf = {
            'bootstrap.servers': kafka_bootstrap_servers,
            'group.id': 'arbitrage-alert-group',
            'auto.offset.reset': 'latest'
        }

        self.consumer = Consumer(conf)
        self.consumer.subscribe(['arbitrage-alerts'])

        self.timescale_loader = TimescaleLoader()
        self.redis_loader = RedisLoader()

        self.logger.info("✅ Arbitrage Alert Consumer initialized")

    def consume_alerts(self):
        """Consommer et traiter les alertes d'arbitrage"""
        self.logger.info("🚨 Listening for arbitrage alerts...")

        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    raise KafkaException(msg.error())

                opportunity = json.loads(msg.value().decode('utf-8'))

                self.logger.warning(
                    f"🚨 ARBITRAGE ALERT: {opportunity['symbol']} - "
                    f"{opportunity['spread_percent']:.2f}% spread"
                )

                # Stocker et cacher
                self.timescale_loader.insert_arbitrage_opportunity(opportunity)
                self.redis_loader.set_arbitrage_alert(opportunity, ttl=300)

                # Notification
                self.send_notification(opportunity)

        except KeyboardInterrupt:
            self.logger.info("⏹️  Stopping alerts consumer...")
        finally:
            self.consumer.close()

    def send_notification(self, opportunity: dict):
        """Envoyer notification (placeholder)"""
        self.logger.info(f"📧 Notification sent for {opportunity['symbol']}")


# ============================================================
# SCRIPT D'EXÉCUTION
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Kafka Consumer for Crypto Prices')
    parser.add_argument(
        '--type',
        choices=['prices', 'arbitrage'],
        default='prices',
        help='Type of consumer (prices or arbitrage alerts)'
    )

    args = parser.parse_args()

    if args.type == 'prices':
        consumer = CryptoPriceConsumer(kafka_bootstrap_servers='localhost:9093')
        consumer.consume_prices()
    else:
        consumer = ArbitrageAlertConsumer(kafka_bootstrap_servers='localhost:9093')
        consumer.consume_alerts()
