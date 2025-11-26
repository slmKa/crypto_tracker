"""
Composants pour afficher des métriques (KPIs)
"""
import streamlit as st
import pandas as pd

def display_price_card(symbol: str, price: float, change_24h: float):
    """
    Afficher une carte de prix avec variation
    
    Args:
        symbol: Symbole crypto
        price: Prix actuel
        change_24h: Variation 24h en %
    """
    # Déterminer couleur selon variation
    delta_color = "normal" if change_24h >= 0 else "inverse"
    
    st.metric(
        label=symbol,
        value=f"${price:,.2f}",
        delta=f"{change_24h:+.2f}%",
        delta_color=delta_color
    )

def display_market_summary(summary: dict):
    """
    Afficher résumé du marché en colonnes
    
    Args:
        summary: Dict avec métriques du marché
    """
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Volume 24h",
            f"${summary.get('total_volume_24h', 0):,.0f}",
            help="Volume total de trading sur 24h"
        )
    
    with col2:
        avg_change = summary.get('avg_change_24h', 0)
        st.metric(
            "Avg Change 24h",
            f"{avg_change:+.2f}%",
            delta_color="normal" if avg_change >= 0 else "inverse"
        )
    
    with col3:
        st.metric(
            "Gainers / Losers",
            f"{summary.get('gainers', 0)} / {summary.get('losers', 0)}",
            help="Nombre d'assets en hausse vs baisse"
        )
    
    with col4:
        st.metric(
            "Total Assets",
            summary.get('total_assets', 0)
        )

def display_arbitrage_alert(opportunity: dict):
    """
    Afficher une alerte d'arbitrage
    
    Args:
        opportunity: Dict avec détails de l'opportunité
    """
    spread = opportunity['spread_percent']
    
    # Couleur selon importance du spread
    if spread > 1.0:
        alert_type = "error"  # Rouge
    elif spread > 0.5:
        alert_type = "warning"  # Jaune
    else:
        alert_type = "info"  # Bleu
    
    with st.container():
        st.markdown(f"""
        <div style="
            padding: 1rem;
            border-left: 4px solid {'#ff4b4b' if alert_type == 'error' else '#ffa500' if alert_type == 'warning' else '#0068c9'};
            background-color: rgba(0, 0, 0, 0.1);
            border-radius: 0.5rem;
            margin-bottom: 1rem;
        ">
            <h3 style="margin: 0; color: white;">{opportunity['symbol']}</h3>
            <p style="margin: 0.5rem 0; font-size: 1.2rem; color: {'#ff4b4b' if alert_type == 'error' else '#ffa500'};">
                <b>{spread:.2f}% Spread</b>
            </p>
            <p style="margin: 0; color: #ccc;">
                📈 Buy on <b>{opportunity['buy_exchange']}</b> @ ${opportunity['buy_price']:,.2f}<br>
                📉 Sell on <b>{opportunity['sell_exchange']}</b> @ ${opportunity['sell_price']:,.2f}<br>
                💰 Potential Profit: <b>${opportunity.get('potential_profit', 0):,.2f}</b>
            </p>
        </div>
        """, unsafe_allow_html=True)

def display_trading_signal(signal: str, strength: float):
    """
    Afficher un signal de trading
    
    Args:
        signal: 'BUY', 'SELL', ou 'HOLD'
        strength: Force du signal (-3 à +3)
    """
    # Emojis et couleurs
    signal_config = {
        'BUY': {'emoji': '🟢', 'color': '#00ff00', 'text': 'Strong Buy' if strength > 2.5 else 'Buy'},
        'SELL': {'emoji': '🔴', 'color': '#ff0000', 'text': 'Strong Sell' if strength < -2.5 else 'Sell'},
        'HOLD': {'emoji': '⚪', 'color': '#gray', 'text': 'Hold'}
    }
    
    config = signal_config.get(signal, signal_config['HOLD'])
    
    st.markdown(f"""
    <div style="
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, {config['color']}22, transparent);
        border-radius: 0.5rem;
        border: 2px solid {config['color']};
    ">
        <div style="font-size: 3rem;">{config['emoji']}</div>
        <div style="font-size: 1.5rem; font-weight: bold; color: {config['color']};">
            {config['text']}
        </div>
        <div style="color: #ccc;">Signal Strength: {abs(strength):.1f}/3</div>
    </div>
    """, unsafe_allow_html=True)

