import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURARE ---
st.set_page_config(page_title="Asistent CFD: Misiunea 45k", layout="wide", page_icon="🚀")

# (CSS-ul tău rămâne neschimbat aici pentru fundal alb și text negru...)
st.markdown("""
    <style>
    .stApp { background-color: #ffffff !important; }
    p, h1, h2, h3, h4, h5, h6import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURARE PAGINĂ (LIGHT MODE) ---
st.set_page_config(page_title="Asistent CFD: Misiunea 45k", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .stApp, [data-testid="stSidebar"], [data-testid="stHeader"] { background-color: #ffffff !important; }
    p, h1, h2, h3, h4, h5, h6, span, label, div { color: #000000 !important; }
    .stButton>button { background-color: #2ea043 !important; color: #ffffff !important; font-weight: bold !important; width: 100% !important; }
    .stMetric { background-color: #f4f6f9 !important; border-radius: 8px !important; border: 1px solid #cccccc !important; padding: 15px !important; }
    </style>
""", unsafe_allow_html=True)

# --- MENIUL DIN STÂNGA ---
with st.sidebar:
    st.header("💼 Configurare Trade")
    ticker = st.text_input("Simbol (ex: NVDA, AAPL):", value="NVDA").upper().strip()
    directie = st.radio("Direcție:", ["📈 CUMPĂRARE (Long)", "📉 VÂNZARE (Short)"])
    
    st.divider()
    
    # --- ALEGERE MOD CALCUL ---
    mod_calcul = st.selectbox("Miză bazată pe:", ["Suma în Bani (£)", "Număr de Acțiuni (Qty)"])
    
    if mod_calcul == "Suma în Bani (£)":
        suma_gbp = st.number_input("Suma disponibilă (£):", value=100.0, step=10.0)
        cantitate_manuala = None
    else:
        # REPARAT: Folosim step=1 și value=5 (întregi) ca să nu mai dea eroarea de tip mixt
        cantitate_manuala = st.number_input("Câte acțiuni vrei (Amount):", value=5.0, step=0.1, min_value=1.0)
        suma_gbp = None

    st.divider()
    multiplicator_sl = st.slider("Sensibilitate Stop Loss (ATR):", 0.5, 3.0, 1.5, 0.1)
    raport_rr = st.slider("Țintă Profit (Ratio):", 1.0, 5.0, 2.0, 0.1)

