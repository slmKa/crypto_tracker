"""
DAG principal pour le pipeline ETL crypto
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import sys
import os

# Ajouter le path des scripts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from extractors.binance_extractor import BinanceExtractor
from transformers.ticker_transformer import TickerTransformer
from transformers.ohlcv_transformer import OHLCVTransformer
from loaders.timescale_loader import TimescaleLoader
from loaders.redis_loader import RedisLoader

# ============================================================
# CONFIGURATION DU DAG
# ============================================================

# Arguments par défaut pour toutes les tâches
default_args = {
    'owner': 'crypto-team',
    'depends_on_past': False,  # Ne pas attendre succès run précédent
    'start_date': days_ago(1),
    'email': ['alert@crypto-tracker.com'],
    'email_on_failure': True,   # Email si échec
    'email_on_retry': False,
    'retries': 3,               # Nombre de tentatives
    'retry_delay': timedelta(minutes=5),  # Délai entre retries
    'retry_exponential_backoff': True,    # Backoff exponentiel
    'max_retry_delay': timedelta(minutes=30)
}

# Définir le DAG
dag = DAG(
    'crypto_etl_pipeline',
    default_args=default_args,
    description='Pipeline ETL pour tracking crypto multi-exchanges',
    schedule_interval='*/5 * * * *',  # Toutes les 5 minutes
    catchup=False,  # Ne pas exécuter les runs passés manqués
    tags=['crypto', 'etl', 'production']
)

# ============================================================
# DÉFINITION DES TÂCHES
# ============================================================

def extract_tickers(**context):
    """
    Tâche 1 : Extraire les tickers de tous les exchanges
    
    context : Dict fourni par Airflow avec métadonnées
              (execution_date, dag_run, etc.)
    """
    print("🔍 Extraction des tickers...")
    
    # Symboles à tracker
    symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT']
    
    # Extraire de Binance
    extractor = BinanceExtractor()
    tickers = []
    
    for symbol in symbols:
        try:
            ticker = extractor.get_ticker(symbol)
            ticker['exchange'] = 'binance'
            tickers.append(ticker)
            print(f"  ✅ {symbol}: ${ticker['last']:,.2f}")
        except Exception as e:
            print(f"  ❌ Erreur {symbol}: {e}")
    
    # Sauvegarder dans XCom (communication inter-tâches)
    context['task_instance'].xcom_push(key='raw_tickers', value=tickers)
    
    print(f"✅ {len(tickers)} tickers extraits")
    return len(tickers)

def transform_tickers(**context):
    """
    Tâche 2 : Transformer les tickers extraits
    """
    print("🔄 Transformation des tickers...")
    
    # Récupérer depuis XCom
    ti = context['task_instance']
    raw_tickers = ti.xcom_pull(key='raw_tickers', task_ids='extract_tickers')
    
    if not raw_tickers:
        raise ValueError("Aucun ticker à transformer")
    
    # Transformer
    transformer = TickerTransformer()
    transformed_tickers = []
    
    for raw in raw_tickers:
        try:
            transformed = transformer.transform(raw)
            transformed_tickers.append(transformed)
        except Exception as e:
            print(f"  ❌ Erreur transformation {raw.get('symbol')}: {e}")
    
    # Détecter arbitrage si plusieurs exchanges (futur)
    # df, summary = transformer.merge_multi_exchange(transformed_tickers)
    
    # Sauvegarder
    ti.xcom_push(key='transformed_tickers', value=transformed_tickers)
    
    print(f"✅ {len(transformed_tickers)} tickers transformés")
    return len(transformed_tickers)

def load_to_timescale(**context):
    """
    Tâche 3 : Charger dans TimescaleDB
    """
    print("💾 Chargement dans TimescaleDB...")
    
    ti = context['task_instance']
    tickers = ti.xcom_pull(key='transformed_tickers', task_ids='transform_tickers')
    
    if not tickers:
        raise ValueError("Aucun ticker à charger")
    
    # Charger en batch
    loader = TimescaleLoader()
    loader.insert_tickers_batch(tickers)
    
    print(f"✅ {len(tickers)} tickers insérés dans TimescaleDB")
    return len(tickers)

def load_to_redis(**context):
    """
    Tâche 4 : Charger dans Redis (cache)
    """
    print("🚀 Chargement dans Redis...")
    
    ti = context['task_instance']
    tickers = ti.xcom_pull(key='transformed_tickers', task_ids='transform_tickers')
    
    if not tickers:
        raise ValueError("Aucun ticker à cacher")
    
    # Cacher avec TTL de 10 minutes
    redis_loader = RedisLoader()
    redis_loader.set_multiple_tickers(tickers, ttl=600)
    
    # Publier sur channel Pub/Sub pour dashboard temps réel
    for ticker in tickers:
        redis_loader.publish_ticker('prices', ticker)
    
    print(f"✅ {len(tickers)} tickers cachés dans Redis")
    return len(tickers)

def extract_ohlcv(**context):
    """
    Tâche 5 : Extraire OHLCV (parallèle aux tickers)
    """
    print("📈 Extraction OHLCV...")
    
    symbols = ['BTC/USDT', 'ETH/USDT']
    timeframe = '1h'
    limit = 100
    
    extractor = BinanceExtractor()
    ohlcv_data = []
    
    for symbol in symbols:
        try:
            data = extractor.get_ohlcv(symbol, timeframe, limit)
            ohlcv_data.append(data)
            print(f"  ✅ {symbol}: {len(data['data'])} bougies")
        except Exception as e:
            print(f"  ❌ Erreur {symbol}: {e}")
    
    ti = context['task_instance']
    ti.xcom_push(key='raw_ohlcv', value=ohlcv_data)
    
    print(f"✅ OHLCV extrait pour {len(ohlcv_data)} symboles")
    return len(ohlcv_data)

def transform_ohlcv(**context):
    """
    Tâche 6 : Transformer OHLCV (calculer indicateurs)
    """
    print("🔄 Transformation OHLCV...")
    
    ti = context['task_instance']
    raw_ohlcv_list = ti.xcom_pull(key='raw_ohlcv', task_ids='extract_ohlcv')
    
    if not raw_ohlcv_list:
        raise ValueError("Aucune donnée OHLCV")
    
    transformer = OHLCVTransformer()
    transformed_dfs = []
    
    for raw_ohlcv in raw_ohlcv_list:
        try:
            # Transformer
            df = transformer.transform(raw_ohlcv)
            
            # Ajouter indicateurs techniques
            df = transformer.add_technical_indicators(df)
            
            # Détecter patterns
            df = transformer.detect_patterns(df)
            
            # Générer signaux
            df = transformer.generate_trading_signals(df)
            
            transformed_dfs.append(df)
            
            symbol = raw_ohlcv['symbol']
            signals = df['signal'].value_counts()
            print(f"  ✅ {symbol}: {len(df)} bougies | Signaux: {signals.to_dict()}")
            
        except Exception as e:
            print(f"  ❌ Erreur transformation: {e}")
    
    # Sérialiser DataFrames pour XCom (convertir en dict)
    serialized = [df.to_dict('records') for df in transformed_dfs]
    ti.xcom_push(key='transformed_ohlcv', value=serialized)
    
    print(f"✅ {len(transformed_dfs)} DataFrames OHLCV transformés")
    return len(transformed_dfs)

def load_ohlcv(**context):
    """
    Tâche 7 : Charger OHLCV dans TimescaleDB
    """
    print("💾 Chargement OHLCV...")
    
    ti = context['task_instance']
    serialized_dfs = ti.xcom_pull(key='transformed_ohlcv', task_ids='transform_ohlcv')
    
    if not serialized_dfs:
        raise ValueError("Aucune donnée OHLCV à charger")
    
    loader = TimescaleLoader()
    
    # Reconvertir en DataFrames et charger
    import pandas as pd
    for data in serialized_dfs:
        df = pd.DataFrame(data)
        
        # Restaurer l'index datetime
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
        
        loader.insert_ohlcv_dataframe(df)
    
    print(f"✅ {len(serialized_dfs)} DataFrames OHLCV chargés")
    return len(serialized_dfs)

def detect_arbitrage(**context):
    """
    Tâche 8 : Détecter opportunités d'arbitrage
    """
    print("🔍 Détection d'arbitrage...")
    
    ti = context['task_instance']
    tickers = ti.xcom_pull(key='transformed_tickers', task_ids='transform_tickers')
    
    if not tickers or len(tickers) < 2:
        print("⚠️  Pas assez de données pour arbitrage")
        return 0
    
    # Grouper par symbole
    from collections import defaultdict
    by_symbol = defaultdict(list)
    
    for ticker in tickers:
        by_symbol[ticker['symbol']].append(ticker)
    
    # Détecter arbitrage
    opportunities = []
    for symbol, symbol_tickers in by_symbol.items():
        if len(symbol_tickers) < 2:
            continue
        
        # Trouver min et max
        prices = [(t['last'], t['exchange']) for t in symbol_tickers]
        prices.sort()
        
        min_price, min_exchange = prices[0]
        max_price, max_exchange = prices[-1]
        
        spread_percent = ((max_price - min_price) / min_price) * 100
        
        # Si spread > 0.3% → opportunité
        if spread_percent > 0.3:
            opportunity = {
                'symbol': symbol,
                'buy_exchange': min_exchange,
                'sell_exchange': max_exchange,
                'buy_price': min_price,
                'sell_price': max_price,
                'spread_percent': spread_percent,
                'potential_profit': max_price - min_price,
                'timestamp': tickers[0]['timestamp']
            }
            
            opportunities.append(opportunity)
            print(f"  🚨 {symbol}: {spread_percent:.2f}% - "
                  f"Acheter sur {min_exchange}, vendre sur {max_exchange}")
    
    # Sauvegarder les opportunités
    if opportunities:
        loader = TimescaleLoader()
        redis_loader = RedisLoader()
        
        for opp in opportunities:
            # Persister dans TimescaleDB
            loader.insert_arbitrage_opportunity(opp)
            
            # Alerter via Redis
            redis_loader.set_arbitrage_alert(opp, ttl=300)
    
    print(f"✅ {len(opportunities)} opportunités d'arbitrage détectées")
    return len(opportunities)

def send_summary_report(**context):
    """
    Tâche 9 : Envoyer rapport récapitulatif
    """
    print("📧 Génération du rapport...")
    
    ti = context['task_instance']
    execution_date = context['execution_date']
    
    # Collecter les métriques
    num_tickers = ti.xcom_pull(key='return_value', task_ids='load_to_timescale')
    num_ohlcv = ti.xcom_pull(key='return_value', task_ids='load_ohlcv')
    num_arbitrage = ti.xcom_pull(key='return_value', task_ids='detect_arbitrage')
    
    report = f"""
    ═══════════════════════════════════════
    📊 CRYPTO ETL PIPELINE - RAPPORT
    ═══════════════════════════════════════
    
    Exécution : {execution_date}
    
    Métriques :
    • Tickers traités : {num_tickers}
    • OHLCV traités : {num_ohlcv}
    • Arbitrages détectés : {num_arbitrage}
    
    Statut : ✅ SUCCESS
    
    ═══════════════════════════════════════
    """
    
    print(report)
    
    # TODO: Envoyer par email / Slack
    # from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
    
    return report

# ============================================================
# DÉFINITION DES DÉPENDANCES (TOPOLOGIE DU DAG)
# ============================================================

# Créer les tâches
task_extract_tickers = PythonOperator(
    task_id='extract_tickers',
    python_callable=extract_tickers,
    provide_context=True,
    dag=dag
)

task_transform_tickers = PythonOperator(
    task_id='transform_tickers',
    python_callable=transform_tickers,
    provide_context=True,
    dag=dag
)

task_load_timescale = PythonOperator(
    task_id='load_to_timescale',
    python_callable=load_to_timescale,
    provide_context=True,
    dag=dag
)

task_load_redis = PythonOperator(
    task_id='load_to_redis',
    python_callable=load_to_redis,
    provide_context=True,
    dag=dag
)

task_extract_ohlcv = PythonOperator(
    task_id='extract_ohlcv',
    python_callable=extract_ohlcv,
    provide_context=True,
    dag=dag
)

task_transform_ohlcv = PythonOperator(
    task_id='transform_ohlcv',
    python_callable=transform_ohlcv,
    provide_context=True,
    dag=dag
)

task_load_ohlcv = PythonOperator(
    task_id='load_ohlcv',
    python_callable=load_ohlcv,
    provide_context=True,
    dag=dag
)

task_detect_arbitrage = PythonOperator(
    task_id='detect_arbitrage',
    python_callable=detect_arbitrage,
    provide_context=True,
    dag=dag
)

task_send_report = PythonOperator(
    task_id='send_summary_report',
    python_callable=send_summary_report,
    provide_context=True,
    dag=dag
)

# Définir les dépendances (ordre d'exécution)
"""
Graphe du DAG :

                    extract_tickers
                           ↓
                    transform_tickers
                        ↙       ↘
          load_to_timescale   load_to_redis
                        ↘       ↙
                    detect_arbitrage
                           ↓
                   send_summary_report

    (En parallèle)
    
    extract_ohlcv
         ↓
    transform_ohlcv
         ↓
    load_ohlcv
         ↓
    send_summary_report
"""

# Pipeline tickers
task_extract_tickers >> task_transform_tickers
task_transform_tickers >> [task_load_timescale, task_load_redis]
[task_load_timescale, task_load_redis] >> task_detect_arbitrage

# Pipeline OHLCV (parallèle)
task_extract_ohlcv >> task_transform_ohlcv >> task_load_ohlcv

# Rapport final (attend tout)
[task_detect_arbitrage, task_load_ohlcv] >> task_send_report