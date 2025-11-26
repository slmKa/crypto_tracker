"""
Page dédiée aux opportunités d'arbitrage - VERSION AMÉLIORÉE
"""
import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Arbitrage Opportunities",
    page_icon="🔄",
    layout="wide"
)

# Imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'utils'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'components'))

from data_loader import DataLoader
from metrics import (
    display_arbitrage_alert, 
    display_arbitrage_opportunity_detailed,
    display_exchange_stats,
    display_symbol_stats
)
from charts import (
    plot_arbitrage_heatmap,
    plot_spread_distribution,
    plot_spread_by_symbol,
    plot_spread_by_exchange_pair,
    plot_opportunities_timeline,
    plot_volume_vs_spread,
    plot_profitability_by_exchange
)

# Initialisation
@st.cache_resource
def init_loader():
    return DataLoader()

loader = init_loader()

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("🔄 Arbitrage Tracker")
    st.markdown("---")
    
    # Tabs pour les options
    tab1, tab2, tab3 = st.tabs(["⚙️ Filters", "💰 Calculator", "📊 Settings"])
    
    with tab1:
        st.subheader("Filter Options")
        
        # Période d'analyse
        time_period = st.selectbox(
            "Time Period",
            options=[1, 6, 12, 24, 48],
            format_func=lambda x: f"{x} hour{'s' if x > 1 else ''}",
            index=3  # 24h par défaut
        )
        
        # Seuil de spread minimum
        min_spread = st.slider(
            "Minimum Spread %",
            min_value=0.0,
            max_value=5.0,
            value=0.3,
            step=0.1,
            help="Only show opportunities with spread above this threshold"
        )
        
        # Filtre par profitabilité nette
        min_profit_pct = st.slider(
            "Minimum Profit %",
            min_value=0.0,
            max_value=2.0,
            value=0.1,
            step=0.05,
            help="Minimum net profit after fees"
        )
        
        # Filtre par volume
        min_volume = st.number_input(
            "Minimum 24h Volume (USD)",
            min_value=0,
            max_value=10000000,
            value=100000,
            step=100000,
            help="Filter by minimum trading volume"
        )
    
    with tab2:
        st.subheader("💰 Profit Calculator")
        
        investment = st.number_input(
            "Investment Amount (USD)",
            min_value=100,
            max_value=1000000,
            value=10000,
            step=1000
        )
        
        # Frais détaillés
        st.markdown("**Fee Structure**")
        maker_fee = st.number_input(
            "Maker Fee %",
            min_value=0.0,
            max_value=1.0,
            value=0.1,
            step=0.01,
            help="Fee for limit orders"
        )
        
        taker_fee = st.number_input(
            "Taker Fee %",
            min_value=0.0,
            max_value=1.0,
            value=0.1,
            step=0.01,
            help="Fee for market orders"
        )
        
        withdrawal_fee = st.number_input(
            "Withdrawal Fee %",
            min_value=0.0,
            max_value=2.0,
            value=0.0,
            step=0.01,
            help="Fee for withdrawing from exchange"
        )
    
    with tab3:
        st.subheader("📊 Display Settings")
        
        # Auto-refresh
        auto_refresh = st.checkbox("Auto-refresh (60s)", value=False)
        
        # Affichage des sections
        show_analysis = st.checkbox("Show Spread Analysis", value=True)
        show_stats = st.checkbox("Show Statistics", value=True)
        show_timeline = st.checkbox("Show Timeline", value=True)
        show_correlation = st.checkbox("Show Volume Correlation", value=True)
    
    if auto_refresh:
        import time
        time.sleep(60)
        st.rerun()

# ============================================================
# MAIN CONTENT
# ============================================================

st.title("🔄 Arbitrage Opportunities Dashboard")
st.markdown("Advanced real-time cross-exchange arbitrage analysis")

# Charger les données
with st.spinner("🔍 Scanning for arbitrage opportunities..."):
    # Calcul en temps réel
    realtime_opps = loader.calculate_arbitrage_opportunities(min_spread=min_spread)
    
    # Redis (temps réel)
    redis_opps = loader.get_top_arbitrage_redis(limit=20)
    
    # TimescaleDB (historique)
    db_opps = loader.get_arbitrage_opportunities(hours=time_period)

# Fusionner et filtrer
all_opps = []

# Ajouter opportunités temps réel
for opp in realtime_opps:
    if opp.get('spread_percent', 0) >= min_spread and opp.get('volume_24h', 0) >= min_volume:
        all_opps.append(opp)

# Ajouter opportunités Redis
for opp in redis_opps:
    if opp.get('spread_percent', 0) >= min_spread and opp.get('volume_24h', 0) >= min_volume:
        if not any(o['symbol'] == opp.get('symbol') for o in all_opps):
            all_opps.append(opp)

# Ajouter opportunités DB (si pas déjà présentes)
if not db_opps.empty:
    for _, row in db_opps.iterrows():
        if row['spread_percent'] >= min_spread:
            opp_dict = row.to_dict()
            if not any(o['symbol'] == opp_dict['symbol'] for o in all_opps):
                all_opps.append(opp_dict)

