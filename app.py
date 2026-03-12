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
    st.header("🎮 Panou de Comandă")
    
    st.markdown("### 🏆 Misiunea 45K")
    balanta_curenta = st.number_input("Balanța contului Demo (£):", value=20000.0, step=100.0)
    progres = min(100, max(0, ((balanta_curenta - 20000) / 25000) * 100))
    st.progress(int(progres))
    st.caption(f"Ai realizat {progres:.1f}% din profitul vizat!")
    
    st.divider()
    
    st.markdown("### 1. Ce analizăm?")
    assets = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "SE", "MSTR", "BTC-USD", "META", "GOOGL"]
    ticker = st.selectbox("Compania:", sorted(assets))

    st.markdown("### 2. Viteza Tranzacției")
    timp_selectat = st.selectbox("Interval Grafic (Timeframe):", ["15 Minute (Rapid/Day Trade)", "1 Oră (Swing Trade)", "1 Zi (Termen Lung)"])
    
    dict_interval = {"15 Minute (Rapid/Day Trade)": "15m", "1 Oră (Swing Trade)": "1h", "1 Zi (Termen Lung)": "1d"}
    dict_perioada = {"15m": "60d", "1h": "730d", "1d": "1y"}
    
    interval_yf = dict_interval[timp_selectat]
    perioada_yf = dict_perioada[interval_yf]

    st.markdown("### 3. Date Financiare")
    cash = st.number_input("Cât riști din cont? (£):", value=1000.0, step=100.0)
    levier = st.slider("Levier (Multiplicator):", 1, 30, 5)
    directie = st.radio("Ce crezi că face prețul?", ["📈 CUMPĂR (Sper că urcă)", "📉 VÂND (Sper că scade)"])
    
    if st.button("🚪 Delogare"):
        st.session_state["password_correct"] = False
        st.rerun()

