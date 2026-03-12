import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Asistent CFD: Misiunea 45k", layout="wide", page_icon="🚀")

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

    st.title("🚀 Misiunea 45K: Acces Asistent")
    pwd = st.text_input("Parola de acces:", type="password")
    if st.button("INTRĂ ÎN APLICAȚIE"):
        if pwd == st.secrets.get("auth", {}).get("password", "parola_mea_secreta"): # Fallback pt testare locala
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

# --- GESTIUNE PORTOFEL ---
if "banca_totala" not in st.session_state:
    st.session_state["banca_totala"] = 20000.0
if "bani_blocati" not in st.session_state:
    st.session_state["bani_blocati"] = 0.0

# --- PRELUARE CURS VALUTAR GBP -> USD ---
@st.cache_data(ttl=3600) # Se actualizeaza la o ora
def get_curs_valutar():
    try:
        return float(yf.download("GBPUSD=X", period="1d", progress=False)['Close'].iloc[-1])
    except:
        return 1.27 # Curs de rezerva in caz de eroare (media istorica recenta)

curs_gbp_usd = get_curs_valutar()

# --- SIDEBAR: PANOU DE COMANDĂ ---
with st.sidebar:
    st.header("💼 Portofelul Tău (Demo)")
    
    bani_liberi = st.session_state["banca_totala"] - st.session_state["bani_blocati"]
    st.metric("Bani Liberi (Gata de joc)", f"£{bani_liberi:.2f}")
    st.metric("Bani Blocați (Garanție)", f"£{st.session_state['bani_blocati']:.2f}")
    
    progres = min(100, max(0, ((st.session_state["banca_totala"] - 20000) / 25000) * 100))
    st.progress(int(progres))
    st.caption(f"Progres Misiune: {progres:.1f}% din profitul vizat.")
    
    st.divider()
    
    st.markdown("### 1. Alege Pariul")
    assets = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "SE", "MSTR", "META", "GOOGL"]
    ticker = st.selectbox("Compania (Simbol bursier):", sorted(assets))

    st.markdown("### 2. Timpul de joc")
    timp_selectat = st.selectbox("Interval:", ["15 Minute (Rapid)", "1 Oră (Swing)", "1 Zi (Lent)"])
    dict_interval = {"15 Minute (Rapid)": "15m", "1 Oră (Swing)": "1h", "1 Zi (Lent)": "1d"}
    dict_perioada = {"15m": "60d", "1h": "730d", "1d": "1y"}
    interval_yf = dict_interval[timp_selectat]
    perioada_yf = dict_perioada[interval_yf]

    st.markdown("### 3. Direcția")
    directie = st.radio("Cum joci?", ["📈 CUMPĂR (Sper că urcă)", "📉 VÂND (Sper că scade)"])

    st.divider()
    
    st.markdown("### 4. Biletul de Intrare")
    suma_pariata_gbp = st.number_input("Câți bani blochezi ca garanție? (£):", value=500.0, step=100.0, min_value=10.0, max_value=float(max(10.0, bani_liberi)))

    if st.button("🚪 Delogare"):
        st.session_state["password_correct"] = False
        st.rerun()

