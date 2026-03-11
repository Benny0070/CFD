import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="CFD Creier Digital PRO", layout="wide")

# --- FUNCȚIE CONECTARE GOOGLE SHEETS (Smart Connect) ---
def conectare_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Logica de detecție: Cloud vs Local
        if "google_credentials" in st.secrets:
            # SUNTEM PE STREAMLIT CLOUD
            creds_dict = dict(st.secrets["google_credentials"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # SUNTEM LOCAL (pe calculatorul tău)
            creds = ServiceAccountCredentials.from_json_keyfile_name("google_key.json", scope)
            
        client = gspread.authorize(creds)
        # Asigură-te că numele fișierului din Google Drive este exact acesta:
        sheet = client.open("Jurnal CFD").sheet1
        return sheet
    except Exception as e:
        st.error(f"⚠️ Eroare la conectarea cu Google Sheets: {e}")
        return None

# --- INTERFAȚA ȘI LOGICA ---
st.title("🧠 Creier Digital: Trading Math & Cloud Journal")

# Lista de sugestii (poți adăuga oricâte aici)
lista_companii = ["Nvidia - NVDA", "Tesla - TSLA", "Apple - AAPL", "Microsoft - MSFT", "Sea Limited - SE", "MicroStrategy - MSTR", "Bitcoin - BTC-USD"]

with st.sidebar:
    st.header("🕹️ CONTROL PANEL")
    mod_selectie = st.radio("Cum alegi compania?", ["Din listă", "Introducere manuală"])
    
    if mod_selectie == "Din listă":
        alegere = st.selectbox("1. Alege Compania", sorted(lista_companii))
        ticker = alegere.split(" - ")[1]
        nume_afisat = alegere.split(" - ")[0]
    else:
        ticker = st.text_input("1. Scrie Simbolul (ex: TSLA, META):").upper().strip()
        nume_afisat = ticker
    
    st.divider()
    suma_cash = st.number_input("2. Banii Tăi (£)", value=100.0, step=10.0)
    directie = st.radio("3. Direcție", ["CUMPĂR (Crește)", "VÂND (Scade)"])
    levier = st.slider("4. Levier (Multiplier)", 1, 30, 5)

if not ticker:
    st.info("👈 Introdu un simbol în stânga pentru a începe analiza.")
    st.stop()

# --- DESCĂRCARE DATE ---
try:
    with st.spinner(f"Analizez {ticker}..."):
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        
    if df.empty:
        st.error("Nu am găsit date pentru acest simbol. Verifică dacă e scris corect.")
    else:
        # Curățare coloane (pentru versiuni noi de yfinance)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        pret_acum = float(df['Close'].iloc[-1])
        
        # Calcule Tehnice Simple
        df['SMA30'] = df['Close'].rolling(window=30).mean()
        volatilitate = ((df['High'] - df['Low']) / df['Close'] * 100).tail(14).mean()
        volatilitate = max(1.2, min(5.0, volatilitate)) # Limităm între 1.2% și 5%

        # --- AFIȘARE METRICI ---
        st.subheader(f"Analiză Real-Time: {nume_afisat}")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Preț Actual", f"${pret_acum:.2f}")
        col_m2.metric("Fluctuație Medie/Zi", f"{volatilitate:.2f}%")
        col_m3.metric("Expunere Totală", f"£{suma_cash * levier:.2f}")

        # --- GRAFIC ---
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Preț")])
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA30'], line=dict(color='orange', width=1.5), name="Media 30z"))
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- CALCULATOR STRATEGIE ---
        st.divider()
        st.subheader("🎯 Strategie Sugerată (Managementul Riscului)")
        
        # Estimăm o mișcare bazată pe volatilitate pentru următoarele 3 zile
        procent_miscare = (volatilitate * 2.5) / 100
        
        if "CUMPĂR" in directie:
            sl = pret_acum * (1 - procent_miscare)
            tp = pret_acum * (1 + (procent_miscare * 1.5))
            tip_actiune = "Cumpar"
        else:
            sl = pret_acum * (1 + procent_miscare)
            tp = pret_acum * (1 - (procent_miscare * 1.5))
            tip_actiune = "Vand"

        pierdere_estimata = (suma_cash * levier) * procent_miscare
        profit_estimat = (suma_cash * levier) * (procent_miscare * 1.5)

        c1, c2, c3 = st.columns(3)
        c1.error(f"🛑 STOP LOSS\n\n**${sl:.2f}**\n\n(-£{pierdere_estimata:.2f})")
        c2.success(f"💰 TAKE PROFIT\n\n**${tp:.2f}**\n\n(+£{profit_estimat:.2f})")
        
        with c3:
            st.write("###")
            if st.button("🚀 SALVEAZĂ ÎN JURNAL", use_container_width=True):
                sheet = conectare_google_sheets()
                if sheet:
                    now = datetime.now().strftime("%d/%m/%Y %H:%M")
                    # Rândul care pleacă spre Google Sheets
                    rand = [now, nume_afisat, ticker, tip_actiune, suma_cash, f"1:{levier}", 
                            "Calculat", round(pret_acum, 2), round(sl, 2), round(tp, 2), 
                            f"-{round(pierdere_estimata, 2)}", f"+{round(profit_estimat, 2)}"]
                    sheet.append_row(rand)
                    st.balloons()
                    st.success("Trimis cu succes în Cloud!")

        # --- ISTORIC ---
        st.divider()
        if st.checkbox("Vezi Jurnalul tău complet"):
            sheet = conectare_google_sheets()
            if sheet:
                date = sheet.get_all_records()
                if date:
                    st.dataframe(pd.DataFrame(date).iloc[::-1], use_container_width=True)
                else:
                    st.info("Jurnalul este gol momentan.")

except Exception as e:
    st.error(f"Eroare aplicație: {e}")
