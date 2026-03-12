import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURARE PAGINĂ (LIGHT MODE) ---
st.set_page_config(page_title="Asistent CFD: Misiunea 45k", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    /* Fundal alb și text negru pentru toată aplicația */
    .stApp { background-color: #ffffff; color: #000000; }
    
    /* Casetele cu numere (Metrice) */
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; border-left: 4px solid #2ea043; }
    
    /* Butoane mai prietenoase, verzi */
    .stButton>button { width: 100%; font-weight: bold; border-radius: 5px; height: 3.2em; background-color: #2ea043; color: white; border: none; }
    .stButton>button:hover { background-color: #1f772e; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- SISTEM SECURITATE ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True

    st.title("🚀 Misiunea 45K")
    pwd = st.text_input("Introdu parola ca să intrăm:", type="password")
    if st.button("INTRĂ"):
        if pwd == st.secrets.get("auth", {}).get("password", "parola"): 
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("❌ Parola nu e bună.")
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

# --- GESTIUNE BANI (Portofelul Tău) ---
if "banca_totala" not in st.session_state:
    st.session_state["banca_totala"] = 20000.0
if "bani_blocati" not in st.session_state:
    st.session_state["bani_blocati"] = 0.0

@st.cache_data(ttl=3600)
def get_curs_valutar():
    try: return float(yf.download("GBPUSD=X", period="1d", progress=False)['Close'].iloc[-1])
    except: return 1.27 
curs_gbp_usd = get_curs_valutar()

# --- MENIUL DIN STÂNGA ---
with st.sidebar:
    st.header("💼 Portofelul Tău")
    
    bani_liberi = st.session_state["banca_totala"] - st.session_state["bani_blocati"]
    st.metric("Bani Liberi", f"£{bani_liberi:.2f}")
    st.metric("Bani în Tranzacții", f"£{st.session_state['bani_blocati']:.2f}")
    
    progres = min(100, max(0, ((st.session_state["banca_totala"] - 20000) / 25000) * 100))
    st.progress(int(progres))
    st.caption(f"Ești la {progres:.1f}% din ținta de profit.")
    
    st.divider()
    
    st.markdown("### 1. Ce tranzacționăm?")
    assets = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "SE", "MSTR", "META", "GOOGL"]
    ticker = st.selectbox("Alege compania:", sorted(assets))

    st.markdown("### 2. Cât timp vrei să aștepți?")
    timp_selectat = st.selectbox("Strategie:", ["Mișcare Rapidă (15 minute)", "Câteva ore/zile (1 Oră)", "Termen lung (1 Zi)"])
    dict_interval = {"Mișcare Rapidă (15 minute)": "15m", "Câteva ore/zile (1 Oră)": "1h", "Termen lung (1 Zi)": "1d"}
    dict_perioada = {"15m": "60d", "1h": "730d", "1d": "1y"}
    interval_yf = dict_interval[timp_selectat]
    perioada_yf = dict_perioada[interval_yf]

    st.markdown("### 3. În ce direcție o ia?")
    directie = st.radio("Alegi să:", ["📈 CUMPERI (Crezi că prețul crește)", "📉 VINZI (Crezi că prețul scade)"])

    st.divider()
    
    st.markdown("### 4. Câți bani bagi?")
    suma_de_bagat_gbp = st.number_input("Suma pe care vrei s-o bagi (£):", value=500.0, step=100.0, min_value=10.0)

    if st.button("🚪 Ieși din cont"):
        st.session_state["password_correct"] = False
        st.rerun()

# --- ANALIZA ȘI MATEMATICA ---
try:
    with st.spinner('Descarc datele de pe bursă...'):
        df = yf.download(ticker, period=perioada_yf, interval=interval_yf, progress=False)
    
    if df.empty: 
        st.error(f"Nu găsesc date pentru {ticker} acum.")
    else:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close, high, low = df['Close'], df['High'], df['Low']
        pret_acum = float(close.iloc[-1])
        
        # Volatilitatea (cât se agită acțiunea)
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        st.title(f"📊 Analiză pentru {ticker} (Preț: ${pret_acum:.2f})")
        
        # --- SLIDERE SIMPLE ---
        st.write("Ajustează-ți planul de atac trăgând de butoanele de mai jos:")
        col_slider1, col_slider2 = st.columns(2)
        with col_slider1:
            multiplicator_sl = st.slider("Cât de repede vrei să te scoată dacă greșești? (Stop Loss):", 0.5, 3.0, 1.5, step=0.1, help="Mai la stânga = te scoate repede ca să nu pierzi mult. Mai la dreapta = îi dai acțiunii loc să respire.")
        with col_slider2:
            raport_rr = st.slider("Cât profit urmărești? (Take Profit):", 1.0, 5.0, 2.0, step=0.5, help="La 2.0 înseamnă că țintești să faci profit dublu față de cât riști să pierzi.")

        # --- CALCUL MAGIC PENTRU CITY INDEX ---
        sl_dist_usd = atr * multiplicator_sl 
        tp_dist_usd = sl_dist_usd * raport_rr 
        
        # Dacă bagi 500£, City Index îți dă de fapt putere de cumpărare de 5 ori mai mare (Levier).
        putere_cumparare_gbp = suma_de_bagat_gbp * 5 
        putere_cumparare_usd = putere_cumparare_gbp * curs_gbp_usd
        
        # Aflăm automat câte CFD-uri îți permiți să iei
        cantitate = int(putere_cumparare_usd / pret_acum) 
        if cantitate < 1: cantitate = 1

        if "CUMP" in directie:
            sl_usd, tp_usd = pret_acum - sl_dist_usd, pret_acum + tp_dist_usd
        else:
            sl_usd, tp_usd = pret_acum + sl_dist_usd, pret_acum - tp_dist_usd

        # Bani câștigați/pierduți (convertiți înapoi în Lire)
        pierdere_gbp = (cantitate * sl_dist_usd) / curs_gbp_usd
        profit_gbp = (cantitate * tp_dist_usd) / curs_gbp_usd

        # Șanse (AI)
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
        if raport_rr >= 3: scor -= 10 
        
        scor = max(15, min(95, scor))
        probabilitate = scor if "CUMP" in directie else (100 - scor)

        # --- REZUMAT UMAN ---
        st.markdown(f"""
        <div style="background-color: #f8f9fa; border-left: 5px solid #2ea043; padding: 20px; border-radius: 5px; color: #000000; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h3 style="margin-top:0px; color: #000000;">💡 Ce spune aplicația:</h3>
            <p style="font-size: 18px; margin-bottom: 0px;">
                „Vrei să bagi <strong>£{suma_de_bagat_gbp}</strong> pe {ticker}. Sistemul îți dă <strong>{probabilitate}%</strong> șanse să iasă bine.<br><br>
                Dacă prețul ajunge unde vrem noi, faci un profit net de <strong>+£{profit_gbp:.2f}</strong>.<br>
                Dacă planul pică, te scoatem din piață ca să pierzi doar <strong>-£{pierdere_gbp:.2f}</strong>.”
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.write("---")
        
        # --- CE SCRII PE TELEFON ---
        st.subheader("📱 Copiază valorile astea în City Index")
        col_c1, col_c2, col_c3 = st.columns(3)
        col_c1.info(f"🔢 **CANTITATE:**\n# {cantitate}")
        col_c2.error(f"🔴 **STOP LOSS:**\n$ {sl_usd:.2f}")
        col_c3.success(f"🟢 **TAKE PROFIT:**\n$ {tp_usd:.2f}")

        st.write("---")
        
        # --- GRAFIC LUMINOS ---
        st.subheader(f"Graficul pe scurt")
        df_plot = df.tail(80) 
        fig = go.Figure()
        
        fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name="Preț"))
        
        fig.add_hline(y=pret_acum, line_dash="solid", line_color="black", annotation_text=f"Preț Acum (${pret_acum:.2f})", annotation_font_color="black")
        fig.add_hline(y=sl_usd, line_dash="dash", line_color="red", annotation_text=f"Aici ieși pe minus")
        fig.add_hline(y=tp_usd, line_dash="dash", line_color="green", annotation_text=f"Aici iei profitul")
        
        fig.update_layout(template="plotly_white", height=500, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)

        # --- SALVARE ---
        st.write("---")
        if st.button("✅ Am pus comanda pe telefon (Salvează)"):
            sheet = get_gsheet()
            if sheet:
                now = datetime.now().strftime("%d/%m/%Y %H:%M")
                dir_txt = "LONG" if "CUMP" in directie else "SHORT"
                try:
                    sheet.append_row([
                        now, ticker, timp_selectat, dir_txt, cantitate, 
                        f"Bani băgați: £{suma_de_bagat_gbp}", f"{probabilitate}%", 
                        round(pret_acum, 2), round(sl_usd, 2), round(tp_usd, 2), 
                        f"-£{round(pierdere_gbp, 2)}", f"+£{round(profit_gbp, 2)}"
                    ])
                    st.session_state["bani_blocati"] += suma_de_bagat_gbp
                    st.toast("Bravo! Am salvat tranzacția.")
                    st.rerun() 
                except Exception as e:
                    st.error("Nu am putut salva. Verifică Excel-ul.")

        # --- ISTORIC ---
        st.divider()
        with st.expander("📂 Vezi Istoricul Tranzacțiilor"):
            sheet = get_gsheet()
            if sheet:
                data = sheet.get_all_records()
                if data:
                    df_istoric = pd.DataFrame(data)
                    st.dataframe(df_istoric.iloc[::-1], use_container_width=True)

                    if st.button("♻️ O tranzacție s-a terminat? Eliberează banii blocați"):
                        st.session_state["bani_blocati"] = 0.0
                        st.rerun()

except Exception as e:
    st.error(f"Ceva nu a mers bine: {e}")
