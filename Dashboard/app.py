"""
Dashboard principal Crypto Tracker
Point d'entrée de l'application Streamlit
"""



import streamlit as st
import sys
import os
import pandas as pd
import numpy as np  # ✅ AJOUT ICI
from datetime import datetime
from dotenv import load_dotenv
import os


print("TimescaleDB host:", os.getenv("TIMESCALE_DB_HOST"))
print("Redis host:", os.getenv("REDIS_HOST"))


# Configuration de la page (doit être la 1ère commande Streamlit)
st.set_page_config(
    page_title="Crypto Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ajouter le path des utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'components'))

from data_loader import DataLoader
from metrics import display_price_card, display_market_summary, display_arbitrage_alert
from charts import plot_price_chart, plot_volume_distribution

# ============================================================
# INITIALISATION
# ============================================================

@st.cache_resource
def init_data_loader():
    """Initialiser le data loader (une seule fois par session)"""
    return DataLoader()

loader = init_data_loader()

# Liste des cryptos à tracker
CRYPTO_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT', 'XRP/USDT']
# ============================================================
# SIDEBAR (Barre latérale)
# ============================================================

with st.sidebar:
    st.title("📊 Crypto Tracker")
    st.markdown("---")
    
    # Sélection du symbole
    selected_symbol = st.selectbox(
        "Select Cryptocurrency",
        CRYPTO_SYMBOLS,
        index=0  # BTC par défaut
    )
    
    # Période d'historique
    time_period = st.selectbox(
        "Time Period",
        options=[1, 6, 12, 24, 48, 168],  # Heures
        format_func=lambda x: f"{x}h" if x < 24 else f"{x//24}d",
        index=3  # 24h par défaut
    )
    
    # Bouton refresh manuel
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()  # Vider le cache
        st.rerun()  # Recharger l'app
    
    st.markdown("---")
    
    # Informations système
    st.caption("Last Update")
    st.caption(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    st.markdown("---")
    
    # Liens utiles
    st.markdown("### 🔗 Quick Links")
    st.markdown("- [Binance](https://www.binance.com)")
    st.markdown("- [CoinGecko](https://www.coingecko.com)")
    st.markdown("- [TradingView](https://www.tradingview.com)")

# ============================================================
# MAIN CONTENT
# ============================================================

# Titre principal
st.title("📊 Crypto Market Overview")
st.markdown("Real-time cryptocurrency tracking and analysis")

# Charger les données
with st.spinner("Loading market data..."):
    latest_prices = loader.get_latest_prices(CRYPTO_SYMBOLS)
    market_summary = loader.get_latest_prices(CRYPTO_SYMBOLS)
    arbitrage_opps = loader.get_top_arbitrage_redis(limit=5)

# ============================================================
# SECTION 1 : MARKET SUMMARY (CORRIGÉE)
# ============================================================

st.header("🌐 Market Summary")

if not latest_prices.empty and latest_prices['price'].notna().any():
    # Filtrer les valeurs NaN
    valid_prices = latest_prices[latest_prices['price'].notna()]
    
    total_volume = valid_prices['volume_24h'].sum()
    avg_change = valid_prices['change_24h'].mean()
    gainers = len(valid_prices[valid_prices['change_24h'] > 0])
    losers = len(valid_prices[valid_prices['change_24h'] < 0])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Volume 24h", f"${total_volume:,.0f}")
    
    with col2:
        st.metric("Avg Change 24h", f"{avg_change:+.2f}%")
    
    with col3:
        st.metric("Gainers / Losers", f"{gainers} / {losers}")
    
    with col4:
        st.metric("Total Assets", len(valid_prices))
else:
    st.warning("⚠️ No market data available. Check Redis/Binance connection.")

st.markdown("---")

# ============================================================
# SECTION 2 : PRICE CARDS (CORRIGÉE)
# ============================================================

st.header("💰 Current Prices")

num_cols = 3
rows = [CRYPTO_SYMBOLS[i:i+num_cols] for i in range(0, len(CRYPTO_SYMBOLS), num_cols)]

for row_symbols in rows:
    cols = st.columns(num_cols)
    
    for col, symbol in zip(cols, row_symbols):
        with col:
            symbol_data = latest_prices[latest_prices['symbol'] == symbol]
            
            if not symbol_data.empty and pd.notna(symbol_data.iloc[0]['price']):
                price = symbol_data.iloc[0]['price']
                change = symbol_data.iloc[0]['change_24h']
                
                # Vérifier que les valeurs sont valides
                if pd.notna(price) and pd.notna(change):
                    display_price_card(symbol, price, change)
                else:
                    st.warning(f"⚠️ Invalid data for {symbol}")
            else:
                st.warning(f"❌ No data for {symbol}")

st.markdown("---")


# ============================================================
# SECTION 3 : PRICE CHART (CORRIGÉE)
# ============================================================

st.header(f"📈 {selected_symbol} Price Chart")

col1, col2 = st.columns([3, 1])

with col1:
    price_history = loader.get_price_history(selected_symbol, hours=time_period)
    
    if not price_history.empty:
        fig = plot_price_chart(price_history, title=f"{selected_symbol} - Last {time_period}h")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"⚠️ No historical data for {selected_symbol}")

with col2:
    st.subheader("Statistics")
    
    if not price_history.empty:
        current_price = price_history['price'].iloc[-1]
        high_24h = price_history['price'].max()
        low_24h = price_history['price'].min()
        avg_price = price_history['price'].mean()
        
        st.metric("Current", f"${current_price:,.2f}")
        st.metric("24h High", f"${high_24h:,.2f}")
        st.metric("24h Low", f"${low_24h:,.2f}")
        st.metric("24h Average", f"${avg_price:,.2f}")
        
        price_range = high_24h - low_24h
        current_position = (current_price - low_24h) / price_range if price_range > 0 else 0.5
        
        st.progress(current_position)
        st.caption(f"Position in 24h range: {current_position*100:.1f}%")
    else:
        st.info("No statistics available")

st.markdown("---")

# ============================================================
# SECTION 4 : VOLUME ANALYSIS
# ============================================================

st.header("📊 Volume Analysis")

if not price_history.empty and 'volume_24h' in price_history.columns:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig_volume = plot_volume_distribution(price_history)
        st.plotly_chart(fig_volume, use_container_width=True)
    
    with col2:
        volume_stats = loader.get_volume_analysis(selected_symbol, hours=time_period)
        
        if volume_stats:
            from metrics import display_volume_stats
            display_volume_stats(volume_stats)
else:
    st.info("Volume data not available")

st.markdown("---")

# ============================================================
# SECTION 5 : ARBITRAGE OPPORTUNITIES
# ============================================================

st.header("🔄 Arbitrage Opportunities")

if arbitrage_opps:
    st.success(f"Found {len(arbitrage_opps)} arbitrage opportunities!")
    
    for opp in arbitrage_opps[:3]:  # Afficher top 3
        display_arbitrage_alert(opp)
else:
    st.info("No significant arbitrage opportunities at the moment")

# ============================================================
# SECTION 6 : TOP MOVERS (CORRIGÉE)
# ============================================================

st.header("🚀 Top Movers (24h)")

if not latest_prices.empty and latest_prices['price'].notna().any():
    valid_data = latest_prices[latest_prices['price'].notna() & latest_prices['change_24h'].notna()]
    
    if not valid_data.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🟢 Top Gainers")
            gainers = valid_data.nlargest(3, 'change_24h')
            
            for _, row in gainers.iterrows():
                st.markdown(f"""
                **{row['symbol']}**: ${row['price']:,.2f} 
                <span style='color: #00ff00'>▲ {row['change_24h']:+.2f}%</span>
                """, unsafe_allow_html=True)
        
        with col2:
            st.subheader("🔴 Top Losers")
            losers = valid_data.nsmallest(3, 'change_24h')
            
            for _, row in losers.iterrows():
                st.markdown(f"""
                **{row['symbol']}**: ${row['price']:,.2f} 
                <span style='color: #ff0000'>▼ {row['change_24h']:+.2f}%</span>
                """, unsafe_allow_html=True)
    else:
        st.info("No valid price data to display top movers")
else:
    st.warning("⚠️ Market data unavailable")