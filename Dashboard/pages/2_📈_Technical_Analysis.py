"""
Page d'analyse technique avancée - CORRIGÉE
"""
import streamlit as st
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Technical Analysis",
    page_icon="📈",
    layout="wide"
)

# ============================================================
# IMPORTS (✅ UTILISER LE BON DataLoader)
# ============================================================

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'utils'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'components'))

# ✅ IMPORTER LE BON DataLoader depuis utils/
from data_loader import DataLoader
from charts import plot_candlestick_chart, plot_technical_indicators
from metrics import display_trading_signal, display_indicator_gauge

# ============================================================
# INITIALISATION DU LOADER
# ============================================================

@st.cache_resource
def init_loader():
    return DataLoader()

loader = init_loader()

CRYPTO_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT']

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("📈 Technical Analysis")
    st.markdown("---")

    symbol = st.selectbox("Cryptocurrency", CRYPTO_SYMBOLS, index=0)

    timeframe = st.selectbox("Timeframe", options=['1h', '4h', '1d'], index=0)

    period_map = {'1h': 168, '4h': 168, '1d': 720}  # ✅ Ajusté
    period = period_map[timeframe]

    st.markdown("---")

    st.subheader("Display Options")
    show_volume = st.checkbox("Show Volume", value=True)
    show_ma = st.checkbox("Show Moving Averages", value=True)
    show_bb = st.checkbox("Show Bollinger Bands", value=True)
    show_rsi = st.checkbox("Show RSI", value=True)
    show_macd = st.checkbox("Show MACD", value=True)

# ============================================================
# MAIN CONTENT
# ============================================================

st.title(f"📈 {symbol} - Technical Analysis")
st.markdown(f"Timeframe: **{timeframe}** | Period: **{period//24} days**")

# ✅ UTILISER LA MÉTHODE get_ohlcv_data du DataLoader
with st.spinner("Loading chart data..."):
    ohlcv_df = loader.get_ohlcv_data(symbol, timeframe, hours=period)

if ohlcv_df.empty:
    st.error(f"❌ No OHLCV data available for {symbol} on {timeframe} timeframe")
    st.info("💡 Trying to fetch directly from Binance...")
    
    # Fallback: essayer une requête directe
    try:
        import ccxt
        exchange = ccxt.binance()
        data = exchange.fetch_ohlcv(symbol, timeframe, limit=min(period, 500))
        
        if data:
            ohlcv_df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            ohlcv_df['timestamp'] = pd.to_datetime(ohlcv_df['timestamp'], unit='ms')
            ohlcv_df.set_index('timestamp', inplace=True)
            st.success(f"✅ Retrieved {len(ohlcv_df)} candles from Binance")
        else:
            st.stop()
    except Exception as e:
        st.error(f"❌ Binance fetch failed: {e}")
        st.stop()

# ============================================================
# SECTION 1 : CURRENT INDICATORS
# ============================================================

st.header("📊 Current Indicators")

col1, col2, col3, col4 = st.columns(4)
last_row = ohlcv_df.iloc[-1]

with col1:
    if 'rsi_14' in ohlcv_df.columns and pd.notna(last_row['rsi_14']):
        rsi_value = last_row['rsi_14']
        display_indicator_gauge(
            value=rsi_value,
            min_val=0,
            max_val=100,
            label="RSI (14)",
            thresholds={'low': 30, 'high': 70}
        )
    else:
        st.info("RSI not available")

with col2:
    if 'macd' in ohlcv_df.columns and 'macd_signal' in ohlcv_df.columns:
        macd_value = last_row['macd']
        signal_value = last_row['macd_signal']
        macd_diff = macd_value - signal_value
        st.metric("MACD", f"{macd_value:.2f}", delta=f"{macd_diff:+.2f}",
                  delta_color="normal" if macd_diff >= 0 else "inverse")
        st.caption(f"Signal: {signal_value:.2f}")
    else:
        st.info("MACD not available")

with col3:
    if 'close' in ohlcv_df.columns and 'sma_20' in ohlcv_df.columns:
        close_price = last_row['close']
        sma_20 = last_row['sma_20']
        diff_pct = ((close_price - sma_20) / sma_20) * 100
        st.metric("Price vs SMA(20)", f"${close_price:,.2f}", delta=f"{diff_pct:+.2f}%")
    else:
        st.info("SMA not available")

with col4:
    if 'signal' in ohlcv_df.columns and 'signal_strength' in ohlcv_df.columns:
        signal = last_row['signal']
        strength = last_row['signal_strength']
        display_trading_signal(signal, strength)
    else:
        st.info("Trading signal not available")

st.markdown("---")

# ============================================================
# SECTION 2 : CANDLESTICK CHART
# ============================================================

st.header("🕯️ Price Chart")

df_to_plot = ohlcv_df.copy()

if not show_ma:
    ma_cols = [col for col in df_to_plot.columns if 'sma' in col or 'ema' in col]
    df_to_plot.drop(columns=ma_cols, errors='ignore', inplace=True)

if not show_bb:
    bb_cols = [col for col in df_to_plot.columns if 'bb_' in col]
    df_to_plot.drop(columns=bb_cols, errors='ignore', inplace=True)

fig_candles = plot_candlestick_chart(df_to_plot, symbol)
st.plotly_chart(fig_candles, use_container_width=True)

# ============================================================
# SECTION 3 : INDICATORS
# ============================================================

st.header("📉 Technical Indicators")

if show_rsi or show_macd:
    fig_indicators = plot_technical_indicators(ohlcv_df, symbol)
    st.plotly_chart(fig_indicators, use_container_width=True)
else:
    st.info("Enable RSI or MACD in sidebar to display indicators")

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Technical analysis indicators are for informational purposes only.</p>
    <p>⚠️ Always do your own research before making trading decisions.</p>
</div>
""", unsafe_allow_html=True)