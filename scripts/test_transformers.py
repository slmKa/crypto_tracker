"""
Tests complets des transformers
"""
from extractors.binance_extractor import BinanceExtractor
from transformers.ticker_transformer import TickerTransformer
from transformers.ohlcv_transformer import OHLCVTransformer
import json

def test_ticker_transformer():
    print("=" * 60)
    print("🎯 TEST 1 : TICKER TRANSFORMER")
    print("=" * 60)
    
    # Extraire données
    extractor = BinanceExtractor()
    ticker = extractor.get_ticker("BTC/USDT")
    ticker['exchange'] = 'binance'  # Ajouter le nom de l'exchange
    
    print("\n📥 Données brutes :")
    print(json.dumps(ticker, indent=2, default=str))
    
    # Transformer
    transformer = TickerTransformer()
    transformed = transformer.transform(ticker)
    
    print("\n✨ Données transformées :")
    print(json.dumps(transformed, indent=2, default=str))
    
    print("\n📊 Enrichissements calculés :")
    print(f"  - Spread absolu : ${transformed.get('spread_absolute', 0):.2f}")
    print(f"  - Spread relatif : {transformed.get('spread_relative', 0):.4f}%")
    print(f"  - Prix moyen (mid) : ${transformed.get('mid_price', 0):.2f}")
    print(f"  - Position dans range 24h : {transformed.get('range_position', 0):.2%}")

def test_multi_exchange():
    print("\n" + "=" * 60)
    print("🌐 TEST 2 : MULTI-EXCHANGE COMPARISON")
    print("=" * 60)
    
    # Simuler données de plusieurs exchanges
    # (Dans la vraie vie, on extrairait de Binance, Coinbase, Kraken)
    extractor = BinanceExtractor()
    ticker = extractor.get_ticker("BTC/USDT")
    
    # Simuler 3 exchanges avec des prix légèrement différents
    tickers = [
        {**ticker, 'exchange': 'binance', 'last': ticker['last']},
        {**ticker, 'exchange': 'coinbase', 'last': ticker['last'] * 1.002},  # +0.2%
        {**ticker, 'exchange': 'kraken', 'last': ticker['last'] * 0.998}     # -0.2%
    ]
    
    transformer = TickerTransformer()
    df, summary = transformer.merge_multi_exchange(tickers)
    
    print("\n📊 Comparaison par exchange :")
    print(df[['exchange', 'last', 'bid', 'ask', 'spread_relative']])
    
    print("\n📈 Résumé agrégé :")
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
    
    if 'arbitrage_opportunity' in summary:
        print(f"\n🚨 OPPORTUNITÉ D'ARBITRAGE : {summary['arbitrage_opportunity']:.3f}%")
        print(f"   Stratégie : Acheter sur {summary['arbitrage_buy']}")
        print(f"               Vendre sur {summary['arbitrage_sell']}")

def test_ohlcv_transformer():
    print("\n" + "=" * 60)
    print("📈 TEST 3 : OHLCV TRANSFORMER")
    print("=" * 60)
    
    # Extraire OHLCV
    extractor = BinanceExtractor()
    ohlcv = extractor.get_ohlcv("BTC/USDT", timeframe="1h", limit=100)
    
    # Transformer
    transformer = OHLCVTransformer()
    df = transformer.transform(ohlcv)
    
    print(f"\n📊 Dataset : {len(df)} bougies chargées")
    print(f"   Période : {df.index[0]} → {df.index[-1]}")
    
    # Afficher les dernières bougies avec indicateurs
    print("\n🕯️ Dernières bougies avec indicateurs :")
    columns = ['close', 'sma_20', 'ema_12', 'rsi_14', 'macd', 'volume_ratio']
    print(df[columns].tail(10).to_string())
    
    # Détecter patterns
    df = transformer.detect_patterns(df)
    
    print("\n🔍 Patterns détectés (dernières 20 bougies) :")
    pattern_cols = [col for col in df.columns if col.startswith('pattern_')]
    patterns = df[pattern_cols].tail(20)
    
    for pattern_col in pattern_cols:
        count = patterns[pattern_col].sum()
        if count > 0:
            print(f"  - {pattern_col}: {count} occurrence(s)")
    
    # Générer signaux
    df = transformer.generate_trading_signals(df)
    
    print("\n📡 Signaux de trading (dernières 10 bougies) :")
    signal_df = df[['close', 'signal', 'signal_strength']].tail(10)
    print(signal_df.to_string())
    
    # Compter les signaux
    signal_counts = df['signal'].value_counts()
    print("\n📊 Distribution des signaux sur toute la période :")
    for signal, count in signal_counts.items():
        print(f"  {signal}: {count} ({count/len(df)*100:.1f}%)")
    
    # Identifier le dernier signal fort
    last_signals = df[df['signal'] != 'HOLD'].tail(5)
    if not last_signals.empty:
        print("\n⚡ Derniers signaux forts :")
        for idx, row in last_signals.iterrows():
            print(f"  {idx}: {row['signal']} (force: {row['signal_strength']:.1f})")
            print(f"     Prix: ${row['close']:.2f} | RSI: {row['rsi_14']:.1f}")

def test_outliers():
    print("\n" + "=" * 60)
    print("🚨 TEST 4 : DÉTECTION D'OUTLIERS")
    print("=" * 60)
    
    # Créer des données avec outliers
    import numpy as np
    
    normal_prices = [50000 + np.random.normal(0, 500) for _ in range(100)]
    prices_with_outliers = normal_prices + [75000, 25000]  # Ajouter outliers
    
    transformer = TickerTransformer()
    outliers = transformer.detect_outliers(prices_with_outliers, threshold=3.0)
    
    print(f"\n📊 Dataset : {len(prices_with_outliers)} prix")
    print(f"   Moyenne : ${np.mean(prices_with_outliers):,.2f}")
    print(f"   Écart-type : ${np.std(prices_with_outliers):,.2f}")
    
    print(f"\n🚨 Outliers détectés : {len(outliers)}")
    for idx in outliers:
        print(f"   Index {idx}: ${prices_with_outliers[idx]:,.2f}")

if __name__ == "__main__":
    try:
        test_ticker_transformer()
        test_multi_exchange()
        test_ohlcv_transformer()
        test_outliers()
        
        print("\n" + "=" * 60)
        print("✅ TOUS LES TESTS ONT RÉUSSI !")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        import traceback
        traceback.print_exc()