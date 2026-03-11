import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Creier Digital PRO v2", layout="wide", page_icon="📈")

# --- SISTEM DE LOGIN (DIN SECRETS) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True

    st.markdown("""
        <style>
        .login-box { padding: 2rem; border-radius: 10px; background-color: #161b22; border: 1px solid #30363d; text-align: center; }
        </style>
        <div class="login-box">
            <h1>🔒 Terminal Securizat</h1>
            <p>Introdu cheia de acces pentru a activa algoritmii.</p>
        </div>
    """, unsafe_allow_html=True)
    
    password_input = st.text_input("Parola:", type="password")
    if st.button("AUTENTIFICARE"):
        if password_input == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ Acces respins. Parolă incorectă.")
    return False

if not check_password():
    st.stop()

# --- CONECTARE CLOUD (GOOGLE SHEETS) ---
def conectare_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "google_credentials" in st.secrets:
            creds_dict = dict(st.secrets["google_credentials"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("google_key.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open("Jurnal CFD").sheet1
        return sheet
    except Exception as e:
        st.sidebar.error(f"Eroare Cloud: {e}")
        return None

# --- SIDEBAR: PARAMETRI ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2092/2092663.png", width=80)
    st.header("🕹️ Panou Control")
    
    mod_selectie = st.radio("Sursă Date:", ["Listă Predefinită", "Căutare Manuală"])
    
    lista_companii = [
        "Nvidia - NVDA", "Tesla - TSLA", "Apple - AAPL", "Microsoft - MSFT", 
        "Amazon - AMZN", "Sea Limited - SE", "MicroStrategy - MSTR", 
        "Bitcoin - BTC-USD", "Ethereum - ETH-USD", "Meta - META", "Google - GOOGL"
    ]
    
    if mod_selectie == "Listă Predefinită":
        alegere = st.selectbox("Selectează Asset:", sorted(lista_companii))
        ticker = alegere.split(" - ")[1]
        nume_afisat = alegere.split(" - ")[0]
    else:
        ticker = st.text_input("Simbol (ex: TSLA, GOLD):").upper().strip()
        nume_afisat = ticker

    st.divider()
    suma_cash = st.number_input("Capital (£):", value=100.0, step=50.0)
    directie = st.radio("Strategie:", ["CUMPĂR (Long)", "VÂND (Short)"])
    levier = st.slider("Levier (Leverage):", 1, 30, 5)
    
    if st.button("DECONECTARE"):
        st.session_state["password_correct"] = False
        st.rerun()

# --- LOGICA DE ANALIZĂ ȘI ESTIMARE AI ---
if ticker:
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if df.empty:
            st.warning("⚠️ Simbolul nu a fost găsit.")
        else:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            # 1. Indicatori Tehnici
            pret_acum = float(df['Close'].iloc[-1])
            # RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            rsi_acum = df['RSI'].iloc[-1]
            
            # Trend (SMA 20 vs SMA 50)
            df['SMA20'] = df['Close'].rolling(window=20).mean()
            df['SMA50'] = df['Close'].rolling(window=50).mean()
            sma20 = df['SMA20'].iloc[-1]
            sma50 = df['SMA50'].iloc[-1]
            
            # Volatilitate
            volatilitate = ((df['High'] - df['Low']) / df['Close'] * 100).tail(14).mean()
            
            # 2. ALGORITM ESTIMARE AI
            scor_buy = 50
            if rsi_acum < 30: scor_buy += 20  # Oversold
            if rsi_acum > 70: scor_buy -= 20  # Overbought
            if pret_acum > sma20: scor_buy += 10 # Trend pozitiv
            if sma20 > sma50: scor_buy += 10 # Golden Cross context
            
            probabilitate = scor_buy if "CUMPĂR" in directie else (100 - scor_buy)
            
            # 3. INTERFAȚĂ REZULTATE
            st.title(f"📊 Analiză AI: {nume_afisat}")
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Preț Curent", f"${pret_acum:.2f}")
            m2.metric("RSI (14)", f"{rsi_acum:.1f}")
            m3.metric("Volatilitate", f"{volatilitate:.2f}%")
            m4.metric("Probabilitate Succes", f"{probabilitate}%")

            # Mesaj AI
            culoare_ai = "#00ff00" if probabilitate > 55 else "#ff4b4b"
            st.markdown(f"""
                <div style="background-color:#161b22; padding:20px; border-radius:10px; border-left: 10px solid {culoare_ai};">
                    <h2 style="margin:0;">🤖 Verdict AI: {probabilitate}% șanse pentru {directie}</h2>
                    <p style="color:gray;">Bazat pe RSI, SMA20/50 și volatilitatea curentă a pieței.</p>
                </div>
            """, unsafe_allow_html=True)

            # 4. GRAFIC INTERACTIV
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Preț"))
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='yellow', width=1), name="SMA 20"))
            fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 5. CALCULATOR MANAGEMENT RISC
            st.divider()
            st.subheader("🛠️ Setări Tranzacție")
            
            risc_procent = (volatilitate * 2.5) / 100
            expunere = suma_cash * levier
            
            if "CUMPĂR" in directie:
                sl, tp = pret_acum * (1 - risc_procent), pret_acum * (1 + (risc_procent * 2))
                tip_log = "LONG (Cumpărare)"
            else:
                sl, tp = pret_acum * (1 + risc_procent), pret_acum * (1 - (risc_procent * 2))
                tip_log = "SHORT (Vânzare)"

            p_pierdere = expunere * risc_procent
            p_profit = expunere * (risc_procent * 2)

            col_a, col_b, col_c = st.columns(3)
            col_a.error(f"🛑 STOP LOSS\n\n**${sl:.2f}**\n\nPierdere: -£{p_pierdere:.2f}")
            col_b.success(f"💰 TAKE PROFIT\n\n**${tp:.2f}**\n\nProfit: +£{p_profit:.2f}")
            
            with col_c:
                st.write("###")
                if st.button("💾 EXECUȚĂ & SALVEAZĂ ÎN CLOUD", use_container_width=True):
                    sheet = conectare_google_sheets()
                    if sheet:
                        try:
                            now = datetime.now().strftime("%d/%m/%Y %H:%M")
                            row = [now, nume_afisat, ticker, tip_log, suma_cash, f"1:{levier}", 
                                   f"{probabilitate}%", round(pret_acum, 2), round(sl, 2), 
                                   round(tp, 2), f"-{round(p_pierdere, 2)}", f"+{round(p_profit, 2)}"]
                            sheet.append_row(row)
                            st.balloons()
                            st.success("Tranzacție înregistrată în Google Sheets!")
                        except Exception as e:
                            st.error(f"Eroare la scriere: {e}")

            # 6. JURNAL CLOUD VIZUAL
            st.divider()
            if st.checkbox("🔍 Deschide Jurnalul Istoric"):
                sheet = conectare_google_sheets()
                if sheet:
                    data = sheet.get_all_records()
                    if data:
                        df_jurnal = pd.DataFrame(data)
                        st.dataframe(df_jurnal.iloc[::-1], use_container_width=True)
                    else:
                        st.info("Jurnalul este gol.")

    except Exception as e:
        st.error(f"Eroare la procesarea datelor: {e}")