# --- ANALIZĂ ȘI LOGICĂ ---
if ticker:
    try:
        # Luăm date suficiente pentru EMA 200
        df = yf.download(ticker, period="60d", interval="15m", progress=False)
        
        if df.empty:
            st.error("Nu am găsit date pentru acest simbol.")
        else:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            close = df['Close']
            pret_acum = float(close.iloc[-1])
            curs_gbp_usd = 1.28 # Aproximativ (poate fi automatizat)

            # --- CALCUL INDICATORI (PROBABILITATE) ---
            # 1. EMA 200
            ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
            
            # 2. RSI Corect
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + (gain/loss))).iloc[-1]
            
            # 3. MACD
            exp1 = close.ewm(span=12, adjust=False).mean()
            exp2 = close.ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            macd_val, signal_val = macd.iloc[-1], signal.iloc[-1]

            # --- CALCUL SCOR AI ---
            scor_bullish = 50
            if pret_acum > ema200: scor_bullish += 15
            else: scor_bullish -= 15
            
            if rsi < 35: scor_bullish += 20
            elif rsi > 65: scor_bullish -= 20
            
            if macd_val > signal_val: scor_bullish += 15
            else: scor_bullish -= 15
            
            # Ajustare probabilitate în funcție de ce ai ales (BUY sau SELL)
            if "CUMP" in directie:
                probabilitate = scor_bullish
            else:
                probabilitate = 100 - scor_bullish
            
            probabilitate = max(10, min(95, int(probabilitate)))

            # --- GESTIUNE CANTITATE ȘI MARJĂ ---
            levier = 5
            if mod_calcul == "Suma în Bani (£)":
                putere_usd = (suma_gbp * levier) * curs_gbp_usd
                cantitate = int(putere_usd / pret_acum)
                marja_gbp = suma_gbp
            else:
                cantitate = cantitate_manuala
                marja_gbp = ((cantitate * pret_acum) / levier) / curs_gbp_usd

            # --- CALCUL SL / TP (ATR) ---
            tr = pd.concat([df['High'] - df['Low'], 
                            abs(df['High'] - close.shift()), 
                            abs(df['Low'] - close.shift())], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            
            dist_sl = atr * multiplicator_sl
            dist_tp = dist_sl * raport_rr
            
            if "CUMP" in directie:
                sl, tp = pret_acum - dist_sl, pret_acum + dist_tp
            else:
                sl, tp = pret_acum + dist_sl, pret_acum - dist_tp

            # --- AFIȘARE REZULTATE ---
            st.title(f"📊 Analiză {ticker}")
            
            # Probabilitatea sub formă de Progress Bar
            st.subheader(f"Probabilitate Succes: {probabilitate}%")
            st.progress(probabilitate / 100)

            col1, col2, col3 = st.columns(3)
            col1.metric("Preț Acum", f"${pret_acum:.2f}")
            col2.metric("Acțiuni (Amount)", f"{cantitate}")
            col3.metric("Marjă Necesară", f"£{marja_gbp:.2f}")

            # REZUMAT VIZUAL PENTRU TELEFON
            st.write("---")
            culoare_box = "#dcfce7" if "CUMP" in directie else "#fee2e2"
            text_actiune = "BUY (CUMPĂRĂ)" if "CUMP" in directie else "SELL (VINDE)"
            
            st.markdown(f"""
                <div style="background-color: {culoare_box}; padding: 20px; border-radius: 10px; border: 2px solid #333;">
                    <h2 style="margin-top:0px; text-align:center;"> City Index: {text_actiune}</h2>
                    <p style="font-size: 20px; text-align:center;">
                        Amount: <b>{cantitate}</b> | 
                        Take Profit: <b>${tp:.2f}</b> | 
                        Stop Loss: <b>${sl:.2f}</b>
                    </p>
                </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Eroare la procesare: {e}"), span, label, div { color: #000000 !important; }
    .stButton>button { background-color: #2ea043 !important; color: #ffffff !important; }
    </style>
""", unsafe_allow_html=True)

# --- MENIUL DIN STÂNGA ---
with st.sidebar:
    st.header("💼 Configurare Trade")
    ticker = st.text_input("Simbol:", value="NVDA").upper().strip()
    directie = st.radio("Direcție:", ["📈 CUMPĂRARE (Long)", "📉 VÂNZARE (Short)"])
    
    st.divider()
    
    # --- NOU: ALEGERE MOD CALCUL ---
    mod_calcul = st.selectbox("Cum vrei să introduci miza?", ["Suma în Bani (£)", "Număr de Acțiuni (Qty)"])
    
    if mod_calcul == "Suma în Bani (£)":
        suma_gbp = st.number_input("Suma pe care o ai (£):", value=100.0, step=10.0)
        cantitate_manuala = None
    else:
        cantitate_manuala = st.number_input("Câte acțiuni vrei (Amount):", value=5.0, step=0.1, min_value=1.0)
        suma_gbp = None

    st.divider()
    multiplicator_sl = st.slider("Stop Loss (Sensibilitate):", 0.5, 3.0, 1.5, 0.1)
    raport_rr = st.slider("Take Profit (Raport):", 1.0, 5.0, 2.0, 0.1)

# --- LOGICA DE PIAȚĂ ---
try:
    if ticker:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            pret_acum = float(df['Close'].iloc[-1])
            
            # Curs valutar pentru conversie (folosim un fix sau dynamic)
            curs_gbp_usd = 1.27 # Îl poți lăsa fix sau prelua din yf ca în codul anterior
            
            # --- CALCUL CANTITATE SAU MARJĂ ---
            levier = 5 # City Index oferă de obicei 1:5 pe acțiuni (20% marjă)
            
            if mod_calcul == "Suma în Bani (£)":
                putere_usd = (suma_gbp * levier) * curs_gbp_usd
                cantitate = int(putere_usd / pret_acum)
                if cantitate < 1: cantitate = 1
                marja_utilizata_gbp = suma_gbp
            else:
                cantitate = cantitate_manuala
                # Marja = (Preț * Cantitate) / Levier / Curs
                valoare_totala_usd = pret_acum * cantitate
                marja_utilizata_gbp = (valoare_totala_usd / levier) / curs_gbp_usd

            # --- CALCUL STOP LOSS & TAKE PROFIT (ATR) ---
            tr = pd.concat([df['High'] - df['Low'], 
                            abs(df['High'] - df['Close'].shift()), 
                            abs(df['Low'] - df['Close'].shift())], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            
            dist_sl = atr * multiplicator_sl
            dist_tp = dist_sl * raport_rr
            
            if "CUMP" in directie:
                sl_usd, tp_usd = pret_acum - dist_sl, pret_acum + dist_tp
            else:
                sl_usd, tp_usd = pret_acum + dist_sl, pret_acum - dist_tp

            # --- AFIȘARE REZULTATE ---
            st.title(f"📊 Plan de atac: {ticker}")
            
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                st.metric("Preț Intrare", f"${pret_acum:.2f}")
                st.metric("Cost Marjă (Bani blocați)", f"£{marja_utilizata_gbp:.2f}")
            
            with col_res2:
                profit_potential = (abs(tp_usd - pret_acum) * cantitate) / curs_gbp_usd
                pierdere_potentiala = (abs(sl_usd - pret_acum) * cantitate) / curs_gbp_usd
                st.write(f"💰 **Profit estimat:** +£{profit_potential:.2f}")
                st.write(f"⚠️ **Pierdere estimată:** -£{pierdere_potentiala:.2f}")

            # --- TABLOUL PENTRU CITY INDEX ---
            st.markdown(f"""
                <div style="background-color: #f8fafc; border: 2px solid #2ea043; padding: 20px; border-radius: 10px;">
                    <h3 style="margin-top:0px;"> De introdus pe telefon:</h3>
                    <p style="font-size: 20px;">
                        1. Direcție: <strong>{"BUY" if "CUMP" in directie else "SELL"}</strong><br>
                        2. Amount (Cantitate): <strong>{cantitate}</strong><br>
                        3. Take Profit: <strong>${tp_usd:.2f}</strong><br>
                        4. Stop Loss: <strong>${sl_usd:.2f}</strong>
                    </p>
                </div>
            """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Eroare: {e}")
