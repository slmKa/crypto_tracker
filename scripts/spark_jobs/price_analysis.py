"""
Job Spark pour analyser les prix de cryptos
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, avg, max as spark_max, min as spark_min, 
    count, stddev, window, from_json, to_timestamp
)
from pyspark.sql.types import (
    StructType, StructField, StringType, 
    DoubleType, LongType, TimestampType
)
from datetime import datetime

class CryptoPriceAnalyzer:
    """
    Analyseur Spark pour données crypto
    
    Capacités :
    1. Lire depuis Kafka en streaming
    2. Calculer statistiques en temps réel
    3. Détecter anomalies
    4. Sauvegarder résultats
    """
    
    def __init__(self, app_name="CryptoPriceAnalyzer"):
        """
        Initialiser Spark Session
        
        SparkSession = Point d'entrée pour Spark
        """
        self.spark = SparkSession.builder \
            .appName(app_name) \
            .master("spark://spark-master:7077") \
            .config("spark.executor.memory", "2g") \
            .config("spark.executor.cores", "2") \
            .config("spark.sql.shuffle.partitions", "10") \
            .getOrCreate()
        
        # Configurer log level
        self.spark.sparkContext.setLogLevel("WARN")
        
        print(f"✅ Spark Session created: {app_name}")
        print(f"   Spark UI: http://localhost:8081")
    
    def read_from_timescaledb(self, hours=24):
        """
        Lire les données depuis TimescaleDB
        
        Spark peut lire directement depuis PostgreSQL via JDBC
        
        Args:
            hours: Nombre d'heures d'historique
            
        Returns:
            DataFrame Spark
        """
        # JDBC URL
        jdbc_url = "jdbc:postgresql://timescaledb:5432/crypto_db"
        
        # Query SQL
        query = f"""
        (SELECT * FROM tickers 
         WHERE time >= NOW() - INTERVAL '{hours} hours'
         ORDER BY time ASC) AS tickers_data
        """
        
        # Lire avec Spark
        df = self.spark.read \
            .format("jdbc") \
            .option("url", jdbc_url) \
            .option("dbtable", query) \
            .option("user", "crypto_user") \
            .option("password", "crypto_pass") \
            .option("driver", "org.postgresql.Driver") \
            .load()
        
        print(f"✅ Loaded {df.count()} rows from TimescaleDB")
        
        return df
    
    def calculate_statistics(self, df):
        """
        Calculer des statistiques agrégées
        
        Args:
            df: DataFrame Spark avec colonnes [symbol, last, time, ...]
            
        Returns:
            DataFrame avec stats par symbole
        """
        print("📊 Calculating statistics...")
        
        stats_df = df.groupBy("symbol").agg(
            count("last").alias("tick_count"),
            avg("last").alias("avg_price"),
            spark_max("last").alias("max_price"),
            spark_min("last").alias("min_price"),
            stddev("last").alias("price_stddev"),
            avg("volume_24h").alias("avg_volume")
        )
        
        # Ajouter colonnes calculées
        stats_df = stats_df.withColumn(
            "price_range",
            col("max_price") - col("min_price")
        ).withColumn(
            "volatility_pct",
            (col("price_stddev") / col("avg_price")) * 100
        )
        
        return stats_df
    
    def detect_price_anomalies(self, df, threshold=3.0):
        """
        Détecter les anomalies de prix (Z-score)
        
        Anomalie = Prix s'écarte de plus de 3 écarts-types de la moyenne
        
        Args:
            df: DataFrame avec prix
            threshold: Seuil Z-score (défaut: 3.0)
            
        Returns:
            DataFrame avec anomalies
        """
        print("🔍 Detecting price anomalies...")
        
        # Calculer moyenne et écart-type par symbole
        stats = df.groupBy("symbol").agg(
            avg("last").alias("mean_price"),
            stddev("last").alias("std_price")
        )
        
        # Joindre avec données originales
        df_with_stats = df.join(stats, on="symbol")
        
        # Calculer Z-score
        df_with_zscore = df_with_stats.withColumn(
            "z_score",
            (col("last") - col("mean_price")) / col("std_price")
        )
        
        # Filtrer anomalies
        anomalies = df_with_zscore.filter(
            (col("z_score") > threshold) | (col("z_score") < -threshold)
        )
        
        anomaly_count = anomalies.count()
        print(f"🚨 Found {anomaly_count} anomalies")
        
        return anomalies
    
    def windowed_aggregation(self, df, window_duration="1 hour"):
        """
        Agrégation par fenêtres temporelles
        
        Exemple : Calculer OHLC par heure
        
        Args:
            df: DataFrame avec timestamp
            window_duration: Taille de la fenêtre
            
        Returns:
            DataFrame avec agrégations
        """
        print(f"⏱️  Calculating windowed aggregations ({window_duration})...")
        
        # Convertir timestamp en format Spark
        df = df.withColumn("timestamp", to_timestamp(col("time")))
        
        # Agrégation par fenêtre
        windowed_df = df.groupBy(
            window(col("timestamp"), window_duration),
            "symbol"
        ).agg(
            spark_max("last").alias("high"),
            spark_min("last").alias("low"),
            avg("last").alias("avg_price"),
            count("last").alias("tick_count"),
            avg("volume_24h").alias("avg_volume")
        )
        
        # Renommer colonne window
        windowed_df = windowed_df.select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            "symbol",
            "high",
            "low",
            "avg_price",
            "tick_count",
            "avg_volume"
        )
        
        return windowed_df
    
    def calculate_correlation(self, df):
        """
        Calculer la corrélation entre paires de cryptos
        
        Exemple : Corrélation entre BTC et ETH
        
        Args:
            df: DataFrame avec symboles et prix
            
        Returns:
            Matrice de corrélation
        """
        print("🔗 Calculating correlations...")
        
        # Pivoter pour avoir une colonne par symbole
        pivot_df = df.groupBy("time").pivot("symbol").agg(avg("last"))
        
        # Calculer corrélation (nécessite conversion en Pandas pour corr())
        pandas_df = pivot_df.toPandas()
        correlation_matrix = pandas_df.corr()
        
        print("\n📊 Correlation Matrix:")
        print(correlation_matrix)
        
        return correlation_matrix
    
    def save_results(self, df, output_path, mode="overwrite"):
        """
        Sauvegarder les résultats
        
        Formats supportés : Parquet, CSV, JSON
        
        Args:
            df: DataFrame à sauvegarder
            output_path: Chemin de sortie
            mode: 'overwrite', 'append', 'ignore'
        """
        print(f"💾 Saving results to {output_path}...")
        
        # Sauvegarder en Parquet (format optimisé)
        df.write \
            .mode(mode) \
            .parquet(output_path)
        
        print(f"✅ Results saved to {output_path}")
    
    def stop(self):
        """Arrêter Spark Session"""
        print("Stopping Spark Session...")
        self.spark.stop()
        print("✅ Spark Session stopped")


# ============================================================
# JOB BATCH : ANALYSE HISTORIQUE
# ============================================================

def run_batch_analysis():
    """
    Job batch pour analyser l'historique
    """
    print("="*60)
    print("🚀 CRYPTO PRICE ANALYSIS - BATCH MODE")
    print("="*60)
    
    # Initialiser
    analyzer = CryptoPriceAnalyzer(app_name="CryptoBatchAnalysis")
    
    try:
        # 1. Charger les données (dernières 24h)
        print("\n📥 Step 1: Loading data from TimescaleDB...")
        df = analyzer.read_from_timescaledb(hours=24)
        
        # Afficher échantillon
        print("\n📊 Sample data:")
        df.show(5)
        
        # 2. Calculer statistiques globales
        print("\n📊 Step 2: Calculating statistics...")
        stats_df = analyzer.calculate_statistics(df)
        stats_df.show()
        
        # Sauvegarder
        analyzer.save_results(
            stats_df,
            "/opt/spark-data/daily_stats",
            mode="append"
        )
        
        # 3. Détecter anomalies
        print("\n🔍 Step 3: Detecting anomalies...")
        anomalies_df = analyzer.detect_price_anomalies(df, threshold=3.0)
        
        if anomalies_df.count() > 0:
            anomalies_df.select(
                "symbol", "time", "last", "mean_price", "z_score"
            ).show()
            
            # Sauvegarder anomalies
            analyzer.save_results(
                anomalies_df,
                "/opt/spark-data/anomalies",
                mode="append"
            )
        
        # 4. Agrégation horaire
        print("\n⏱️  Step 4: Hourly aggregation...")
        hourly_df = analyzer.windowed_aggregation(df, window_duration="1 hour")
        hourly_df.show(10)
        
        analyzer.save_results(
            hourly_df,
            "/opt/spark-data/hourly_ohlc",
            mode="append"
        )
        
        # 5. Corrélation entre cryptos
        print("\n🔗 Step 5: Calculating correlations...")
        try:
            correlation_matrix = analyzer.calculate_correlation(df)
        except Exception as e:
            print(f"⚠️  Correlation calculation skipped: {e}")
        
        print("\n" + "="*60)
        print("✅ BATCH ANALYSIS COMPLETED")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error during batch analysis: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        analyzer.stop()


# ============================================================
# JOB STREAMING : ANALYSE EN TEMPS RÉEL
# ============================================================

def run_streaming_analysis():
    """
    Job streaming pour analyser Kafka en temps réel
    """
    print("="*60)
    print("🔄 CRYPTO PRICE ANALYSIS - STREAMING MODE")
    print("="*60)
    
    analyzer = CryptoPriceAnalyzer(app_name="CryptoStreamingAnalysis")
    
    try:
        # Définir le schéma des messages Kafka
        schema = StructType([
            StructField("symbol", StringType(), True),
            StructField("exchange", StringType(), True),
            StructField("timestamp", LongType(), True),
            StructField("last", DoubleType(), True),
            StructField("bid", DoubleType(), True),
            StructField("ask", DoubleType(), True),
            StructField("volume_24h", DoubleType(), True)
        ])
        
        # Lire depuis Kafka en streaming
        print("\n📡 Connecting to Kafka...")
        kafka_df = analyzer.spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", "kafka:9092") \
            .option("subscribe", "crypto-prices") \
            .option("startingOffsets", "latest") \
            .load()
        
        # Parser JSON
        parsed_df = kafka_df.selectExpr("CAST(value AS STRING) as json") \
            .select(from_json(col("json"), schema).alias("data")) \
            .select("data.*")
        
        # Convertir timestamp en format Spark
        parsed_df = parsed_df.withColumn(
            "event_time",
            to_timestamp(col("timestamp") / 1000)
        )
        
        # Agrégation en fenêtres glissantes (5 minutes)
        windowed_agg = parsed_df \
            .withWatermark("event_time", "10 minutes") \
            .groupBy(
                window(col("event_time"), "5 minutes", "1 minute"),
                "symbol"
            ).agg(
                count("last").alias("tick_count"),
                avg("last").alias("avg_price"),
                spark_max("last").alias("max_price"),
                spark_min("last").alias("min_price")
            )
        
        # Écrire les résultats en console
        query = windowed_agg.writeStream \
            .outputMode("update") \
            .format("console") \
            .option("truncate", "false") \
            .start()
        
        print("\n✅ Streaming query started")
        print("📊 Aggregating prices in 5-minute windows...")
        print("⏹️  Press Ctrl+C to stop\n")
        
        # Attendre (bloquant)
        query.awaitTermination()
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopping streaming query...")
    except Exception as e:
        print(f"\n❌ Error during streaming: {e}")
        import traceback
        traceback.print_exc()
    finally:
        analyzer.stop()


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Spark Crypto Price Analyzer')
    parser.add_argument(
        '--mode',
        choices=['batch', 'streaming'],
        default='batch',
        help='Analysis mode (batch or streaming)'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'batch':
        run_batch_analysis()
    else:
        run_streaming_analysis()