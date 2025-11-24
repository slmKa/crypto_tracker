"""
Script de test pour vérifier que l'extraction fonctionne
"""
from extractors.binance_extractor import BinanceExtractor
import json

def test_binance_extractor():
    print("🚀 Test de l'extracteur Binance\n")
    
    # Initialiser l'extracteur
    extractor = BinanceExtractor()
    
    # Test 1 : Récupérer le ticker BTC/USDT
    print("📊 Test 1 : Ticker BTC/USDT")
    ticker = extractor.get_ticker("BTC/USDT")
    print(json.dumps(ticker, indent=2))
    print(f"Prix actuel : ${ticker['last']:,.2f}\n")
    
    # Test 2 : Récupérer les OHLCV (dernières 10 bougies de 1h)
    print("📈 Test 2 : OHLCV 1h (10 dernières bougies)")
    ohlcv = extractor.get_ohlcv("BTC/USDT", timeframe="1h", limit=10)
    
    for candle in ohlcv['data'][-5:]:  # Afficher les 5 dernières
        timestamp, open_p, high, low, close, volume = candle
        print(f"  {timestamp} | O:{open_p} H:{high} L:{low} C:{close} V:{volume}")
    
    # Test 3 : Order book
    print("\n📖 Test 3 : Order Book")
    order_book = extractor.get_order_book("BTC/USDT", limit=5)
    
    print("Top 5 Bids (ordres d'achat):")
    for price, qty in order_book['bids'][:5]:
        print(f"  ${price:,.2f} × {qty:.4f} BTC")
    
    print("\nTop 5 Asks (ordres de vente):")
    for price, qty in order_book['asks'][:5]:
        print(f"  ${price:,.2f} × {qty:.4f} BTC")
    
    print("\n✅ Tous les tests ont réussi !")

if __name__ == "__main__":
    test_binance_extractor()