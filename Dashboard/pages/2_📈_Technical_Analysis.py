"""
Page d'analyse technique avancée - COMPLÈTE
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
# IMPORTS
# ============================================================

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'utils'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'components'))

from data_loader import DataLoader
from charts import (
    plot_candlestick_chart, plot_technical_indicators,
    plot_stochastic_oscillator, plot_atr, plot_adx,
    plot_support_resistance, plot_backtest_results
)
from metrics import display_trading_signal, display_indicator_gauge

# ============================================================
# INITIALISATION
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

    period_map = {'1h': 168, '4h': 168, '1d': 720}
    period = period_map[timeframe]

    st.markdown("---")
    st.subheader("📊 Display Options")
    
    col1, col2 = st.columns(2)
    with col1:
        show_volume = st.checkbox("Volume", value=True)
        show_ma = st.checkbox("Moving Avg", value=True)
        show_bb = st.checkbox("Bollinger", value=True)
    
    with col2:
        show_rsi = st.checkbox("RSI", value=True)
        show_macd = st.checkbox("MACD", value=True)
        show_stoch = st.checkbox("Stochastic", value=False)
    
    st.markdown("---")
    st.subheader("🔧 Advanced Options")
    
    show_atr = st.checkbox("ATR (Volatility)", value=False)
    show_adx = st.checkbox("ADX (Trend)", value=False)
    show_sr = st.checkbox("Support/Resistance", value=False)
    show_signals = st.checkbox("Trading Signals", value=True)
    show_backtest = st.checkbox("Backtest Strategy", value=False)
    
    st.markdown("---")
    st.subheader("⚙️ Settings")
    
    multi_timeframe = st.checkbox("Compare Timeframes", value=False)
    export_data = st.checkbox("Export Data", value=False)

# ============================================================
# MAIN CONTENT
# ============================================================

st.title(f"📈 {symbol} - Technical Analysis")
st.markdown(f"Timeframe: **{timeframe}** | Period: **{period//24} days**")

# Load data
with st.spinner(f"📊 Loading {symbol} data from Binance..."):
    try:
        ohlcv_df = loader.get_ohlcv_data(symbol, timeframe, hours=period)
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        st.stop()

if ohlcv_df.empty:
    st.error(f"❌ No OHLCV data available for {symbol} on {timeframe} timeframe")
    st.info("💡 Try a different timeframe or cryptocurrency")
    st.stop()

# ============================================================
# SECTION 0 : DATA QUALITY CHECK
# ============================================================

with st.expander("🔍 Data Quality Check", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Data Source", "Binance API")
    
    with col2:
        st.metric("Last Update", ohlcv_df.index[-1].strftime("%Y-%m-%d %H:%M:%S"))
    
    with col3:
        st.metric("Candles Count", len(ohlcv_df))
    
    with col4:
        expected = period
        actual = len(ohlcv_df)
        completeness = (actual / expected * 100) if expected > 0 else 0
        st.metric("Data Completeness", f"{completeness:.1f}%")
    
    if st.checkbox("View Raw Data"):
        st.dataframe(ohlcv_df.tail(10))

st.markdown("---")

# ============================================================
# SECTION 1 : CURRENT INDICATORS
# ============================================================

st.header("📊 Current Indicators")

last_row = ohlcv_df.iloc[-1]
col1, col2, col3, col4, col5 = st.columns(5)

# Trouver la dernière ligne avec des valeurs valides
valid_idx = len(ohlcv_df) - 1
while valid_idx >= 0 and (pd.isna(ohlcv_df.iloc[valid_idx]['rsi_14']) or 
                          pd.isna(ohlcv_df.iloc[valid_idx]['macd'])):
    valid_idx -= 1

if valid_idx >= 0:
    last_valid_row = ohlcv_df.iloc[valid_idx]
else:
    last_valid_row = last_row

with col1:
    if 'rsi_14' in ohlcv_df.columns and pd.notna(last_valid_row['rsi_14']):
        rsi_value = last_valid_row['rsi_14']
        st.metric("RSI (14)", f"{rsi_value:.1f}", 
                 delta="Overbought" if rsi_value > 70 else "Oversold" if rsi_value < 30 else "Neutral")
    else:
        st.info("RSI N/A")

with col2:
    if 'macd' in ohlcv_df.columns and pd.notna(last_valid_row['macd']):
        macd_value = last_valid_row['macd']
        signal_value = last_valid_row['macd_signal']
        macd_diff = macd_value - signal_value
        st.metric("MACD", f"{macd_value:.4f}", delta=f"{macd_diff:+.4f}")
    else:
        st.info("MACD N/A")

with col3:
    if 'stoch_k' in ohlcv_df.columns and pd.notna(last_valid_row['stoch_k']):
        stoch_value = last_valid_row['stoch_k']
        st.metric("Stochastic %K", f"{stoch_value:.1f}",
                 delta="Overbought" if stoch_value > 80 else "Oversold" if stoch_value < 20 else "Neutral")
    else:
        st.info("Stochastic N/A")

with col4:
    if 'atr' in ohlcv_df.columns and pd.notna(last_valid_row['atr']):
        atr_value = last_valid_row['atr']
        st.metric("ATR", f"${atr_value:,.2f}", delta="Volatility")
    else:
        st.info("ATR N/A")

with col5:
    if 'adx' in ohlcv_df.columns and pd.notna(last_valid_row['adx']):
        adx_value = last_valid_row['adx']
        st.metric("ADX", f"{adx_value:.1f}",
                 delta="Strong Trend" if adx_value > 25 else "Weak Trend")
    else:
        st.info("ADX N/A")

st.markdown("---")

# ============================================================
# SECTION 2 : TRADING SIGNALS
# ============================================================

if show_signals:
    st.header("🎯 Trading Signals")
    
    signals = loader.detect_signals(ohlcv_df)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if signals['golden_cross']:
            st.success("🟢 **GOLDEN CROSS** - Bullish signal!")
        elif signals['death_cross']:
            st.error("🔴 **DEATH CROSS** - Bearish signal!")
        else:
            st.info("No SMA crossover")
    
    with col2:
        if signals['macd_crossover']:
            st.success("🟢 **MACD CROSSOVER** - Bullish signal!")
        else:
            st.info("No MACD crossover")
    
    with col3:
        if signals['resistance_breakout']:
            st.success("🟢 **RESISTANCE BREAKOUT** - Bullish!")
        elif signals['support_breakout']:
            st.error("🔴 **SUPPORT BREAKOUT** - Bearish!")
        else:
            st.info("No breakout detected")
    
    st.markdown("---")

# ============================================================
# SECTION 3 : CANDLESTICK CHART
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

st.markdown("---")

# ============================================================
# SECTION 4 : TECHNICAL INDICATORS
# ============================================================

st.header("📉 Technical Indicators")

if show_rsi or show_macd:
    fig_indicators = plot_technical_indicators(ohlcv_df, symbol)
    st.plotly_chart(fig_indicators, use_container_width=True)

if show_stoch:
    fig_stoch = plot_stochastic_oscillator(ohlcv_df, symbol)
    st.plotly_chart(fig_stoch, use_container_width=True)

if show_atr:
    fig_atr = plot_atr(ohlcv_df, symbol)
    st.plotly_chart(fig_atr, use_container_width=True)

if show_adx:
    fig_adx = plot_adx(ohlcv_df, symbol)
    st.plotly_chart(fig_adx, use_container_width=True)

if show_sr:
    fig_sr = plot_support_resistance(ohlcv_df, symbol)
    st.plotly_chart(fig_sr, use_container_width=True)

st.markdown("---")

# ============================================================
# SECTION 5 : BACKTESTING
# ============================================================

if show_backtest:
    st.header("📊 Strategy Backtest")
    
    backtest_results = loader.backtest_strategy(ohlcv_df, initial_capital=10000)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Final Capital", f"${backtest_results['final_capital']:,.2f}")
    
    with col2:
        st.metric("Total Return", f"{backtest_results['total_return']:+.2f}%",
                 delta_color="normal" if backtest_results['total_return'] > 0 else "inverse")
    
    with col3:
        st.metric("Number of Trades", int(backtest_results['num_trades']))
    
    with col4:
        st.metric("Win Rate", f"{backtest_results['win_rate']:.1f}%")
    
    if backtest_results['trades']:
        fig_backtest = plot_backtest_results(backtest_results['trades'], symbol)
        st.plotly_chart(fig_backtest, use_container_width=True)
        
        with st.expander("📋 View All Trades"):
            trades_df = pd.DataFrame(backtest_results['trades'])
            st.dataframe(trades_df)
    else:
        st.info("No trades executed during backtest period")
    
    st.markdown("---")

# ============================================================
# SECTION 6 : MULTI-TIMEFRAME COMPARISON
# ============================================================

if multi_timeframe:
    st.header("⏱️ Multi-Timeframe Comparison")
    
    timeframes_to_compare = ['1h', '4h', '1d']
    cols = st.columns(3)
    
    for idx, tf in enumerate(timeframes_to_compare):
        with cols[idx]:
            period_map_multi = {'1h': 168, '4h': 168, '1d': 720}
            tf_data = loader.get_ohlcv_data(symbol, tf, hours=period_map_multi[tf])
            
            if not tf_data.empty:
                last = tf_data.iloc[-1]
                st.subheader(f"{tf} Timeframe")
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    close_price = last['close']
                    st.metric(
                        "Close",
                        f"${close_price:,.2f}" if pd.notna(close_price) else "N/A"
                    )
                with col_b:
                    if 'rsi_14' in tf_data.columns and pd.notna(last['rsi_14']):
                        rsi_val = last['rsi_14']
                        st.metric(
                            "RSI (14)",
                            f"{rsi_val:.1f}",
                            delta="Overbought" if rsi_val > 70 else "Oversold" if rsi_val < 30 else "Neutral"
                        )
                    else:
                        st.metric("RSI (14)", "N/A")
                with col_c:
                    if 'signal' in tf_data.columns:
                        signal = last['signal']
                        signal_color = "🟢" if signal == 'BUY' else "🔴" if signal == 'SELL' else "⚪"
                        st.metric("Signal", f"{signal_color} {signal}")
                    else:
                        st.metric("Signal", "N/A")
                
                # Afficher aussi MACD et ATR
                col_d, col_e = st.columns(2)
                with col_d:
                    if 'macd' in tf_data.columns and pd.notna(last['macd']):
                        macd_val = last['macd']
                        st.metric("MACD", f"{macd_val:.4f}")
                    else:
                        st.metric("MACD", "N/A")
                with col_e:
                    if 'atr' in tf_data.columns and pd.notna(last['atr']):
                        atr_val = last['atr']
                        st.metric("ATR", f"${atr_val:,.2f}")
                    else:
                        st.metric("ATR", "N/A")
    
    st.markdown("---")

# ============================================================
# SECTION 7 : EXPORT DATA
# ============================================================

if export_data:
    st.header("📥 Export Data")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv = ohlcv_df.to_csv()
        st.download_button(
            label="📊 Download CSV",
            data=csv,
            file_name=f"{symbol}_{timeframe}_ohlcv.csv",
            mime="text/csv"
        )
    
    with col2:
        st.info("HTML export coming soon")
    
    with col3:
        st.info("PDF export coming soon")

st.markdown("---")

# ============================================================
# FOOTER
# ============================================================

st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>📌 Technical analysis indicators are for informational purposes only.</p>
    <p>⚠️ Always do your own research before making trading decisions.</p>
    <p>🚀 Strategy backtest results do not guarantee future performance.</p>
</div>
""", unsafe_allow_html=True)