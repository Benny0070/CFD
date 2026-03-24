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
    p, h1, h2, h3, h4, h5, h6, span, label, div { color: #000000 !important; }
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
        cantitate_manuala = st.number_input("Câte acțiuni vrei (Amount):", value=5, step=1, min_value=1)
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
                    <h3 style="margin-top:0px;">📱 De introdus pe telefon:</h3>
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
