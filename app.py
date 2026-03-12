import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import numpy as np

# --- CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Asistent CFD: Misiunea 45k", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .main { background-color: #0d1117; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 8px; border: 1px solid #30363d; border-left: 4px solid #2ea043; }
    .stButton>button { width: 100%; font-weight: bold; border-radius: 5px; height: 3em; background-color: #2ea043; color: white; border: none; }
    .stButton>button:hover { background-color: #3fb950; }
    </style>
""", unsafe_allow_html=True)

# --- SISTEM SECURITATE ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True

    st.title("🚀 Misiunea 45K: Autentificare")
    pwd = st.text_input("Parola de acces:", type="password")
    if st.button("INTRĂ ÎN APLICAȚIE"):
        if pwd == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("❌ Parolă greșită.")
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

# --- SIDEBAR: SETĂRILE TALE ---
with st.sidebar:
    st.header("🎮 Setări Tranzacție")
    
    st.markdown("### 1. Ce tranzacționăm?")
    assets = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "SE", "MSTR", "META", "GOOGL"]
    ticker = st.selectbox("Compania:", sorted(assets))

    st.markdown("### 2. Viteza Tranzacției")
    timp_selectat = st.selectbox("Interval Grafic:", ["15 Minute (Day Trade)", "1 Oră (Swing)", "1 Zi (Termen Lung)"])
    dict_interval = {"15 Minute (Day Trade)": "15m", "1 Oră (Swing)": "1h", "1 Zi (Termen Lung)": "1d"}
    dict_perioada = {"15m": "60d", "1h": "730d", "1d": "1y"}
    interval_yf = dict_interval[timp_selectat]
    perioada_yf = dict_perioada[interval_yf]

    st.markdown("### 3. Direcția")
    directie = st.radio("Ce crezi că face prețul?", ["📈 CUMPĂR (Aștept creștere)", "📉 VÂND (Aștept scădere)"])

    st.divider()
    
    st.markdown("### 4. Managementul Banilor")
    mod_calcul = st.radio("Cum vrei să stabilești mărimea tranzacției?", 
                          ["Vreau să risc o sumă fixă (Recomandat)", "Introduc direct Cantitatea"])
    
    if mod_calcul == "Vreau să risc o sumă fixă (Recomandat)":
        risc_dorit = st.number_input("Cât ești dispus să pierzi maxim? (£):", value=150.0, step=50.0)
        cantitate_manuala = 0
    else:
        cantitate_manuala = st.number_input("Cantitate (CFD-uri pe City Index):", value=10, step=1)
        risc_dorit = 0

    if st.button("🚪 Delogare"):
        st.session_state["password_correct"] = False
        st.rerun()

# --- MOTORUL AI ---
try:
    df = yf.download(ticker, period=perioada_yf, interval=interval_yf, progress=False)
    
    if df.empty: 
        st.error("Nu am putut găsi date.")
    else:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close, high, low = df['Close'], df['High'], df['Low']
        pret_acum = float(close.iloc[-1])
        
        # Matematica pentru Risc (ATR)
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        # Calcul Stop Loss & Take Profit (Distante)
        sl_dist = atr * 1.5 
        tp_dist = sl_dist * 2 
        
        # --- CALCUL CANTITATE (MAGIA MATEMATICII) ---
        if mod_calcul == "Vreau să risc o sumă fixă (Recomandat)":
            # Împărțim riscul dorit la distanța până la Stop Loss pentru a afla cantitatea
            cantitate = int(risc_dorit / sl_dist)
            if cantitate < 1: cantitate = 1 # Ești obligat să iei minim 1 acțiune
        else:
            cantitate = cantitate_manuala

        # Calculam preturile finale
        if "CUMPĂR" in directie:
            sl, tp = pret_acum - sl_dist, pret_acum + tp_dist
        else:
            sl, tp = pret_acum + sl_dist, pret_acum - tp_dist

        pierdere_suma = cantitate * sl_dist
        profit_suma = cantitate * tp_dist
        marja_blocata = (cantitate * pret_acum) * 0.20 # Marja 20% estimată

        # Indicatori pt scor
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = (100 - (100 / (1 + gain/loss))).iloc[-1]
        ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]

        scor = 50
        if pret_acum > ema200: scor += 15
        else: scor -= 15
        if rsi < 35: scor += 15
        elif rsi > 65: scor -= 15
        scor = max(10, min(90, scor))
        probabilitate = scor if "CUMPĂR" in directie else (100 - scor)

        # --- AFIȘARE INTERFAȚĂ ---
        st.title(f"🧠 Analiză: {ticker} (Preț: ${pret_acum:.2f})")
        st.info(f"Șanse estimate de AI: **{probabilitate}%**")

        col_stanga, col_dreapta = st.columns([1, 1.5])
        
        with col_stanga:
            st.subheader("📋 Instrucțiuni City Index")
            
            if mod_calcul == "Vreau să risc o sumă fixă (Recomandat)":
                st.success(f"Pentru a risca aproximativ £{risc_dorit}, trebuie să introduci:\n\n**CANTITATE:** {cantitate}")
            else:
                st.info(f"Ai ales manual cantitatea:\n\n**CANTITATE:** {cantitate}")
            
            st.write(f"*Brokerul va bloca drept garanție (Marjă) suma de aprox. ${marja_blocata:.2f}*")
            
            st.error(f"🔴 **PUNE STOP LOSS LA:** ${sl:.2f}\n*Pierdere: -${pierdere_suma:.2f}*")
            st.success(f"🟢 **PUNE TAKE PROFIT LA:** ${tp:.2f}\n*Câștig: +${profit_suma:.2f}*")

            st.write("---")
            if st.button("💾 SALVEAZĂ TRANZACȚIA"):
                sheet = get_gsheet()
                if sheet:
                    now = datetime.now().strftime("%d/%m/%Y %H:%M")
                    directie_txt = "LONG" if "CUMPĂR" in directie else "SHORT"
                    try:
                        sheet.append_row([now, ticker, timp_selectat, directie_txt, cantitate, "Marjă 20%", f"{probabilitate}%", round(pret_acum, 2), round(sl, 2), round(tp, 2), f"-{round(pierdere_suma, 2)}", f"+{round(profit_suma, 2)}"])
                        st.toast("Salvat în Jurnal!")
                    except Exception as e:
                        st.error("Eroare la salvare.")

        with col_dreapta:
            df_plot = df.tail(60) 
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name="Preț"))
            fig.add_hline(y=pret_acum, line_dash="solid", line_color="white", annotation_text="Preț Acum")
            fig.add_hline(y=sl, line_dash="dash", line_color="red", annotation_text="Stop Loss")
            fig.add_hline(y=tp, line_dash="dash", line_color="green", annotation_text="Take Profit")
            fig.update_layout(template="plotly_dark", height=420, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Eroare: {e}")
