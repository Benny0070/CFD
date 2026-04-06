import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Asistent CFD: Misiunea 45k", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .stApp, [data-testid="stSidebar"], [data-testid="stHeader"] { background-color: #ffffff !important; }
    p, h1, h2, h3, h4, h5, h6, span, label, div { color: #000000 !important; }
    .stButton>button { background-color: #2ea043 !important; color: #ffffff !important; font-weight: bold !important; border-radius: 8px; }
    .stMetric { background-color: #f8fafc !important; border: 1px solid #e2e8f0 !important; border-radius: 10px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("💼 Control Panel")
    
    if st.button("🔄 REFRESH DATE"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    ticker = st.text_input("Simbol (ex: NVDA, TSLA):", value="NVDA").upper().strip()
    directie = st.radio("Direcție Trade:", ["📈 CUMPĂRARE (Long)", "📉 VÂNZARE (Short)"])
    
    st.divider()
    mod_calcul = st.selectbox("Miză bazată pe:", ["Suma în Bani (£)", "Număr de Acțiuni (Qty)"])
    if mod_calcul == "Suma în Bani (£)":
        suma_gbp = st.number_input("Suma disponibilă (£):", value=100.0, step=10.0)
        cantitate_manuala = None
    else:
        cantitate_manuala = st.number_input("Câte acțiuni (Qty):", value=10.0, step=1.0, min_value=1.0)
        suma_gbp = None

    # SETĂRI OPTIMIZATE (ATR 2.0, Ratio 1.2)
    st.divider()
    multiplicator_sl = st.slider("Sensibilitate Stop Loss (ATR):", 0.5, 4.0, 2.0, 0.1)
    raport_rr = st.slider("Țintă Profit (Ratio):", 0.1, 5.0, 1.2, 0.1)
    
    # COSTURI CITY INDEX (Estimative)
    st.subheader("⚙️ Setări Broker (City Index)")
    comision_minim = st.number_input("Comision Minim (£):", value=10.0, help="City Index ia minim ~10 GBP pe trade la acțiuni.")
    spread_puncte = st.number_input("Spread estimat ($):", value=0.05, step=0.01, help="Diferența de preț Bid/Ask")

# --- 3. LOGICĂ ȘI CALCULE ---
if ticker:
    try:
        df = yf.download(ticker, period="60d", interval="15m", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            close_prices = df['Close']
            pret_acum = float(close_prices.iloc[-1])
            curs_gbp_usd = 1.28  # Curs estimat

            # --- INDICATORI ---
            ema200_series = close_prices.ewm(span=200, adjust=False).mean()
            ema200_val = ema200_series.iloc[-1]
            
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi_val = 100 - (100 / (1 + (gain/loss))).iloc[-1]
            
            exp1 = close_prices.ewm(span=12, adjust=False).mean()
            exp2 = close_prices.ewm(span=26, adjust=False).mean()
            macd_val = (exp1 - exp2).iloc[-1]
            signal_val = (exp1 - exp2).ewm(span=9, adjust=False).mean().iloc[-1]

            # --- PROBABILITATE ---
            scor = 50
            if pret_acum > ema200_val: scor += 15
            else: scor -= 15
            if rsi_val < 35: scor += 20
            elif rsi_val > 65: scor -= 20
            if macd_val > signal_val: scor += 15
            else: scor -= 15
            
            probabilitate = scor if "CUMP" in directie else (100 - scor)
            probabilitate = max(10, min(95, int(probabilitate)))

            # --- MANAGEMENT RISC ---
            levier = 5
            if mod_calcul == "Suma în Bani (£)":
                cantitate = int(((suma_gbp * levier) * curs_gbp_usd) / pret_acum)
                marja_gbp = suma_gbp
            else:
                cantitate = int(cantitate_manuala)
                marja_gbp = ((cantitate * pret_acum) / levier) / curs_gbp_usd

            # ATR & Target
            tr = pd.concat([df['High']-df['Low'], abs(df['High']-close_prices.shift()), abs(df['Low']-close_prices.shift())], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            
            dist_sl = atr * multiplicator_sl
            dist_tp = dist_sl * raport_rr
            
            sl_p = pret_acum - dist_sl if "CUMP" in directie else pret_acum + dist_sl
            tp_p = pret_acum + dist_tp if "CUMP" in directie else pret_acum - dist_tp

            # --- CALCUL BREAKEVEN (Punctul 0 real) ---
            # Cost total = (Comision Deschidere + Inchidere) + (Spread * Cantitate)
            cost_total_gbp = (comision_minim * 2) + ((spread_puncte * cantitate) / curs_gbp_usd)
            necesar_miscare_pret = (cost_total_gbp * curs_gbp_usd) / cantitate
            
            if "CUMP" in directie:
                breakeven_p = pret_acum + necesar_miscare_pret
            else:
                breakeven_p = pret_acum - necesar_miscare_pret

            # --- AFIȘARE UI ---
            st.title(f"📊 {ticker} la ${pret_acum:.2f}")
            
            col_a, col_b = st.columns([2,1])
            with col_a:
                st.subheader(f"Probabilitate Succes: {probabilitate}%")
                st.progress(probabilitate / 100)
            with col_b:
                st.warning(f"⚠️ Pierzi £{cost_total_gbp:.2f} instant la deschidere (Spread+Taxe).")

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Cantitate", f"{cantitate}")
            with c2:
                st.metric("Marjă", f"£{marja_gbp:.2f}")
            with c3:
                profit_net_gbp = (((abs(tp_p - pret_acum) * cantitate) / curs_gbp_usd) - cost_total_gbp)
                st.metric("Profit NET (După taxe)", f"£{profit_net_gbp:.2f}")
            with c4:
                st.metric("Preț Breakeven", f"${breakeven_p:.2f}")

            # --- GRAFIC INTERACTIV ---
            fig = go.Figure(data=[go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Preț"
            )])
            
            fig.add_trace(go.Scatter(x=df.index, y=ema200_series, line=dict(color='orange', width=1), name="EMA 200"))
            
            # Liniile strategice
            fig.add_hline(y=tp_p, line_dash="dash", line_color="green", annotation_text="Profit Target")
            fig.add_hline(y=sl_p, line_dash="dash", line_color="red", annotation_text="Stop Loss")
            fig.add_hline(y=breakeven_p, line_dash="dot", line_color="blue", annotation_text="ZERO REAL (Breakeven)", annotation_font_color="blue")
            
            fig.update_layout(height=500, margin=dict(l=0, r=0, t=0, b=0), template="plotly_white", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- BOXA CITY INDEX ---
            box_c = "#dcfce7" if "CUMP" in directie else "#fee2e2"
            txt_c = "#16a34a" if "CUMP" in directie else "#dc2626"
            
            st.markdown(f"""
                <div style="background-color: {box_c}; padding: 25px; border-radius: 15px; border: 3px solid {txt_c}; text-align: center; margin-top: 20px;">
                    <h2 style="color: #000; margin: 0;">📱 City Index: {"BUY (Long)" if "CUMP" in directie else "SELL (Short)"}</h2>
                    <p style="font-size: 22px; color: #000; margin: 15px 0;">
                        <b>Amount:</b> {cantitate} | <b>TP:</b> ${tp_p:.2f} | <b>SL:</b> ${sl_p:.2f}
                    </p>
                    <p style="color: #d97706; font-size: 16px;"><b>ATENȚIE:</b> Nu închide trade-ul până prețul nu depășește <b>${breakeven_p:.2f}</b>, altfel ieși pe minus!</p>
                </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Eroare tehnică: {e}")
else:
    st.info("Introdu un simbol în stânga pentru a începe analiza.")
