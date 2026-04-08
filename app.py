import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

# --- 1. CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Asistent CFD Pro: Misiunea 45k", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .stMetric { background-color: #f8fafc; border-radius: 12px; padding: 15px; border: 1px solid #e2e8f0; }
    [data-testid="stSidebar"] { background-color: #f1f5f9; }
    .stButton>button { background-color: #0f172a !important; color: white !important; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGICĂ CALCULE (CACHED) ---

@st.cache_data(ttl=300)
def get_market_data(ticker, interval="15m"):
    df = yf.download(ticker, period="60d", interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex): 
        df.columns = df.columns.get_level_values(0)
    return df

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        return yf.Ticker("GBPUSD=X").history(period="1d")['Close'].iloc[-1]
    except:
        return 1.28

def calculate_rsi_wilder(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# --- 3. SIDEBAR (CONTROL PANEL) ---
with st.sidebar:
    st.header("🎮 Panou Control")
    
    tip_activ = st.selectbox("Tip Activ:", ["Acțiuni", "Metale", "Forex"])
    
    if tip_activ == "Acțiuni":
        ticker_input = st.text_input("Simbol:", value="NVDA").upper().strip()
        levier = 5
    elif tip_activ == "Metale":
        ticker_input = st.selectbox("Metal:", ["GC=F (Aur)", "SI=F (Argint)", "HG=F (Cupru)"]).split(" ")[0]
        levier = 20
    else:
        ticker_input = st.text_input("Forex:", value="EURUSD=X").upper().strip()
        levier = 30

    directie = st.radio("Direcție:", ["📈 BUY (Long)", "📉 SELL (Short)"])
    
    st.divider()
    st.subheader("💰 Management Poziție")
    mod_calcul = st.radio("Calculează miza după:", ["Suma în £", "Număr Unități (Qty)"])
    
    if mod_calcul == "Suma în £":
        miza_valoare = st.number_input("Suma disponibilă (£):", value=100.0, step=10.0)
        qty_manual = None
    else:
        qty_manual = st.number_input("Cantitate (Unități):", value=10, step=1, min_value=1)
        miza_valoare = None

    st.divider()
    mult_sl = st.slider("Sensibilitate SL (ATR):", 1.0, 5.0, 2.0)
    rr_ratio = st.slider("Target Profit (Ratio):", 0.5, 5.0, 1.5)
    
    st.divider()
    comision_minim = st.number_input("Comision Broker (£):", value=10.0)
    spread_val = st.number_input("Spread estimat ($):", value=0.05, format="%.4f")

# --- 4. EXECUȚIE ȘI AFIȘARE ---
df = get_market_data(ticker_input)
curs_live = get_exchange_rate()

if not df.empty:
    close = df['Close']
    pret_acum = float(close.iloc[-1])
    
    # Indicatori
    df['EMA200'] = close.ewm(span=200, adjust=False).mean()
    df['RSI'] = calculate_rsi_wilder(close)
    tr = pd.concat([df['High']-df['Low'], abs(df['High']-close.shift()), abs(df['Low']-close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean().iloc[-1]
    
    # --- LOGICA DINAMICĂ SUMA VS QTY ---
    if mod_calcul == "Suma în £":
        # Câte unități îmi permit cu X lire la levierul Y?
        cantitate = int((miza_valoare * levier * curs_live) / pret_acum)
        marja_necesara_gbp = miza_valoare
    else:
        # Câte lire îmi trebuie pentru X unități?
        cantitate = qty_manual
        marja_necesara_gbp = (cantitate * pret_acum) / (levier * curs_live)

    # Prevenire eroare diviziune la zero sau qty prea mic
    if cantitate <= 0: cantitate = 1

    # SL / TP / Breakeven
    dist_sl = atr * mult_sl
    dist_tp = dist_sl * rr_ratio
    sl_p = pret_acum - dist_sl if "BUY" in directie else pret_acum + dist_sl
    tp_p = pret_acum + dist_tp if "BUY" in directie else pret_acum - dist_tp
    
    cost_total_usd = (comision_minim * 2 * curs_live) + (spread_val * cantitate)
    breakeven_p = pret_acum + (cost_total_usd / cantitate) if "BUY" in directie else pret_acum - (cost_total_usd / cantitate)
    
    # --- INTERFAȚA ---
    st.title(f"📊 {ticker_input} - Analiză Live")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Preț USD", f"${pret_acum:.2f}")
    c2.metric("Marjă Necesară", f"£{marja_necesara_gbp:.2f}")
    c3.metric("Cantitate", f"{cantitate} units")
    c4.metric("RSI", f"{df['RSI'].iloc[-1]:.1f}")

    # Grafic
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Preț")])
    fig.add_hline(y=tp_p, line_dash="dash", line_color="#10b981", annotation_text="Profit")
    fig.add_hline(y=sl_p, line_dash="dash", line_color="#ef4444", annotation_text="Stop")
    fig.add_hline(y=breakeven_p, line_dash="dot", line_color="#3b82f6", annotation_text="Breakeven")
    fig.update_layout(height=450, template="plotly_white", margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # BOXA DE EXECUȚIE (Rezumat pentru City Index)
    st.markdown(f"""
        <div style="background-color: #f8fafc; padding: 25px; border-radius: 15px; border: 2px solid #0f172a;">
            <h3 style="margin: 0; color: #0f172a;">📝 Detalii Ordin (City Index)</h3>
            <hr>
            <p style="font-size: 20px;"><b>Direcție:</b> {"BUY (Long)" if "BUY" in directie else "SELL (Short)"} | <b>Unități:</b> {cantitate}</p>
            <p style="font-size: 18px;">
                🎯 <b>TP:</b> ${tp_p:.2f} &nbsp;&nbsp; | &nbsp;&nbsp; 🛑 <b>SL:</b> ${sl_p:.2f}
            </p>
            <p style="color: #2563eb; font-weight: bold;">Punct de profit real (după taxe): ${breakeven_p:.4f}</p>
            <p style="font-size: 14px; color: #64748b;">Marja blocată în cont: £{marja_necesara_gbp:.2f}</p>
        </div>
    """, unsafe_allow_html=True)
else:
    st.warning("Introdu un simbol valid pentru a începe.")