# --- MOTORUL AI ---
try:
    with st.spinner('Scanez bursa...'):
        df = yf.download(ticker, period=perioada_yf, interval=interval_yf, progress=False)
    
    if df.empty: 
        st.error(f"Nu am putut găsi date pentru {ticker}. Verifică dacă bursa este deschisă.")
    else:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close, high, low = df['Close'], df['High'], df['Low']
        pret_acum = float(close.iloc[-1])
        
        # Matematica volatilitatii (ATR)
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        st.title(f"🎛️ Strategie: {ticker} (Preț actual: ${pret_acum:.2f})")
        
        # --- BUTOANE INTERACTIVE (Riscul si Lacomia) ---
        col_slider1, col_slider2 = st.columns(2)
        with col_slider1:
            multiplicator_sl = st.slider("Apetit la Risc (Distanța până la Pierdere):", 0.5, 3.0, 1.5, step=0.1, help="De câte ori se poate mișca prețul normal înainte să te scoată pe minus.")
        with col_slider2:
            raport_rr = st.slider("Lăcomie (Multiplicator Câștig):", 1.0, 5.0, 2.0, step=0.5, help="Ex: 2.0 înseamnă că țintești să câștigi dublu față de cât poți pierde.")

        # --- CALCUL MATEMATIC CITY INDEX ---
        # 1. Calculam distanțele pe grafic în DOLARI
        sl_dist_usd = atr * multiplicator_sl 
        tp_dist_usd = sl_dist_usd * raport_rr 
        
        # 2. Transformam Garanția din Lire în Dolari pentru a afla Cantitatea
        suma_pariata_usd = suma_pariata_gbp * curs_gbp_usd
        # Marja estimata pentru acțiuni pe City Index e 20% (Levier 1:5)
        cantitate = int(suma_pariata_usd / (pret_acum * 0.20)) 
        if cantitate < 1: cantitate = 1

        # 3. Stabilim preturile exacte pentru Stop Loss si Take Profit in DOLARI
        if "CUMPĂR" in directie:
            sl_usd, tp_usd = pret_acum - sl_dist_usd, pret_acum + tp_dist_usd
        else:
            sl_usd, tp_usd = pret_acum + sl_dist_usd, pret_acum - tp_dist_usd

        # 4. Calculam Profitul/Pierderea in DOLARI
        pierdere_usd = cantitate * sl_dist_usd
        profit_usd = cantitate * tp_dist_usd

        # 5. Transformam inapoi in LIRE (£) pentru afisarea catre tine
        pierdere_gbp = pierdere_usd / curs_gbp_usd
        profit_gbp = profit_usd / curs_gbp_usd

        # --- SCOR AI (Sansa de reusita) ---
        scor = 50
        ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = (100 - (100 / (1 + gain/loss))).iloc[-1]

        if pret_acum > ema200: scor += 15
        else: scor -= 15
        if rsi < 35: scor += 15
        elif rsi > 65: scor -= 15
        
        # Penalizare daca esti prea lacom
        if raport_rr >= 3: scor -= 10 
        
        scor = max(15, min(95, scor))
        probabilitate = scor if "CUMPĂR" in directie else (100 - scor)

        # --- SFATUL CREIERULUI ---
        st.markdown(f"""
        <div style="background-color: #1a202c; border-left: 5px solid #e3b341; padding: 20px; border-radius: 5px;">
            <h3 style="margin-top:0px;">💡 Analiza Asistentului:</h3>
            <p style="font-size: 18px;">
                „Dacă blochezi <strong>£{suma_pariata_gbp}</strong> drept garanție pe acțiunile <strong>{ticker}</strong>:<br><br>
                Algoritmul estimează o șansă de reușită de <strong>{probabilitate}%</strong>. <br>
                Dacă prețul atinge linia verde, vei face un profit net de <strong>+£{profit_gbp:.2f}</strong>. <br>
                Dacă piața se întoarce împotriva ta și atinge linia roșie, pierzi maxim <strong>-£{pierdere_gbp:.2f}</strong>.”
            </p>
        </div>
        """, unsafe_allow_html=True)

        # --- INSTRUCȚIUNI CITY INDEX ---
        st.divider()
        st.subheader("📱 Copiază exact asta în telefon (Aplicația City Index)")
        
        col_c1, col_c2, col_c3 = st.columns(3)
        col_c1.info(f"🔢 **CANTITATE:**\n# {cantitate}")
        col_c2.error(f"🔴 **STOP LOSS:**\n$ {sl_usd:.2f}")
        col_c3.success(f"🟢 **TAKE PROFIT:**\n$ {tp_usd:.2f}")

        st.write("---")
        
        # --- GRAFICUL GIGANTIC ---
        st.subheader(f"Harta Bătăliei: Evoluția {ticker}")
        df_plot = df.tail(100) # Ultimul calup de lumânări
        fig = go.Figure()
        
        # Lumânările japoneze
        fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name="Preț"))
        
        # Liniile noastre de acțiune
        fig.add_hline(y=pret_acum, line_dash="solid", line_color="white", annotation_text=f"Preț Acum (${pret_acum:.2f})")
        fig.add_hline(y=sl_usd, line_dash="dash", line_color="red", annotation_text=f"Stop Loss: Pierzi -£{pierdere_gbp:.0f}")
        fig.add_hline(y=tp_usd, line_dash="dash", line_color="green", annotation_text=f"Take Profit: Câștigi +£{profit_gbp:.0f}")
        
        fig.update_layout(template="plotly_dark", height=650, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)

        # --- BUTONUL DE EXECUȚIE ---
        if st.button("💾 BAGĂ BILETUL (Blochează Garanția & Salvează)"):
            sheet = get_gsheet()
            if sheet:
                now = datetime.now().strftime("%d/%m/%Y %H:%M")
                dir_txt = "LONG" if "CUMPĂR" in directie else "SHORT"
                try:
                    # Inseram randul in Google Sheets
                    sheet.append_row([
                        now, ticker, timp_selectat, dir_txt, cantitate, 
                        f"Garanție: £{suma_pariata_gbp}", f"{probabilitate}%", 
                        round(pret_acum, 2), round(sl_usd, 2), round(tp_usd, 2), 
                        f"-£{round(pierdere_gbp, 2)}", f"+£{round(profit_gbp, 2)}"
                    ])
                    # Actualizam state-ul aplicatiei
                    st.session_state["bani_blocati"] += suma_pariata_gbp
                    st.toast("Tranzacție salvată! Garanția a fost blocată din portofel.")
                    st.rerun() 
                except Exception as e:
                    st.error("Eroare la salvarea în Excel. Verifică permisiunile (credentials.json).")

        # --- JURNAL ---
        st.divider()
        with st.expander("📂 Jurnalul Tranzacțiilor Tale"):
            sheet = get_gsheet()
            if sheet:
                data = sheet.get_all_records()
                if data:
                    df_istoric = pd.DataFrame(data)
                    st.dataframe(df_istoric.iloc[::-1], use_container_width=True)

                    if st.button("♻️ S-a închis o tranzacție pe telefon? Deblochează Garanția (Înapoi la 0)"):
                        st.session_state["bani_blocati"] = 0.0
                        st.rerun()

except Exception as e:
    st.error(f"Eroare neașteptată de sistem: {e}")
