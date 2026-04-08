import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

# --- 1. CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Asistent CFD Pro", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .stMetric { background-color: #f8fafc; border-radius: 12px; padding: 15px; border: 1px solid #e2e8f0; }
    .stProgress > div > div > div > div { background-color: #10b981; }
    </style>
""", unsafe_allow_html=True)

# --- 2. FUNCȚII TEHNICE ---
@st.cache_data(ttl=300)
def get_market_data(ticker, interval="15m"):
    df = yf.download(ticker, period="60d", interval=interval, progress=False)
    if not df.empty and isinstance(df.columns, pd.MultiIndex): 
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

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Setări")
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
    mod_calcul = st.radio("Miză după:", ["Suma în £", "Număr Unități (Qty)"])
    if mod_calcul == "Suma în £":
        miza_valoare = st.number_input("Suma (£):", value=100.0, step=10.0)
        qty_manual = None
    else:
        qty_manual = st.number_input("Unități (Qty):", value=10, step=1)
        miza_valoare = None

    mult_sl = st.slider("Sensibilitate SL (ATR):", 1.0, 5.0, 2.0)
    rr_ratio = st.slider("Target Profit (Ratio):", 0.5, 5.0, 1.5)
    spread_val = st.number_input("Spread estimat ($):", value=0.05, format="%.4f")
    comision_minim = st.number_input("Comision Broker (£):", value=10.0)

# --- 4. LOGICĂ ȘI CALCULE ---
df = get_market_data(ticker_input)
curs_live = get_exchange_rate()

if not df.empty and len(df) > 200: # Ne asigurăm că avem destule date pentru EMA200
    close = df['Close']
    pret_acum = float(close.iloc[-1])
    
    # Indicatori
    df['EMA200'] = close.ewm(span=200, adjust=False).mean()
    df['RSI'] = calculate_rsi_wilder(close)
    
    # MACD
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # ATR
    tr = pd.concat([df['High']-df['Low'], abs(df['High']-close.shift()), abs(df['Low']-close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean().iloc[-1]
    
    # --- NOUL SISTEM DE SCOR (Suma va fi mereu 100%) ---
    # Calculăm un singur "Scor Bullish" (șansa ca prețul să urce)
    scor_bullish = 50 
    
    rsi_val = df['RSI'].iloc[-1]
    ema_val = df['EMA200'].iloc[-1]
    macd_val = df['MACD'].iloc[-1]
    sig_val = df['Signal'].iloc[-1]

    # Trend (Cântărește cel mai mult)
    if pret_acum > ema_val:
        scor_bullish += 15
    else:
        scor_bullish -= 15
        
    # Momentum (RSI)
    if rsi_val < 40: # Supravândut, șanse să urce
        scor_bullish += 15
    elif rsi_val > 60: # Supracumpărat, șanse să scadă
        scor_bullish -= 15
        
    # MACD Crossover
    if macd_val > sig_val:
        scor_bullish += 20
    else:
        scor_bullish -= 20

    # Limităm scorul între 5% și 95% (nimic nu e sigur 100% pe bursă)
    scor_bullish = max(5, min(95, scor_bullish))

    # Atribuim probabilitatea în funcție de ce buton a apăsat utilizatorul
    if "BUY" in directie:
        probabilitate = scor_bullish
    else:
        probabilitate = 100 - scor_bullish

    # --- GESTIUNE CANTITATE ---
    if mod_calcul == "Suma în £":
        cantitate = int((miza_valoare * levier * curs_live) / pret_acum)
        marja_gbp = miza_valoare
    else:
        cantitate = qty_manual
        marja_gbp = (cantitate * pret_acum) / (levier * curs_live)
    
    if cantitate <= 0: cantitate = 1

    # SL, TP & Breakeven
    dist_sl = atr * mult_sl
    dist_tp = dist_sl * rr_ratio
    sl_p = pret_acum - dist_sl if "BUY" in directie else pret_acum + dist_sl
    tp_p = pret_acum + dist_tp if "BUY" in directie else pret_acum - dist_tp
    
    cost_usd = (comision_minim * 2 * curs_live) + (spread_val * cantitate)
    breakeven_p = pret_acum + (cost_usd / cantitate) if "BUY" in directie else pret_acum - (cost_usd / cantitate)

    # --- 5. AFIȘARE ---
    st.title(f"📊 {ticker_input} | Preț: ${pret_acum:.2f}")
    
    # Culoarea barei se schimbă: verde pt probabilitate bună, roșu pt proastă
    color_prog = "green" if probabilitate >= 50 else "red"
    st.markdown(f"""
        <style>.stProgress > div > div > div > div {{ background-color: {color_prog}; }}</style>
    """, unsafe_allow_html=True)
    
    st.subheader(f"Probabilitate de Succes: {probabilitate}%")
    st.progress(probabilitate / 100)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cantitate", f"{cantitate}")
    col2.metric("Marjă Necesară", f"£{marja_gbp:.2f}")
    col3.metric("RSI", f"{rsi_val:.1f}")
    col4.metric("Breakeven", f"${breakeven_p:.2f}")

    # Grafic
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Preț")])
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA200'], line=dict(color='orange', width=1), name="EMA 200"))
    fig.add_hline(y=tp_p, line_dash="dash", line_color="green", annotation_text="TP")
    fig.add_hline(y=sl_p, line_dash="dash", line_color="red", annotation_text="SL")
    fig.add_hline(y=breakeven_p, line_dash="dot", line_color="blue", annotation_text="Zero Real")
    fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), template="plotly_white", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # Boxa Finală
    st.markdown(f"""
        <div style="background-color: #f1f5f9; padding: 20px; border-radius: 12px; border: 2px solid #0f172a; color: #1e293b;">
            <h3 style="margin: 0;">📋 Rezumat Ordin City Index</h3>
            <p style="font-size: 18px; margin: 10px 0;">
                <b>Direcție:</b> {"BUY" if "BUY" in directie else "SELL"} | <b>Cantitate:</b> {cantitate} <br>
                <b>Stop Loss:</b> ${sl_p:.2f} | <b>Take Profit:</b> ${tp_p:.2f}
            </p>
            <p style="color: #2563eb; font-weight: bold;">⚠️ Nu închide înainte de: ${breakeven_p:.4f}</p>
        </div>
    """, unsafe_allow_html=True)
else:
    st.error("Nu s-au găsit date suficiente pentru acest simbol. Asigură-te că simbolul este corect.")
