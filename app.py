import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import numpy as np

# --- CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Creier Digital ULTRA v3", layout="wide", page_icon="🧠")

# --- CSS PERSONALIZAT PENTRU LOOK PROFESIONAL ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #238636; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- SISTEM SECURITATE ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True

    st.title("🔐 Terminal Biometric")
    pwd = st.text_input("Introdu Cheia de Acces:", type="password")
    if st.button("AUTENTIFICARE"):
        if pwd == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("❌ Acces Respins")
    return False

if not check_password(): st.stop()

# --- CONECTARE GOOGLE SHEETS ---
def get_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["google_credentials"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Jurnal CFD").sheet1
    except: return None

# --- SIDEBAR - CONTROL TOTAL ---
with st.sidebar:
    st.header("⚙️ Configurare Trade")
    mod = st.radio("Sursă:", ["Listă", "Manual"])
    if mod == "Listă":
        assets = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "SE", "MSTR", "BTC-USD", "ETH-USD", "META", "GOOGL", "AMD"]
        ticker = st.selectbox("Alege Asset:", sorted(assets))
    else:
        ticker = st.text_input("Simbol Manual:", value="TSLA").upper()

    st.divider()
    cash = st.number_input("Capital (£):", value=100.0, step=10.0)
    levier = st.slider("Levier (Multiplier):", 1, 30, 5)
    directie = st.radio("Direcție Piață:", ["CUMPĂR (LONG)", "VÂND (SHORT)"])
    
    if st.button("🚪 LOG OUT"):
        st.session_state["password_correct"] = False
        st.rerun()

# --- MOTORUL ANALITIC (BACKEND) ---
try:
    df = yf.download(ticker, period="6mo", interval="1d", progress=False)
    if df.empty: st.error("Simbol invalid!")
    else:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # INDICATORI TEHNICI COMPLECȘI
        close = df['Close']
        high = df['High']
        low = df['Low']
        
        # 1. RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = 100 - (100 / (1 + gain/loss))
        rsi_val = rsi.iloc[-1]

        # 2. Bollinger Bands (Volatilitate & Overbought/Oversold)
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        upper_bb = sma20 + (std20 * 2)
        lower_bb = sma20 - (std20 * 2)

        # 3. ATR (Volatilitate Reală)
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        pret_acum = float(close.iloc[-1])
        volatilitate_pct = (atr / pret_acum) * 100

        # --- LOGICA AI DE PROBABILITATE ---
        scor = 50
        # Reguli Long
        if rsi_val < 35: scor += 15
        if pret_acum < lower_bb.iloc[-1]: scor += 15
        if pret_acum > sma20.iloc[-1]: scor += 10
        # Reguli Short
        if rsi_val > 65: scor -= 15
        if pret_acum > upper_bb.iloc[-1]: scor -= 15
        
        probabilitate = scor if "CUMPĂR" in directie else (100 - scor)
        
        # --- AFIȘARE INTERFAȚĂ ---
        st.title(f"🔍 Analiză Inteligentă: {ticker}")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preț Actual", f"${pret_acum:.2f}")
        c2.metric("RSI (14)", f"{rsi_val:.1f}")
        c3.metric("Volatilitate (ATR)", f"{volatilitate_pct:.2f}%")
        c4.metric("Șanse Succes", f"{probabilitate}%")

        # --- STRATEGIE MANAGEMENT RISC ---
        st.divider()
        col_st, col_dr = st.columns([1, 2])
        
        with col_st:
            st.subheader("🎯 Parametri Trade")
            # Calcul SL/TP dinamic bazat pe ATR (nu procente fixe)
            distanta_sl = atr * 2
            distanta_tp = atr * 3.5
            
            expunere = cash * levier
            
            if "CUMPĂR" in directie:
                sl = pret_acum - distanta_sl
                tp = pret_acum + distanta_tp
                # Preț faliment (unde pierzi tot cash-ul)
                faliment = pret_acum * (1 - (1/levier))
            else:
                sl = pret_acum + distanta_sl
                tp = pret_acum - distanta_tp
                faliment = pret_acum * (1 + (1/levier))

            pierdere_£ = (abs(pret_acum - sl) / pret_acum) * expunere
            profit_£ = (abs(pret_acum - tp) / pret_acum) * expunere

            st.error(f"🛑 STOP LOSS: ${sl:.2f}")
            st.success(f"💰 TAKE PROFIT: ${tp:.2f}")
            st.warning(f"💀 MARGIN CALL: ${faliment:.2f}")
            
            st.write(f"Risc: £{pierdere_£:.2f} | Profit: £{profit_£:.2f}")
            
            if st.button("🚀 EXECUȚĂ & SALVEAZĂ"):
                sheet = get_gsheet()
                if sheet:
                    now = datetime.now().strftime("%d/%m/%Y %H:%M")
                    sheet.append_row([now, ticker, ticker, directie, cash, f"1:{levier}", f"{probabilitate}%", round(pret_acum, 2), round(sl, 2), round(tp, 2), f"-{round(pierdere_£, 2)}", f"+{round(profit_£, 2)}"])
                    st.balloons()
                    st.toast("Salvat în Cloud!")

        with col_dr:
            # GRAFIC AVANSAT
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Preț"))
            fig.add_trace(go.Scatter(x=df.index, y=upper_bb, line=dict(color='rgba(173, 216, 230, 0.2)'), name="BB Upper"))
            fig.add_trace(go.Scatter(x=df.index, y=lower_bb, line=dict(color='rgba(173, 216, 230, 0.2)'), fill='tonexty', name="BB Lower"))
            fig.add_trace(go.Scatter(x=df.index, y=sma20, line=dict(color='orange', width=1), name="Trend (SMA20)"))
            fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)

        # --- JURNAL VIZUAL ---
        st.divider()
        with st.expander("📂 VEZI ISTORIC TRANZACȚII (CLOUDSHEETS)"):
            sheet = get_gsheet()
            if sheet:
                data = sheet.get_all_records()
                if data: st.table(pd.DataFrame(data).tail(10))

except Exception as e:
    st.error(f"S-a produs o eroare: {e}")