def display_indicator_gauge(value: float, min_val: float, max_val: float, 
                           label: str, thresholds: dict = None):
    """
    Afficher une jauge pour indicateur (ex: RSI)
    
    Args:
        value: Valeur actuelle
        min_val: Valeur minimale
        max_val: Valeur maximale
        label: Label de l'indicateur
       thresholds: Dict avec seuils {'low': 30, 'high': 70}
    """
    import plotly.graph_objects as go
    
    # Déterminer la couleur selon la valeur
    if thresholds:
        if value <= thresholds.get('low', 0):
            color = 'green'  # Oversold
        elif value >= thresholds.get('high', 100):
            color = 'red'    # Overbought
        else:
            color = 'gray'   # Neutral
    else:
        color = 'blue'
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': label, 'font': {'size': 24}},
        delta = {'reference': (max_val + min_val) / 2},
        gauge = {
            'axis': {'range': [min_val, max_val], 'tickwidth': 1},
            'bar': {'color': color},
            'bgcolor': "rgba(0,0,0,0.1)",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [min_val, thresholds.get('low', min_val)], 'color': 'rgba(0, 255, 0, 0.2)'},
                {'range': [thresholds.get('high', max_val), max_val], 'color': 'rgba(255, 0, 0, 0.2)'}
            ] if thresholds else [],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': value
            }
        }
    ))
    
    fig.update_layout(
        paper_bgcolor = "rgba(0,0,0,0)",
        plot_bgcolor = "rgba(0,0,0,0)",
        font = {'color': "white", 'family': "Arial"},
        height = 250,
        margin = dict(l=20, r=20, t=50, b=20)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_volume_stats(stats: dict):
    """
    Afficher statistiques de volume
    
    Args:
        stats: Dict avec métriques de volume
    """
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Total Volume",
            f"{stats.get('total', 0):,.0f}",
            help="Volume total sur la période"
        )
    
    with col2:
        st.metric(
            "Average Volume",
            f"{stats.get('average', 0):,.0f}",
            help="Volume moyen par période"
        )
    
    with col3:
        high_vol_pct = stats.get('high_volume_percent', 0)
        st.metric(
            "High Volume Periods",
            f"{high_vol_pct:.1f}%",
            help="% de périodes avec volume élevé (>1.5x moyenne)"
        )

def display_arbitrage_opportunity_detailed(opportunity: dict, fees: dict = None):
    """
    Afficher détails complets d'une opportunité d'arbitrage
    
    Args:
        opportunity: Dict avec détails de l'opportunité
        fees: Dict avec détails des frais
    """
    spread = opportunity.get('spread_percent', 0)
    buy_price = opportunity.get('buy_price', 0)
    sell_price = opportunity.get('sell_price', 0)
    
    # Couleur selon importance du spread
    if spread > 1.0:
        alert_type = "error"  # Rouge
    elif spread > 0.5:
        alert_type = "warning"  # Jaune
    else:
        alert_type = "info"  # Bleu
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        spread_abs = opportunity.get('spread_absolute', 0)
        st.metric(
            "Spread",
            f"{spread:.4f}%",
            delta=f"${spread_abs:,.4f}" if spread_abs > 0 else "N/A",
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            "Buy Price",
            f"${buy_price:,.4f}" if buy_price > 0 else "N/A",
            help=f"On {opportunity.get('buy_exchange', 'N/A')}"
        )
    
    with col3:
        st.metric(
            "Sell Price",
            f"${sell_price:,.4f}" if sell_price > 0 else "N/A",
            help=f"On {opportunity.get('sell_exchange', 'N/A')}"
        )
    
    # Afficher les frais si disponibles
    if fees:
        st.markdown("### 💰 Fee Breakdown")
        fee_col1, fee_col2, fee_col3, fee_col4 = st.columns(4)
        
        with fee_col1:
            buy_fee = fees.get('buy_fee', 0)
            st.metric("Buy Fee", f"${buy_fee:,.2f}" if buy_fee >= 0 else "N/A")
        with fee_col2:
            sell_fee = fees.get('sell_fee', 0)
            st.metric("Sell Fee", f"${sell_fee:,.2f}" if sell_fee >= 0 else "N/A")
        with fee_col3:
            withdrawal_fee = fees.get('withdrawal_fee', 0)
            st.metric("Withdrawal Fee", f"${withdrawal_fee:,.2f}" if withdrawal_fee >= 0 else "N/A")
        with fee_col4:
            total_fees = fees.get('total_fees', 0)
            total_pct = fees.get('total_fees_percent', 0)
            st.metric(
                "Total Fees", 
                f"${total_fees:,.2f}" if total_fees >= 0 else "N/A", 
                delta=f"{total_pct:.2f}%" if total_pct >= 0 else "N/A"
            )

def display_exchange_stats(stats: dict):
    """
    Afficher statistiques d'arbitrage par exchange
    
    Args:
        stats: Dict avec statistiques par exchange
    """
    if not stats:
        st.info("No exchange statistics available")
        return
    
    st.markdown("### 📊 Exchange Pair Statistics")
    
    # Créer un DataFrame pour affichage
    data = []
    for pair, stat in stats.items():
        data.append({
            'Exchange Pair': pair,
            'Opportunities': stat['count'],
            'Avg Spread %': f"{stat['avg_spread']:.2f}%",
            'Max Spread %': f"{stat['max_spread']:.2f}%",
            'Min Spread %': f"{stat['min_spread']:.2f}%",
            'Total Profit': f"${stat['total_profit']:,.2f}"
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

def display_symbol_stats(stats: dict):
    """
    Afficher statistiques d'arbitrage par symbole
    
    Args:
        stats: Dict avec statistiques par symbole
    """
    if not stats:
        st.info("No symbol statistics available")
        return
    
    st.markdown("### 📈 Symbol Statistics")
    
    # Créer un DataFrame pour affichage
    data = []
    for symbol, stat in stats.items():
        data.append({
            'Symbol': symbol,
            'Opportunities': stat['count'],
            'Avg Spread %': f"{stat['avg_spread']:.2f}%",
            'Max Spread %': f"{stat['max_spread']:.2f}%",
            'Min Spread %': f"{stat['min_spread']:.2f}%",
            'Exchanges': ', '.join(stat['exchanges']),
            'Total Profit': f"${stat['total_profit']:,.2f}"
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)