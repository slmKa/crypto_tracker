"""
Composants de visualisation (graphiques)
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import streamlit as st

def plot_price_chart(df: pd.DataFrame, title: str = "Price Chart") -> go.Figure:
    """
    Créer un graphique de prix simple
    
    Args:
        df: DataFrame avec colonnes ['time', 'price']
        title: Titre du graphique
        
    Returns:
        Figure Plotly
    """
    fig = go.Figure()
    
    # Ligne de prix
    fig.add_trace(go.Scatter(
        x=df.index if isinstance(df.index, pd.DatetimeIndex) else df['time'],
        y=df['price'],
        mode='lines',
        name='Price',
        line=dict(color='#00D9FF', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 217, 255, 0.1)'
    ))
    
    # Style
    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="Price (USD)",
        hovermode='x unified',
        template='plotly_dark',
        height=400,
        showlegend=True
    )
    
    return fig

def plot_candlestick_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    """
    Créer un graphique en chandelier (candlestick) avec volume
    
    Args:
        df: DataFrame OHLCV
        symbol: Nom du symbole
        
    Returns:
        Figure avec 2 subplots (prix + volume)
    """
    # Créer subplots : 2 rangées (prix + volume)
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f'{symbol} Price', 'Volume')
    )
    
    # Subplot 1 : Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='OHLC',
            increasing_line_color='#00D9FF',  # Vert
            decreasing_line_color='#FF006E'   # Rouge
        ),
        row=1, col=1
    )
    
    # Ajouter les moyennes mobiles si disponibles
    if 'sma_20' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['sma_20'],
                mode='lines',
                name='SMA 20',
                line=dict(color='orange', width=1)
            ),
            row=1, col=1
        )
    
    if 'sma_50' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['sma_50'],
                mode='lines',
                name='SMA 50',
                line=dict(color='purple', width=1)
            ),
            row=1, col=1
        )
    
    # Subplot 2 : Volume
    colors = ['#00D9FF' if close >= open_ else '#FF006E' 
              for close, open_ in zip(df['close'], df['open'])]
    
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['volume'],
            name='Volume',
            marker_color=colors,
            showlegend=False
        ),
        row=2, col=1
    )
    
    # Style
    fig.update_layout(
        template='plotly_dark',
        height=700,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        hovermode='x unified'
    )
    
    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    
    return fig

def plot_technical_indicators(df: pd.DataFrame, symbol: str) -> go.Figure:
    """
    Graphique avec indicateurs techniques (RSI, MACD)
    
    Args:
        df: DataFrame avec indicateurs
        symbol: Symbole
        
    Returns:
        Figure avec 3 subplots
    """
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.5, 0.25, 0.25],
        subplot_titles=(f'{symbol} Price', 'RSI', 'MACD')
    )
    
    # Row 1 : Prix + Bollinger Bands
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['close'],
            mode='lines',
            name='Close',
            line=dict(color='white', width=2)
        ),
        row=1, col=1
    )
    
    if 'bb_upper' in df.columns:
        # Upper band
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['bb_upper'],
                mode='lines',
                name='BB Upper',
                line=dict(color='gray', width=1, dash='dash'),
                showlegend=False
            ),
            row=1, col=1
        )
        
        # Lower band
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['bb_lower'],
                mode='lines',
                name='BB Lower',
                line=dict(color='gray', width=1, dash='dash'),
                fill='tonexty',
                fillcolor='rgba(128, 128, 128, 0.1)',
                showlegend=False
            ),
            row=1, col=1
        )
    
    # Row 2 : RSI
    if 'rsi_14' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['rsi_14'],
                mode='lines',
                name='RSI',
                line=dict(color='#00D9FF', width=2)
            ),
            row=2, col=1
        )
        
        # Lignes de référence RSI (30 et 70)
        fig.add_hline(y=70, line_dash="dash", line_color="red", 
                      annotation_text="Overbought", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", 
                      annotation_text="Oversold", row=2, col=1)
    
    # Row 3 : MACD
    if 'macd' in df.columns and 'macd_signal' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['macd'],
                mode='lines',
                name='MACD',
                line=dict(color='blue', width=2)
            ),
            row=3, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['macd_signal'],
                mode='lines',
                name='Signal',
                line=dict(color='orange', width=2)
            ),
            row=3, col=1
        )
        
        # Histogram
        if 'macd_histogram' in df.columns:
            colors = ['green' if val >= 0 else 'red' for val in df['macd_histogram']]
            fig.add_trace(
                go.Bar(
                    x=df.index,
                    y=df['macd_histogram'],
                    name='Histogram',
                    marker_color=colors
                ),
                row=3, col=1
            )
    
    # Style
    fig.update_layout(
        template='plotly_dark',
        height=900,
        showlegend=True,
        hovermode='x unified'
    )
    
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="RSI", row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    
    return fig

def plot_arbitrage_heatmap(opportunities: pd.DataFrame) -> go.Figure:
    """
    Heatmap des opportunités d'arbitrage
    
    Args:
        opportunities: DataFrame avec colonnes 
                      [symbol, buy_exchange, sell_exchange, spread_percent]
    
    Returns:
        Heatmap Plotly
    """
    if opportunities.empty:
        # Graphique vide si pas d'opportunités
        fig = go.Figure()
        fig.add_annotation(
            text="No arbitrage opportunities detected",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(template='plotly_dark', height=400)
        return fig
    
    # Créer matrice pivot
    pivot = opportunities.pivot_table(
        values='spread_percent',
        index='buy_exchange',
        columns='sell_exchange',
        aggfunc='mean'
    )
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale='RdYlGn',
        text=pivot.values,
        texttemplate='%{text:.2f}%',
        textfont={"size": 12},
        colorbar=dict(title="Spread %")
    ))
    
    fig.update_layout(
        title="Arbitrage Spread Matrix (Buy → Sell)",
        xaxis_title="Sell on Exchange",
        yaxis_title="Buy on Exchange",
        template='plotly_dark',
        height=400
    )
    
    return fig
def plot_volume_distribution(df: pd.DataFrame) -> go.Figure:
    """
    Graphique de distribution du volume
    Accepte 'volume' ou 'volume_24h'
    """
    # ✅ DÉTECTION AUTOMATIQUE DE LA COLONNE VOLUME
    volume_col = None
    
    if 'volume' in df.columns:
        volume_col = 'volume'
    elif 'volume_24h' in df.columns:
        volume_col = 'volume_24h'
    else:
        # Chercher toute colonne contenant "volume"
        vol_cols = [col for col in df.columns if 'volume' in col.lower()]
        if vol_cols:
            volume_col = vol_cols[0]
    
    if volume_col is None:
        # Créer un graphique vide avec message d'erreur
        fig = go.Figure()
        fig.add_annotation(
            text="⚠️ No volume data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            title="Volume Distribution",
            template='plotly_dark',
            height=400
        )
        return fig
    
    # ✅ CRÉER LE GRAPHIQUE AVEC LA COLONNE DÉTECTÉE
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df.index,
        y=df[volume_col],
        name='Volume',
        marker_color='#00D9FF',
        hovertemplate='<b>Time</b>: %{x}<br><b>Volume</b>: %{y:,.0f}<extra></extra>'
    ))
    
    fig.update_layout(
        title=f"Volume Distribution ({volume_col})",
        xaxis_title="Time",
        yaxis_title="Volume",
        template='plotly_dark',
        hovermode='x unified',
        height=400,
        showlegend=False
    )
    
    return fig