# Trier par spread décroissant
all_opps = sorted(all_opps, key=lambda x: x.get('spread_percent', 0), reverse=True)

# ============================================================
# SECTION 1 : OVERVIEW METRICS
# ============================================================

st.header("📊 Overview Metrics")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Active Opportunities",
        len(all_opps),
        help="Number of arbitrage opportunities detected"
    )

with col2:
    if all_opps:
        max_spread = max(opp.get('spread_percent', 0) for opp in all_opps)
        st.metric(
            "Max Spread",
            f"{max_spread:.2f}%",
            help="Highest spread detected"
        )
    else:
        st.metric("Max Spread", "N/A")

with col3:
    if all_opps:
        avg_spread = sum(opp.get('spread_percent', 0) for opp in all_opps) / len(all_opps)
        st.metric(
            "Average Spread",
            f"{avg_spread:.2f}%"
        )
    else:
        st.metric("Average Spread", "N/A")

with col4:
    if all_opps:
        total_volume = sum(opp.get('volume_24h', 0) for opp in all_opps)
        st.metric(
            "Total Volume",
            f"${total_volume/1e6:.1f}M",
            help="Combined 24h volume"
        )
    else:
        st.metric("Total Volume", "N/A")

with col5:
    if all_opps and investment:
        # Calculer profit potentiel avec le meilleur spread
        best_opp = max(all_opps, key=lambda x: x.get('spread_percent', 0))
        best_spread = best_opp.get('spread_percent', 0)
        
        # Calculer les frais
        fees_calc = loader.calculate_total_fees(
            best_opp.get('buy_exchange', 'Binance'),
            best_opp.get('sell_exchange', 'Binance'),
            best_opp.get('symbol', 'BTC/USDT'),
            investment,
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            withdrawal_fee=withdrawal_fee
        )
        
        gross_profit = investment * (best_spread / 100)
        net_profit = gross_profit - fees_calc['total_fees']
        
        st.metric(
            "Best Net Profit",
            f"${net_profit:,.2f}",
            delta=f"{(net_profit/investment)*100:.2f}%",
            delta_color="normal" if net_profit > 0 else "inverse"
        )
    else:
        st.metric("Best Net Profit", "N/A")

st.markdown("---")

# ============================================================
# SECTION 2 : ACTIVE OPPORTUNITIES
# ============================================================

st.header("🚨 Active Opportunities")

