"""
Tests des loaders (TimescaleDB + Redis)
"""
from extractors.binance_extractor import BinanceExtractor
from transformers.ticker_transformer import TickerTransformer
from transformers.ohlcv_transformer import OHLCVTransformer
from loaders.timescale_loader import TimescaleLoader
from loaders.redis_loader import RedisLoader
import time
from datetime import datetime, timedelta


def test_timescale_loader():
    print("=" * 60)
    print("🗄️  TEST 1 : TIMESCALE LOADER")
    print("=" * 60)
    
    # Initialiser
    loader = TimescaleLoader()
    extractor = BinanceExtractor()
    transformer = TickerTransformer()
    
    # Extraire et transformer
    raw_ticker = extractor.get_ticker("BTC/USDT")
    raw_ticker['exchange'] = 'binance'
    
    ticker = transformer.transform(raw_ticker)
    
    # Insérer
    print("\n📥 Insertion ticker...")
    loader.insert_ticker(ticker)
    
    # Vérifier
    print("\n📤 Vérification...")
    df = loader.query_latest_prices("BTC/USDT", limit=5)
    print(df)
    
    print("\n✅ Test TimescaleDB réussi !")

def test_batch_insert():
    print("\n" + "=" * 60)
    print("📦 TEST 2 : BATCH INSERT")
    print("=" * 60)
    
    loader = TimescaleLoader()
    extractor = BinanceExtractor()
    transformer = TickerTransformer()
    
    # Extraire plusieurs fois (simuler stream)
    tickers = []
    for _ in range(10):
        raw = extractor.get_ticker("BTC/USDT")
        raw['exchange'] = 'binance'
        ticker = transformer.transform(raw)
        tickers.append(ticker)
        time.sleep(0.5)  # Attendre 0.5s entre chaque
    
    # Insérer en batch
    print(f"\n📦 Insertion de {len(tickers)} tickers en batch...")
    start = time.time()
    loader.insert_tickers_batch(tickers)
    elapsed = time.time() - start
    
    print(f"⏱️  Temps d'insertion : {elapsed:.3f}s")
    print(f"💨 Vitesse : {len(tickers)/elapsed:.1f} tickers/sec")

def test_ohlcv_insert():
    print("\n" + "=" * 60)
    print("📈 TEST 3 : OHLCV INSERT")
    print("=" * 60)
    
    loader = TimescaleLoader()
    extractor = BinanceExtractor()
    transformer = OHLCVTransformer()
    
    # Extraire OHLCV
    raw_ohlcv = extractor.get_ohlcv("BTC/USDT", timeframe="1h", limit=50)
    
    # Transformer (ajoute indicateurs)
    df = transformer.transform(raw_ohlcv)
    df = transformer.generate_trading_signals(df)
    
    # Insérer
    print(f"\n📥 Insertion de {len(df)} bougies avec indicateurs...")
    loader.insert_ohlcv_dataframe(df)
    
    # Vérifier
    print("\n📤 Vérification...")
    df_check = loader.query_ohlcv("BTC/USDT", "1h", hours=3)
    print(f"Récupéré : {len(df_check)} bougies")
    print(df_check[['close', 'rsi_14', 'signal']].tail())

def test_redis_loader():
    print("\n" + "=" * 60)
    print("🚀 TEST 4 : REDIS LOADER")
    print("=" * 60)
    
    redis_loader = RedisLoader()
    extractor = BinanceExtractor()
    transformer = TickerTransformer()
    
    # Test 1 : Cache simple
    print("\n💾 Test cache...")
    raw = extractor.get_ticker("BTC/USDT")
    raw['exchange'] = 'binance'
    ticker = transformer.transform(raw)
    
    redis_loader.set_ticker(ticker, ttl=30)
    cached = redis_loader.get_ticker('binance', 'BTC/USDT')
    
    print(f"Prix caché : ${cached['last']:,.2f}")
    
    # Test 2 : Batch cache
    print("\n📦 Test batch cache...")
    symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]
    tickers = []
    
    for symbol in symbols:
        raw = extractor.get_ticker(symbol)
        raw['exchange'] = 'binance'
        ticker = transformer.transform(raw)
        tickers.append(ticker)
    
    redis_loader.set_multiple_tickers(tickers, ttl=60)
    print(f"✅ {len(tickers)} tickers cachés")
    
    # Test 3 : Get latest price
    print("\n🔍 Test get latest price...")
    price = redis_loader.get_latest_price("BTC/USDT")
    print(f"Dernier prix BTC : ${price:,.2f}")
    
    # Test 4 : Rate limiting
    print("\n⏱️  Test rate limiting...")
    for i in range(5):
        count = redis_loader.increment_api_call_count('binance')
        print(f"  Appel {count}")
    
    is_limited = redis_loader.check_rate_limit('binance', max_calls=3)
    print(f"Rate limit atteint : {is_limited}")
    
    # Test 5 : Stats
    print("\n📊 Stats Redis :")
    stats = redis_loader.get_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

def test_pub_sub():
    print("\n" + "=" * 60)
    print("📡 TEST 5 : PUB/SUB")
    print("=" * 60)
    
    redis_loader = RedisLoader()
    extractor = BinanceExtractor()
    transformer = TickerTransformer()
    
    print("\n📤 Publishing 5 price updates...")
    
    for i in range(5):
        raw = extractor.get_ticker("BTC/USDT")
        raw['exchange'] = 'binance'
        ticker = transformer.transform(raw)
        
        redis_loader.publish_ticker('prices', ticker)
        print(f"  Published: ${ticker['last']:,.2f}")
        time.sleep(1)
    
    print("\n💡 Tip: Run a subscriber in another terminal:")
    print("   python -c \"from loaders.redis_loader import RedisLoader; "
          "r = RedisLoader(); "
          "r.subscribe_to_channel('prices', lambda d: print(f\\\"Price: {d['last']}\\\"))\"")

def test_continuous_aggregates():
    print("\n" + "=" * 60)
    print("⚙️  TEST 6 : CONTINUOUS AGGREGATES")
    print("=" * 60)
    
    loader = TimescaleLoader()
    
    print("\n🔧 Configuration des agrégats continus...")
    loader.setup_continuous_aggregates()
    
    print("\n📊 Configuration des retention policies...")
    loader.setup_retention_policy('tickers', retention_days=30)
    loader.setup_retention_policy('ohlcv', retention_days=90)
    
    print("\n✅ Configuration avancée terminée !")

if __name__ == "__main__":
    try:
        test_timescale_loader()
        test_batch_insert()
        test_ohlcv_insert()
        test_redis_loader()
        test_pub_sub()
        test_continuous_aggregates()
        
        print("\n" + "=" * 60)
        print("✅ TOUS LES TESTS LOAD ONT RÉUSSI !")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        import traceback
        traceback.print_exc()