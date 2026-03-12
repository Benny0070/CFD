import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import numpy as np

# --- CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Asistent CFD: Misiunea 45k", layout="wide", page_icon="🎰")

st.markdown("""
    <style>
    .main { background-color: #0d1117; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 8px; border: 1px solid #30363d; border-left: 4px solid #e3b341; }
    .stButton>button { width: 100%; font-weight: bold; border-radius: 5px; height: 3em; background-color: #e3b341; color: black; border: none; }
    .stButton>button:hover { background-color: #f1c453; color: black; }
    </style>
""", unsafe_allow_html=True)

# --- SISTEM SECURITATE ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True

    st.title("🎰 Misiunea 45K: Acces Asistent")
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

# --- GESTIUNE PORTOFEL (Banca Ta) ---
if "banca_totala" not in st.session_state:
    st.session_state["banca_totala"] = 20000.0
if "bani_blocati" not in st.session_state:
    st.session_state["bani_blocati"] = 0.0

# --- SIDEBAR: SETĂRILE TALE ---
with st.sidebar:
    st.header("💼 Portofelul Tău (Demo)")
    
    # Afișare bani
    bani_liberi = st.session_state["banca_totala"] - st.session_state["bani_blocati"]
    st.metric("Bani Disponibili (Cash)", f"£{bani_liberi:.2f}")
    st.metric("Bani Blocați în Pariuri", f"£{st.session_state['bani_blocati']:.2f}")
    
    progres = min(100, max(0, ((st.session_state["banca_totala"] - 20000) / 25000) * 100))
    st.progress(int(progres))
    st.caption(f"Progres spre +25k profit: {progres:.1f}%")
    
    st.divider()
    
    st.markdown("### 1. Alege Pariul")
    assets = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "SE", "MSTR", "META", "GOOGL", "BTC-USD"]
    ticker = st.selectbox("Compania:", sorted(assets))

    st.markdown("### 2. Timpul de joc")
    timp_selectat = st.selectbox("Interval:", ["15 Minute (Acțiune Rapidă)", "1 Oră (Aștept câteva zile)", "1 Zi (Termen Lung)"])
    dict_interval = {"15 Minute (Acțiune Rapidă)": "15m", "1 Oră (Aștept câteva zile)": "1h", "1 Zi (Termen Lung)": "1d"}
    dict_perioada = {"15m": "60d", "1h": "730d", "1d": "1y"}
    interval_yf = dict_interval[timp_selectat]
    perioada_yf = dict_perioada[interval_yf]

    st.markdown("### 3. Direcția")
    directie = st.radio("Cum joci?", ["📈 CUMPĂR (Sper că urcă)", "📉 VÂND (Sper că scade)"])

    st.divider()
    
    st.markdown("### 4. Cât bagi în joc?")
    suma_pariata = st.number_input("Suma pariată (Bani blocați ca garanție):", value=500.0, step=100.0, max_value=float(bani_liberi))

    if st.button("🚪 Delogare"):
        st.session_state["password_correct"] = False
        st.rerun()