if all_opps:
    # Afficher les top opportunités
    st.subheader(f"Top {min(10, len(all_opps))} Opportunities")
    
    for opp in all_opps[:10]:
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                display_arbitrage_alert(opp)
            
            with col2:
                st.markdown("### Profit Calculation")
                
                spread = opp.get('spread_percent', 0)
                gross = investment * (spread / 100)
                fees = investment * (trading_fee / 100) * 2
                net = gross - fees
                
                st.metric("Gross Profit", f"${gross:,.2f}")
                st.metric("Fees", f"${fees:,.2f}", delta=f"-{trading_fee*2:.2f}%")
                st.metric("Net Profit", f"${net:,.2f}", 
                         delta=f"{(net/investment)*100:+.2f}%",
                         delta_color="normal" if net > 0 else "inverse")
                
                # ROI
                roi = (net / investment) * 100
                st.progress(min(roi / 10, 1.0))  # Cap à 10% pour la barre
                st.caption(f"ROI: {roi:.2f}%")
    
    st.markdown("---")
    
    # ============================================================
    # SECTION 3 : DETAILED TABLE
    # ============================================================
    
    st.header("📋 Detailed Opportunity Table")
    
    # Convertir en DataFrame
    df_opps = pd.DataFrame(all_opps)
    
    # Calculer colonnes additionnelles
    if not df_opps.empty:
        df_opps['gross_profit'] = investment * (df_opps['spread_percent'] / 100)
        df_opps['fees'] = investment * (trading_fee / 100) * 2
        df_opps['net_profit'] = df_opps['gross_profit'] - df_opps['fees']
        df_opps['roi_percent'] = (df_opps['net_profit'] / investment) * 100
        
        # Sélectionner et réordonner colonnes
        display_cols = [
            'symbol', 'buy_exchange', 'sell_exchange',
            'buy_price', 'sell_price', 'spread_percent',
            'gross_profit', 'fees', 'net_profit', 'roi_percent'
        ]
        
        # S'assurer que toutes les colonnes existent
        available_cols = [col for col in display_cols if col in df_opps.columns]
        df_display = df_opps[available_cols].copy()
        
        # Renommer pour affichage
        df_display.columns = [
            'Symbol', 'Buy Exchange', 'Sell Exchange',
            'Buy Price', 'Sell Price', 'Spread %',
            'Gross Profit', 'Fees', 'Net Profit', 'ROI %'
        ]
        
        # Formater les nombres
        format_dict = {
            'Buy Price': '${:,.2f}',
            'Sell Price': '${:,.2f}',
            'Spread %': '{:.2f}%',
            'Gross Profit': '${:,.2f}',
            'Fees': '${:,.2f}',
            'Net Profit': '${:,.2f}',
            'ROI %': '{:+.2f}%'
        }
        
        # Appliquer le style
        styled_df = df_display.style.format(format_dict).background_gradient(
            subset=['Spread %', 'ROI %'],
            cmap='RdYlGn'
        )
        
        st.dataframe(styled_df, use_container_width=True, height=400)
        
        # Bouton de téléchargement
        csv = df_display.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"arbitrage_opportunities_{time_period}h.csv",
            mime="text/csv"
        )
    
    st.markdown("---")
    
    # ============================================================
    # SECTION 4 : HEATMAP
    # ============================================================
    
    st.header("🔥 Arbitrage Heatmap")
    
    if not df_opps.empty and len(df_opps) > 1:
        fig_heatmap = plot_arbitrage_heatmap(df_opps)
        st.plotly_chart(fig_heatmap, use_container_width=True)
        
        st.info("""
        **How to read the heatmap:**
        - Each cell shows the average spread when buying on the row exchange and selling on the column exchange
        - Green = Higher spread (more profitable)
        - Red = Lower spread (less profitable)
        - Empty cells = No opportunities detected
        """)
    else:
        st.info("Not enough data to generate heatmap")
    
    st.markdown("---")
    
    # ============================================================
    # SECTION 5 : HISTORICAL TRENDS
    # ============================================================
    
    st.header("📈 Historical Trends")
    
    if not db_opps.empty:
        import plotly.graph_objects as go
        
        # Grouper par heure
        db_opps['hour'] = pd.to_datetime(db_opps['time']).dt.floor('H')
        hourly_avg = db_opps.groupby('hour')['spread_percent'].agg(['mean', 'max', 'count'])
        
        fig_trend = go.Figure()
        
        fig_trend.add_trace(go.Scatter(
            x=hourly_avg.index,
            y=hourly_avg['mean'],
            mode='lines+markers',
            name='Average Spread',
            line=dict(color='#00D9FF', width=2)
        ))
        
        fig_trend.add_trace(go.Scatter(
            x=hourly_avg.index,
            y=hourly_avg['max'],
            mode='lines',
            name='Max Spread',
            line=dict(color='#FF006E', width=1, dash='dash')
        ))
        
        fig_trend.update_layout(
            title=f"Arbitrage Spread Trends (Last {time_period}h)",
            xaxis_title="Time",
            yaxis_title="Spread %",
            template='plotly_dark',
            height=400,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_trend, use_container_width=True)
        
        # Statistiques
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Average Opportunities/Hour",
                f"{hourly_avg['count'].mean():.1f}"
            )
        
        with col2:
            st.metric(
                "Peak Hour",
                hourly_avg['count'].idxmax().strftime("%H:%M") if not hourly_avg.empty else "N/A"
            )
        
        with col3:
            st.metric(
                "Best Spread Hour",
                hourly_avg['max'].idxmax().strftime("%H:%M") if not hourly_avg.empty else "N/A"
            )
    else:
        st.info("No historical data available for the selected period")

else:
    # Aucune opportunité trouvée
    st.warning("🔍 No arbitrage opportunities detected")
    
    st.markdown("""
    ### Why no opportunities?
    
    Possible reasons:
    - Market is currently efficient (prices aligned across exchanges)
    - Minimum spread threshold is too high (try lowering it)
    - No recent data in the database (pipeline may need time to collect data)
    - Exchanges have similar liquidity
    
    **Tip:** Lower the minimum spread threshold in the sidebar to see smaller opportunities.
    """)

# ============================================================
# SECTION 6 : RISK WARNINGS
# ============================================================

st.markdown("---")
st.header("⚠️ Important Considerations")

with st.expander("📖 Read Before Trading"):
    st.markdown("""
    ### Arbitrage Trading Risks
    
    1. **Execution Risk**
       - Prices change rapidly
       - Orders may not fill at expected prices
       - Slippage can eat into profits
    
    2. **Transfer Time**
       - Moving funds between exchanges takes time
       - Prices may move against you during transfer
       - Blockchain confirmation delays
    
    3. **Fees**
       - Trading fees (maker/taker)
       - Withdrawal fees
       - Network/gas fees
       - Currency conversion fees
    
    4. **Liquidity**
       - Order books may have insufficient depth
       - Large orders can move the market
       - Partial fills
    
    5. **Exchange Risk**
       - Withdrawal limits
       - KYC requirements
       - Exchange downtime
       - Security concerns
    
    6. **Regulatory**
       - Tax implications
       - Reporting requirements
       - Jurisdictional restrictions
    
    ### Best Practices
    
    ✅ Start with small amounts  
    ✅ Factor in ALL fees  
    ✅ Test transfers first  
    ✅ Have accounts pre-funded on both exchanges  
    ✅ Use limit orders  
    ✅ Monitor execution carefully  
    ✅ Keep detailed records for taxes  
    
    **This tool is for educational purposes only. Always do your own research.**
    """)

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Arbitrage opportunities update every 5 minutes via Airflow pipeline</p>
    <p>⚠️ Past opportunities do not guarantee future profits</p>
</div>
""", unsafe_allow_html=True)