import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Asistent CFD: Misiunea 45k", layout="wide", page_icon="🚀")

# CSS pentru fundal alb și text negru
st.markdown("""
    <style>
    .stApp, [data-testid="stSidebar"], [data-testid="stHeader"] { background-color: #ffffff !important; }
    p, h1, h2, h3, h4, h5, h6, span, label, div { color: #000000 !important; }
    .stButton>button { background-color: #2ea043 !important; color: #ffffff !important; font-weight: bold !important; border-radius: 8px; }
    .stMetric { background-color: #f8fafc !important; border: 1px solid #e2e8f0 !important; border-radius: 10px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. SIDEBAR (CONFIGURARE) ---
with st.sidebar:
    st.header("💼 Control Panel")
    
    # BUTON REFRESH
    if st.button("🔄 REFRESH DATE (Actualizează Preț)"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    ticker = st.text_input("Simbol (ex: NVDA, TSLA, BTC-USD):", value="NVDA").upper().strip()
    directie = st.radio("Direcție Trade:", ["📈 CUMPĂRARE (Long)", "📉 VÂNZARE (Short)"])
    
    st.divider()
    
    mod_calcul = st.selectbox("Miză bazată pe:", ["Suma în Bani (£)", "Număr de Acțiuni (Qty)"])
    if mod_calcul == "Suma în Bani (£)":
        suma_gbp = st.number_input("Suma disponibilă (£):", value=100.0, step=10.0)
        cantitate_manuala = None
    else:
        cantitate_manuala = st.number_input("Câte acțiuni vrei (Amount):", value=1.0, step=0.1, min_value=1.0)
        suma_gbp = None

    st.divider()
    multiplicator_sl = st.slider("Sensibilitate Stop Loss (ATR):", 0.5, 3.0, 1.5, 0.1)
    raport_rr = st.slider("Țintă Profit (Ratio):", 1.0, 5.0, 2.0, 0.1)

# --- 3. LOGICĂ ȘI CALCULE ---
if ticker:
    try:
        # Descărcăm datele (60 de zile pentru EMA 200)
        df = yf.download(ticker, period="60d", interval="15m", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            close_prices = df['Close']
            pret_acum = float(close_prices.iloc[-1])
            curs_gbp_usd = 1.28

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

            tr = pd.concat([df['High']-df['Low'], abs(df['High']-close_prices.shift()), abs(df['Low']-close_prices.shift())], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            
            dist_sl = atr * multiplicator_sl
            dist_tp = dist_sl * raport_rr
            
            sl_p = pret_acum - dist_sl if "CUMP" in directie else pret_acum + dist_sl
            tp_p = pret_acum + dist_tp if "CUMP" in directie else pret_acum - dist_tp

            # --- AFIȘARE UI ---
            st.title(f"📊 {ticker} la ${pret_acum:.2f}")
            st.subheader(f"Probabilitate Succes: {probabilitate}%")
            st.progress(probabilitate / 100)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Cantitate (Amount)", f"{cantitate}")
            with c2:
                st.metric("Marjă Necesară", f"£{marja_gbp:.2f}")
            with c3:
                profit_net_gbp = ((abs(tp_p - pret_acum) * cantitate) / curs_gbp_usd)
                st.metric("Profit Estimat", f"£{profit_net_gbp:.2f}")

            # --- GRAFIC INTERACTIV ---
            fig = go.Figure(data=[go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Preț"
            )])
            
            # Adăugăm EMA 200 pe grafic
            fig.add_trace(go.Scatter(x=df.index, y=ema200_series, line=dict(color='orange', width=1), name="EMA 200"))
            
            # Liniile de TP și SL
            fig.add_hline(y=tp_p, line_dash="dash", line_color="green", annotation_text="Profit (Target)")
            fig.add_hline(y=sl_p, line_dash="dash", line_color="red", annotation_text="Stop Loss")
            
            fig.update_layout(height=450, margin=dict(l=0, r=0, t=0, b=0), template="plotly_white", 
                              xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- BOXA CITY INDEX ---
            box_c = "#dcfce7" if "CUMP" in directie else "#fee2e2"
            txt_c = "#16a34a" if "CUMP" in directie else "#dc2626"
            tp_f, sl_f = f"{tp_p:.2f}", f"{sl_p:.2f}"
            
            st.markdown(f"""
                <div style="background-color: {box_c}; padding: 25px; border-radius: 15px; border: 3px solid {txt_c}; text-align: center; margin-top: 20px;">
                    <h2 style="color: #000; margin: 0;">📱 City Index: {"BUY (Long)" if "CUMP" in directie else "SELL (Short)"}</h2>
                    <p style="font-size: 24px; color: #000; margin: 15px 0;">
                        <b>Amount:</b> {cantitate} | <b>TP:</b> ${tp_f} | <b>SL:</b> ${sl_f}
                    </p>
                    <p style="color: #333; font-size: 14px;">(Verifică simbolul <b>{ticker}</b> înainte de a plasa trade-ul)</p>
                </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Eroare tehnică: {e}")
else:
    st.info("Introdu un simbol în stânga pentru a începe analiza.")
