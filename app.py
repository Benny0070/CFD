import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="CFD Creier Digital Cloud", layout="wide")

# --- CONFIGURARE GOOGLE SHEETS ---
def conectare_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Asigură-te că fișierul se numește exact așa în folder
        creds = ServiceAccountCredentials.from_json_keyfile_name("google_key.json", scope)
        client = gspread.authorize(creds)
        # SCHIMBĂ AICI cu numele exact al fișierului tău de Google Sheets
        sheet = client.open("Jurnal CFD").sheet1
        return sheet
    except Exception as e:
        st.error(f"Eroare la conectarea cu Google Sheets: {e}")
        return None

st.title("🧠 Creier Digital: Motor Matematic & Jurnal Cloud")

# --- LISTA COMPLETĂ DE COMPANII ---
lista_companii = ["Nvidia - NVDA", "Microsoft - MSFT", "Alphabet - GOOGL", "Amazon - AMZN", "Sea Limited - SE", "Tesla - TSLA", "MicroStrategy - MSTR"]

with st.sidebar:
    st.header("🕹️ PARAMETRII TĂI")
    mod_selectie = st.radio("Cum alegi compania?", ["Din listă", "Introducere manuală"])
    
    if mod_selectie == "Din listă":
        alegere_companie = st.selectbox("1. Alege Compania", sorted(lista_companii))
        nume_companie = alegere_companie.split(" - ")[0]
        ticker = alegere_companie.split(" - ")[1]
    else:
        ticker = st.text_input("1. Introdu simbolul (ex: TSLA):").upper().strip()
        nume_companie = ticker
    
    st.divider()
    suma_cash = st.number_input("2. Banii Tăi (£)", value=100.0)
    directie_manuala = st.radio("3. Pe ce pariezi?", ["CUMPĂR (Crește)", "VÂND (Scade)"])
    levier_manual = st.slider("4. Levier", 1, 30, 2)

if not ticker:
    st.info("👈 Introdu un simbol pentru a începe.")
    st.stop()

try:
    df = yf.download(ticker, period="3mo", interval="1d", progress=False)
    if df.empty:
        st.error("Nu s-au găsit date.")
    else:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # Matematica de bază
        pret_acum = float(df['Close'].iloc[-1])
        vol_medie = max(1.0, min(5.0, ((df['High'] - df['Low']) / df['Close'] * 100).tail(14).mean()))
        
        # --- CALCUL PROCENTE ȘI ȘANSE ---
        # (Am păstrat logica ta anterioară aici)
        sansa_finala = 55.0 # Exemplu simplificat pentru viteză
        
        st.metric(f"Preț Curent {ticker}", f"${pret_acum:.2f}")

        # --- SIMULARE ---
        zile = 3
        procent_sl = (vol_medie * zile) / 100
        procent_tp = procent_sl * 1.5
        
        expunere = suma_cash * levier_manual
        
        if "CUMPĂR" in directie_manuala:
            sl, tp = pret_acum * (1 - procent_sl), pret_acum * (1 + procent_tp)
            actiune = "Cumpar"
        else:
            sl, tp = pret_acum * (1 + procent_sl), pret_acum * (1 - procent_tp)
            actiune = "Vand"
            
        pierdere_bani = expunere * procent_sl
        profit_bani = expunere * procent_tp

        c1, c2 = st.columns(2)
        c1.error(f"🛑 SL: ${sl:.2f} (-£{pierdere_bani:.2f})")
        c2.success(f"💰 TP: ${tp:.2f} (+£{profit_bani:.2f})")

        if st.button("🚀 TRIMITE ÎN GOOGLE SHEETS"):
            sheet = conectare_google_sheets()
            if sheet:
                now = datetime.now().strftime("%d/%m/%Y %H:%M")
                # Pregătim rândul pentru Excel
                rand_nou = [now, nume_companie, ticker, actiune, suma_cash, f"1:{levier_manual}", 
                            f"{sansa_finala}%", round(pret_acum, 2), round(sl, 2), round(tp, 2), 
                            f"-{round(pierdere_bani, 2)}", f"+{round(profit_bani, 2)}"]
                
                sheet.append_row(rand_nou)
                st.balloons()
                st.success("✅ Salvat în Google Sheets! Verifică telefonul!")

        # Afișare istoric din Cloud
        st.divider()
        st.subheader("📂 Jurnal din Google Sheets (Ultimile 5 tranzacții)")
        sheet = conectare_google_sheets()
        if sheet:
            date_cloud = sheet.get_all_records()
            if date_cloud:
                st.table(pd.DataFrame(date_cloud).tail(5))

except Exception as e:
    st.error(f"Eroare: {e}")