# --- MOTORUL AI (FUNDAMENTAL + TEHNIC) ---
try:
    df = yf.download(ticker, period=perioada_yf, interval=interval_yf, progress=False)
    
    if df.empty: 
        st.error("Nu am putut găsi date pentru această companie.")
    else:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close, high, low = df['Close'], df['High'], df['Low']
        pret_acum = float(close.iloc[-1])
        
        # Matematica Tehnică
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = (100 - (100 / (1 + gain/loss))).iloc[-1]

        ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        upper_bb, lower_bb = sma20 + (std20 * 2), sma20 - (std20 * 2)

        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        # Interpretări Umane
        starea_pietei = "Prea Scumpă" if rsi > 70 else "Ieftină (Reducere)" if rsi < 30 else "Echilibrată"
        trend = "Crescător" if pret_acum > ema200 else "În Scădere"
        
        # Calcul Șanse
        scor = 50
        if pret_acum > ema200: scor += 15
        else: scor -= 15
        if rsi < 35: scor += 15
        elif rsi > 65: scor -= 15
        if pret_acum <= lower_bb.iloc[-1]: scor += 15
        if pret_acum >= upper_bb.iloc[-1]: scor -= 15

        scor = max(10, min(90, scor))
        probabilitate = scor if "CUMPĂR" in directie else (100 - scor)

        # Mesaj AI
        if probabilitate > 65: mesaj_ai = "✅ **Undă Verde!** Condițiile sunt excelente pentru ce vrei să faci."
        elif probabilitate < 40: mesaj_ai = "❌ **Risc Maxim!** Algoritmul zice că e o idee proastă. Ești contra curentului."
        else: mesaj_ai = "⚖️ **Piața e neutră.** Nu e cel mai bun moment de intrat. Poate mai aștepți."

        # --- AFIȘARE INTERFAȚĂ ---
        st.title(f"🧠 Creierul Digital: {ticker}")
        st.info(mesaj_ai)
        
        # RADAR ȘTIRI (Avertizare Fundamentală)
        try:
            ticker_obj = yf.Ticker(ticker)
            stiri = ticker_obj.news
            if stiri and len(stiri) > 0:
                titlu_stire = stiri[0]['title']
                st.warning(f"📰 **Radar Știri (Atenție la volatilitate):** {titlu_stire}")
        except:
            pass

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preț Execuție", f"${pret_acum:.2f}")
        c2.metric("Trend (Bursa)", trend)
        c3.metric("Evaluare Moment", starea_pietei)
        c4.metric("Șanse de Câștig", f"{probabilitate}%", delta_color="normal" if probabilitate >= 50 else "inverse")

        st.divider()
        col_stanga, col_dreapta = st.columns([1, 1.5])
        
        with col_stanga:
            st.subheader("📝 Foaia City Index")
            
            expunere = cash * levier
            taxa_broker = expunere * 0.001 # Estimare Spread 0.1%

            distanta_faliment = pret_acum * (0.95 / levier)
            sl_dist = min(atr * 1.5, distanta_faliment * 0.8) 
            tp_dist = sl_dist * 2 

            if "CUMPĂR" in directie:
                sl, tp = pret_acum - sl_dist, pret_acum + tp_dist
                faliment = pret_acum - distanta_faliment
            else:
                sl, tp = pret_acum + sl_dist, pret_acum - tp_dist
                faliment = pret_acum + distanta_faliment

            pierdere_suma = ((abs(pret_acum - sl) / pret_acum) * expunere) + taxa_broker
            profit_suma = ((abs(pret_acum - tp) / pret_acum) * expunere) - taxa_broker

            st.write(f"Cu **£{cash}** (Levier 1:{levier}), controlezi **£{expunere}** în piață.")
            st.caption(f"*(Taxă estimată broker/Spread: £{taxa_broker:.2f})*")
            
            st.error(f"🔴 **STOP LOSS:** ${sl:.2f}\n\n*Riști maxim: **-£{pierdere_suma:.2f}***")
            st.success(f"🟢 **TAKE PROFIT:** ${tp:.2f}\n\n*Încasezi curat: **+£{profit_suma:.2f}***")
            st.warning(f"💀 **Preț Faliment (Margin Call):** ${faliment:.2f}")

            st.write("---")
            if st.button("💾 CONFIRMĂ & SALVEAZĂ"):
                sheet = get_gsheet()
                if sheet:
                    now = datetime.now().strftime("%d/%m/%Y %H:%M")
                    directie_txt = "LONG" if "CUMPĂR" in directie else "SHORT"
                    try:
                        sheet.append_row([now, ticker, timp_selectat, directie_txt, cash, f"1:{levier}", f"{probabilitate}%", round(pret_acum, 2), round(sl, 2), round(tp, 2), f"-{round(pierdere_suma, 2)}", f"+{round(profit_suma, 2)}"])
                        st.toast("Tranzacție înregistrată!")
                    except Exception as e:
                        st.error("Eroare la conectarea cu Jurnalul.")

        with col_dreapta:
            st.subheader("Harta Bătăliei (Grafic)")
            df_plot = df.tail(60) 
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name="Preț"))
            
            fig.add_hline(y=pret_acum, line_dash="solid", line_color="white", annotation_text="Preț Acum")
            fig.add_hline(y=sl, line_dash="dash", line_color="red", annotation_text="Stop Loss")
            fig.add_hline(y=tp, line_dash="dash", line_color="green", annotation_text="Take Profit")

            fig.update_layout(template="plotly_dark", height=420, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)

        # --- STATISTICI CONT ---
        st.divider()
        st.subheader("📊 Analiza Performanței Tale")
        sheet = get_gsheet()
        if sheet:
            data = sheet.get_all_records()
            if data:
                df_istoric = pd.DataFrame(data)
                total_tranzactii = len(df_istoric)
                st.write(f"Ai planificat/executat **{total_tranzactii}** tranzacții până acum.")
                with st.expander("📂 Deschide Jurnalul Complet"):
                    st.dataframe(df_istoric.iloc[::-1], use_container_width=True)
            else:
                st.info("Jurnalul este gol. Fă prima tranzacție pentru a genera statistici!")

except Exception as e:
    st.error(f"Sistemul întâmpină o eroare: {e}")