# --- MOTORUL AI ȘI MATEMATICA JOCULUI ---
try:
    df = yf.download(ticker, period=perioada_yf, interval=interval_yf, progress=False)
    
    if df.empty: 
        st.error("Nu am putut găsi date.")
    else:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close, high, low = df['Close'], df['High'], df['Low']
        pret_acum = float(close.iloc[-1])
        
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        # --- BUTOANE INTERACTIVE (PENTRU JOACA TA) ---
        st.title(f"🎛️ Panou de Control & Analiză: {ticker}")
        
        st.markdown("### 🎚️ Trage de setări pentru a-ți face strategia:")
        col_slider1, col_slider2 = st.columns(2)
        with col_slider1:
            # Multiplicator Stop Loss
            multiplicator_sl = st.slider("Cât spațiu de mișcare îi dai acțiunii? (Distanța până la Stop Loss):", 0.5, 3.0, 1.5, step=0.1, help="Cu cât e mai mare, cu atât e mai greu să te scoată din joc din greșeală, dar riști să pierzi mai mulți bani dacă scade grav.")
        with col_slider2:
            # Multiplicator Profit
            raport_rr = st.slider("Cât ești de lacom? (Raport Câștig/Risc):", 1.0, 5.0, 2.0, step=0.5, help="La 2.0 înseamnă că țintești să câștigi dublu față de cât riști.")

        # Calcul distante bazate pe butoanele tale
        sl_dist = atr * multiplicator_sl 
        tp_dist = sl_dist * raport_rr 
        
        # Calcul CANTITATE bazat pe Pariul tau. Pe City index marja e de obicei 20% (levier 1:5)
        # Banii pariati = (Cantitate * Pret) * 20%  => Cantitate = Suma Pariata / (Pret * 0.20)
        cantitate = int(suma_pariata / (pret_acum * 0.20))
        if cantitate < 1: cantitate = 1

        if "CUMPĂR" in directie:
            sl, tp = pret_acum - sl_dist, pret_acum + tp_dist
        else:
            sl, tp = pret_acum + sl_dist, pret_acum - tp_dist

        pierdere_suma = cantitate * sl_dist
        profit_suma = cantitate * tp_dist

        # Scor AI Dinamic (Se adaptează la lăcomia ta)
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
        
        # Penalizare pentru lăcomie extremă sau SL prea mic
        if raport_rr > 3: scor -= 10 # E greu să atingi un profit imens
        if multiplicator_sl < 1: scor -= 10 # Te scoate piața imediat la cel mai mic sughiț

        scor = max(5, min(95, scor))
        probabilitate = scor if "CUMPĂR" in directie else (100 - scor)

        # --- SFATUL CREIERULUI (PONTUL DIRECT) ---
        st.divider()
        directie_text = "CUMPERI" if "CUMPĂR" in directie else "VINZI"
        
        st.markdown(f"""
        <div style="background-color: #1a202c; border-left: 5px solid #e3b341; padding: 20px; border-radius: 5px;">
            <h3>💡 Pontul Creierului Digital:</h3>
            <p style="font-size: 18px;">
                „Dacă eu aș juca acum, aș folosi fix setările de mai jos. Vrei să pariezi <strong>£{suma_pariata}</strong> că prețul o să se ducă în direcția ta. <br><br>
                Ai o probabilitate estimată de <strong>{probabilitate}%</strong> ca această mutare să fie câștigătoare.<br>
                Dacă prețul ajunge la ținta ta, o să transformi acei £{suma_pariata} blocați într-un <strong>profit curat de +£{profit_suma:.2f}</strong>. <br>
                Dacă dai greș, pierderea va fi de <strong>-£{pierdere_suma:.2f}</strong>. Acesta este un joc de calcul matematic bun.”
            </p>
        </div>
        """, unsafe_allow_html=True)

        # --- INSTRUCȚIUNI CITY INDEX ---
        st.divider()
        col_stanga, col_dreapta = st.columns([1, 1.5])
        
        with col_stanga:
            st.subheader("📝 Copiază în City Index")
            st.info(f"Pentru a pune la bătaie £{suma_pariata}, trebuie să scrii:\n\n**CANTITATE:** {cantitate}")
            
            st.error(f"🔴 **La STOP LOSS scrii:** ${sl:.2f}")
            st.success(f"🟢 **La TAKE PROFIT scrii:** ${tp:.2f}")

            st.write("---")
            if st.button("💾 BAGĂ BILETUL (Salvează & Actualizează Banca)"):
                sheet = get_gsheet()
                if sheet:
                    now = datetime.now().strftime("%d/%m/%Y %H:%M")
                    dir_txt = "LONG" if "CUMPĂR" in directie else "SHORT"
                    try:
                        # Salvăm în Google Sheets
                        sheet.append_row([now, ticker, timp_selectat, dir_txt, cantitate, f"Pariu: £{suma_pariata}", f"{probabilitate}%", round(pret_acum, 2), round(sl, 2), round(tp, 2), f"-{round(pierdere_suma, 2)}", f"+{round(profit_suma, 2)}"])
                        
                        # Actualizăm Banii din sesiune (Portofelul)
                        st.session_state["bani_blocati"] += suma_pariata
                        
                        st.balloons()
                        st.toast("Tranzacție salvată! Banii au fost blocați în portofel.")
                        st.rerun() # Reincarcam ca sa se actualizeze meniul din stanga
                    except Exception as e:
                        st.error("Eroare la salvarea în Excel.")

        with col_dreapta:
            df_plot = df.tail(80) 
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name="Preț"))
            fig.add_hline(y=pret_acum, line_dash="solid", line_color="white", annotation_text="Preț Actual")
            fig.add_hline(y=sl, line_dash="dash", line_color="red", annotation_text=f"Pierdere (-£{pierdere_suma:.0f})")
            fig.add_hline(y=tp, line_dash="dash", line_color="green", annotation_text=f"Câștig (+£{profit_suma:.0f})")
            fig.update_layout(template="plotly_dark", height=420, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        with st.expander("📂 Jurnalul Tranzacțiilor Tale"):
            sheet = get_gsheet()
            if sheet:
                data = sheet.get_all_records()
                if data:
                    df_istoric = pd.DataFrame(data)
                    st.dataframe(df_istoric.iloc[::-1], use_container_width=True)

                    # Optiune pentru a elibera banii cand o tranzactie e inchisa in City Index
                    if st.button("♻️ S-a închis o tranzacție? Resetează Banii Blocați la 0"):
                        st.session_state["bani_blocati"] = 0.0
                        st.toast("Banii blocați au fost eliberați înapoi în portofelul tău liber!")
                        st.rerun()

except Exception as e:
    st.error(f"Eroare: {e}")
