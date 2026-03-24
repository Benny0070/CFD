import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Asistent CFD: Misiunea 45k", layout="wide", page_icon="🚀")

# (Păstrăm stilul tău CSS neschimbat aici...)
st.markdown("""
    <style>
    .stApp, [data-testid="stSidebar"], [data-testid="stHeader"] { background-color: #ffffff !important; }
    p, h1, h2, h3, h4, h5, h6, span, label, div { color: #000000 !important; }
    .stButton>button { background-color: #2ea043 !important; color: #ffffff !important; font-weight: bold !important; width: 100% !important; }
    </style>
""", unsafe_allow_html=True)

# --- LOGICA DE CALCUL INDICATORI ---
def calculeaza_indicatori(df):
    close = df['Close']
    
    # 1. EMA 200 (Trend pe termen lung)
    ema200 = close.ewm(span=200, adjust=False).mean()
    
    # 2. RSI (Relative Strength Index) - Varianta Standard
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # 3. MACD (Moving Average Convergence Divergence)
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    
    return ema200.iloc[-1], rsi.iloc[-1], macd.iloc[-1], signal.iloc[-1]

# --- INTERFAȚĂ SIDEBAR ---
with st.sidebar:
    st.header("💼 Control Portofel")
    ticker = st.text_input("Simbol (ex: NVDA, TSLA):", value="NVDA").upper().strip()
    directie = st.radio("Direcție:", ["📈 CUMPĂRARE (Long)", "📉 VÂNZARE (Short)"])
    suma_gbp = st.number_input("Suma (£):", value=100.0, step=10.0)
    
    # REPARAȚIE SLIDER (Am adăugat virgula lipsă și am pus valori logice)
    multiplicator_sl = st.slider("Sensibilitate Stop Loss (ATR):", 0.5, 3.0, 1.5, 0.1)
    raport_rr = st.slider("Țintă Profit (Risk/Reward):", 1.0, 5.0, 2.0, 0.1)

# --- ANALIZA PIEȚEI ---
if ticker:
    df = yf.download(ticker, period="60d", interval="15m", progress=False)
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        pret_acum = float(df['Close'].iloc[-1])
        ema, rsi_val, macd_val, signal_val = calculeaza_indicatori(df)
        
        # --- SCOR AI ÎMBUNĂTĂȚIT ---
        scor = 50
        if pret_acum > ema: scor += 15
        else: scor -= 15
        
        if rsi_val < 30: scor += 20  # Supravândut
        elif rsi_val > 70: scor -= 20 # Supracumpărat
        
        if macd_val > signal_val: scor += 15
        else: scor -= 15
        
        # Ajustăm scorul pentru SELL
        probabilitate = scor if "CUMP" in directie else (100 - scor)
        probabilitate = max(10, min(95, int(probabilitate)))

        # --- AFIȘARE REZULTATE ---
        st.title(f"Analiză {ticker} - ${pret_acum:.2f}")
        
        # Vizualizare rapidă a forței semnalului
        st.progress(probabilitate / 100)
        st.subheader(f"Probabilitate Succes: {probabilitate}%")

        # Managementul riscului (ATR pentru SL)
        tr = pd.concat([df['High'] - df['Low'], 
                        abs(df['High'] - df['Close'].shift()), 
                        abs(df['Low'] - df['Close'].shift())], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        distanta_sl = atr * multiplicator_sl
        distanta_tp = distanta_sl * raport_rr
        
        if "CUMP" in directie:
            sl = pret_acum - distanta_sl
            tp = pret_acum + distanta_tp
        else:
            sl = pret_acum + distanta_sl
            tp = pret_acum - distanta_tp

        # --- INSTRUCȚIUNI CITY INDEX ---
        st.divider()
        st.subheader("📱 Ce introduci pe City Index:")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Direcție", "BUY" if "CUMP" in directie else "SELL")
        c2.metric("Take Profit", f"${tp:.2f}")
        c3.metric("Stop Loss", f"${sl:.2f}")
        
        st.info(f"**Sfat:** Dacă ești pe SELL (Short), profitul se face când prețul scade sub ${pret_acum:.2f}.")

    else:
        st.error("Nu s-au găsit date pentru acest simbol.")
