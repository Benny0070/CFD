import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

# --- 1. CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Asistent CFD Pro: Misiunea 45k", layout="wide", page_icon="💎")

# CSS personalizat pentru un aspect "Dark/Professional" dar curat
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .stMetric { background-color: #f1f5f9; border-radius: 10px; padding: 10px; border: 1px solid #e2e8f0; }
    .stButton>button { width: 100%; background-color: #0f172a !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. FUNCȚII OPTIMIZATE (CACHING & LOGICĂ) ---

@st.cache_data(ttl=300) # Datele se reîmprospătează la 5 minute
def get_market_data(ticker, interval="15m"):
    df = yf.download(ticker, period="60d", interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex): 
        df.columns = df.columns.get_level_values(0)
    return df

@st.cache_data(ttl=3600) # Cursul valutar se reîmprospătează la o oră
def get_exchange_rate():
    try:
        rate = yf.Ticker("GBPUSD=X").history(period="1d")['Close'].iloc[-1]
        return rate
    except:
        return 1.28 # Fallback

def calculate_rsi_wilder(series, period=14):
    """Calcul RSI folosind metoda de netezire a lui Wilder (Standard Trading)"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# --- 3. SIDEBAR (CONTROL PANEL) ---
with st.sidebar:
    st.header("⚙️ Parametri Trade")
    
    tip_activ = st.selectbox("Tip Activ:", ["Acțiuni (Stocks)", "Metale (Gold/Silver)", "Forex"])
    
    # Mapare simboluri populare
    if tip_activ == "Acțiuni (Stocks)":
        ticker_input = st.text_input("Simbol (ex: NVDA, TSLA):", value="NVDA").upper().strip()
        levier = 5
    elif tip_activ == "Metale (Gold/Silver)":
        ticker_input = st.selectbox("Selectează Metal:", ["GC=F (Aur)", "SI=F (Argint)", "HG=F (Cupru)"]).split(" ")[0]
        levier = 20
    else:
        ticker_input = st.text_input("Pereche Forex (ex: EURUSD=X):", value="EURUSD=X").upper().strip()
        levier = 30

    directie = st.radio("Direcție:", ["📈 BUY (Long)", "📉 SELL (Short)"])
    
    st.divider()
    suma_gbp = st.number_input("Miză disponibilă (£):", value=100.0, step=10.0)
    
    st.divider()
    mult_sl = st.slider("Sensibilitate SL (ATR):", 1.0, 5.0, 2.0)
    rr_ratio = st.slider("Raport Risc:Profit (1:X):", 0.5, 4.0, 1.5)

    st.divider()
    comision_minim = st.number_input("Comision City Index (£):", value=10.0)
    spread_val = st.number_input("Spread estimat ($):", value=0.05, format="%.4f")

# --- 4. PROCESARE DATE ---
df = get_market_data(ticker_input)
curs_live = get_exchange_rate()

if not df.empty:
    # Indicatori Tehnici
    close = df['Close']
    df['EMA200'] = close.ewm(span=200, adjust=False).mean()
    df['RSI'] = calculate_rsi_wilder(close)
    
    # MACD
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    
    # ATR pentru SL/TP
    tr = pd.concat([df['High']-df['Low'], abs(df['High']-close.shift()), abs(df['Low']-close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean().iloc[-1]
    
    # Valori Actuale
    pret_acum = float(close.iloc[-1])
    rsi_acum = float(df['RSI'].iloc[-1])
    ema_acum = float(df['EMA200'].iloc[-1])
    
    # --- LOGICĂ PROBABILITATE (SCORING) ---
    scor = 50
    if "BUY" in directie:
        if pret_acum > ema_acum: scor += 20
        if rsi_acum < 35: scor += 20  # Oversold
        elif rsi_acum > 70: scor -= 15 # Overbought
        if macd.iloc[-1] > signal.iloc[-1]: scor += 15
    else: # SHORT
        if pret_acum < ema_acum: scor += 20
        if rsi_acum > 65: scor += 20
        elif rsi_acum < 30: scor -= 15
        if macd.iloc[-1] < signal.iloc[-1]: scor += 15
    
    probabilitate = max(10, min(95, scor))

    # --- CALCUL MANAGEMENT RISC ---
    # Puterea de cumpărare: (Suma GBP * Levier * Curs USD) / Pret
    cantitate = int((suma_gbp * levier * curs_live) / pret_acum)
    if cantitate == 0: cantitate = 1
    
    dist_sl = atr * mult_sl
    dist_tp = dist_sl * rr_ratio
    
    if "BUY" in directie:
        sl_p, tp_p = pret_acum - dist_sl, pret_acum + dist_tp
    else:
        sl_p, tp_p = pret_acum + dist_sl, pret_acum - dist_tp
        
    # Breakeven (include spread și comision tur-retur)
    cost_total_usd = (comision_minim * 2 * curs_live) + (spread_val * cantitate)
    miscare_necesara = cost_total_usd / cantitate
    breakeven_p = pret_acum + miscare_necesara if "BUY" in directie else pret_acum - miscare_necesara
    
    # --- UI DISPLAY ---
    st.title(f"🚀 Analiză {ticker_input} - {datetime.now().strftime('%H:%M')}")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    col1.metric("Preț Live", f"${pret_acum:.2f}", f"{((pret_acum/df['Open'].iloc[-1])-1)*100:.2f}%")
    col2.metric("RSI (Wilder)", f"{rsi_acum:.2f}")
    col3.metric("Curs GBP/USD", f"{curs_live:.4f}")

    st.subheader(f"Probabilitate Succes: {probabilitate}%")
    st.progress(probabilitate / 100)

    # Grafic
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Preț")])
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA200'], line=dict(color='orange', width=1.5), name="Trend (EMA 200)"))
    
    # Linii suport/rezistență trade
    fig.add_hline(y=tp_p, line_dash="dash", line_color="#22c55e", annotation_text="Profit Target")
    fig.add_hline(y=sl_p, line_dash="dash", line_color="#ef4444", annotation_text="Stop Loss")
    fig.add_hline(y=breakeven_p, line_dash="dot", line_color="#3b82f6", annotation_text="Breakeven (Taxe incluse)")
    
    fig.update_layout(height=450, template="plotly_white", margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # Boxa de Execuție
    color_box = "#ecfdf5" if "BUY" in directie else "#fff1f2"
    border_box = "#10b981" if "BUY" in directie else "#f43f5e"
    
    st.markdown(f"""
        <div style="background-color: {color_box}; padding: 20px; border-radius: 12px; border: 2px solid {border_box}; color: #1e293b;">
            <h3 style="margin-top:0;">📋 Ordin City Index (Simulare)</h3>
            <table style="width:100%; font-size: 18px;">
                <tr>
                    <td><b>Direcție:</b> {"CUMPĂRARE" if "BUY" in directie else "VÂNZARE"}</td>
                    <td><b>Cantitate:</b> {cantitate} units</td>
                </tr>
                <tr>
                    <td><b>Stop Loss:</b> ${sl_p:.2f}</td>
                    <td><b>Take Profit:</b> ${tp_p:.2f}</td>
                </tr>
                <tr>
                    <td colspan="2"><b>Punct Breakeven Real:</b> <span style="color:blue;">${breakeven_p:.4f}</span></td>
                </tr>
            </table>
            <p style="font-size: 14px; margin-top: 10px; color: #64748b;">
                *Taxe estimate: £{cost_total_usd/curs_live:.2f} | Levier aplicat: 1:{levier}
            </p>
        </div>
    """, unsafe_allow_html=True)

else:
    st.error("Nu am putut încărca datele. Verifică simbolul introdus.")
