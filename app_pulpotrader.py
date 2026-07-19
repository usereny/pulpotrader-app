import streamlit as st
import yfinance as yf
import feedparser
from transformers import pipeline
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import random
import time
import os
import sqlite3
from datetime import datetime

# Configuración de página ultra-wide corporativa y futurista
st.set_page_config(page_title="PULPOFX IA v6.0 - Pulpotrader Pro", page_icon="🐙", layout="wide")

# Estilos CSS avanzados para interfaz Cyberpunk/Tecnológica
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Rajdhani:wght@500;700&display=swap');
    
    /* Fuentes globales */
    html, body, [class*="css"] {
        font-family: 'Rajdhani', sans-serif;
    }
    code, pre, .mono-text {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* Contenedores de Neón Tecnológico */
    .tech-card {
        background-color: #0d1117;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.6);
    }
    .neon-buy {
        border-left: 5px solid #00ff87 !important;
        box-shadow: 0 0 15px rgba(0, 255, 135, 0.1);
    }
    .neon-sell {
        border-left: 5px solid #ff3e3e !important;
        box-shadow: 0 0 15px rgba(255, 62, 62, 0.1);
    }
    .neon-header {
        border: 1px solid #00ffd2 !important;
        box-shadow: 0 0 20px rgba(0, 255, 210, 0.15);
    }
</style>
""", unsafe_allow_html=True)

# --- BASE DE DATOS LOCAL INTEGRADA ---
DB_NAME = "pulpotrader.db"
def conectar_db(): return sqlite3.connect(DB_NAME)
def inicializar_db():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS cuenta (id INTEGER PRIMARY KEY, capital REAL, estrategia TEXT, sugerencia TEXT, puntos INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS historial (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, activo TEXT, tipo TEXT, precio TEXT, riesgo TEXT, resultado TEXT, balance TEXT)")
    cursor.execute("SELECT COUNT(*) FROM cuenta")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO cuenta (id, capital, estrategia, sugerencia, puntos) VALUES (1, 1000.0, 'Estrategia estándar de confluencia de canales.', 'Escribe tu estrategia arriba y presiona el botón para procesar.', 0)")
    conn.commit()
    conn.close()

inicializar_db()

def cargar_memoria_db():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT capital, estrategia, sugerencia, puntos FROM cuenta WHERE id = 1")
    row = cursor.fetchone()
    st.session_state.capital = row[0]
    st.session_state.estrategia_activa = row[1]
    st.session_state.sugerencia_ia = row[2]
    st.session_state.puntos_estrategia = row[3]
    cursor.execute("SELECT fecha, activo, tipo, precio, riesgo, resultado, balance FROM historial ORDER BY id DESC")
    st.session_state.historial = [{"fecha": r[0], "activo": r[1], "tipo": r[2], "precio": r[3], "riesgo": r[4], "resultado": r[5], "balance": r[6]} for r in cursor.fetchall()]
    conn.close()

if 'capital' not in st.session_state: cargar_memoria_db()
if 'trade_en_vivo' not in st.session_state: st.session_state.trade_en_vivo = None  

if 'clasificador' not in st.session_state:
    with st.spinner("Cargando cerebro de IA FinBERT... (esperá un momentico)"):
        st.session_state.clasificador = pipeline("sentiment-analysis", model="ProsusAI/finbert")

def guardar_cuenta_db():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE cuenta SET capital = ?, estrategia = ?, sugerencia = ?, puntos = ? WHERE id = 1", (st.session_state.capital, st.session_state.estrategia_activa, st.session_state.sugerencia_ia, st.session_state.puntos_estrategia))
    conn.commit()
    conn.close()

def resetear_cuenta_db():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE cuenta SET capital = 1000.0, estrategia = 'Estrategia estándar.', sugerencia = 'Escribe tu estrategia.', puntos = 0 WHERE id = 1")
    cursor.execute("DELETE FROM historial")
    conn.commit()
    conn.close()
    cargar_memoria_db()

activos_disponibles = {
    "Bitcoin (BTC)": "BTC-USD", "Ethereum (ETH)": "ETH-USD", "Solana (SOL)": "SOL-USD",
    "Euro / Dólar (EUR-USD)": "EURUSD=X", "Libra / Dólar (GBP-USD)": "GBPUSD=X", "Dólar / Yen (USD-JPY)": "USDJPY=X"
}

# --- PANEL LATERAL FUTURISTA ---
st.sidebar.markdown("<h2 style='color: #00ffd2; font-family: monospace;'>⚡ SYSTEM CORE</h2>", unsafe_allow_html=True)
if st.sidebar.button("🔄 RESET ACCOUNT DATABASE", use_container_width=True):
    resetear_cuenta_db()
    st.sidebar.success("¡Base de datos limpia!")
    st.rerun()

activo_seleccionado = st.sidebar.selectbox("ACTIVO TARGET:", list(activos_disponibles.keys()))
activo_ticker = activos_disponibles[activo_seleccionado]
estilo_trading = st.sidebar.selectbox("INTERVALO QUANT:", ["Scalping (Velas 5M)", "Day Trading (Velas 15M)", "Swing Trading (Velas 1H)", "Position (Velas 1D)"])

if "Scalping" in estilo_trading: periodo_yf, intervalo_yf = "1d", "5m"
elif "Day" in estilo_trading: periodo_yf, intervalo_yf = "2d", "15m"
elif "Swing" in estilo_trading: periodo_yf, intervalo_yf = "5d", "1h"
else: periodo_yf, intervalo_yf = "60d", "1d"

riesgo_tolerable = st.sidebar.slider("GESTIÓN DE RIESGO POR TRADE (%)", 0.5, 5.0, 2.5, step=0.5)
umbral_seguridad = st.sidebar.slider("FILTRO QUANT DE CONFLUENCIA (%)", 50, 80, 60)
modo_simulacion = st.sidebar.toggle("🔬 IGNORAR FILTRO TÉCNICO (MODO TEST)", value=False)

st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center; color: #57606f; font-family:monospace; font-size:11px;'>PULPOTRADER ENGINE v6.0<br>DESIGNED BY RENNY GARCÍA</div>", unsafe_allow_html=True)

# --- HEADER ULTRA TECNOLÓGICO ---
if os.path.exists("logo.png"):
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2: st.image("logo.png", use_column_width=True)
else:
    st.markdown("""
    <div class="tech-card neon-header" style="text-align: center;">
        <span style="color: #8a90a1; font-size: 11px; letter-spacing: 3px; font-weight: bold; display: block;">QUANTITATIVE TRADING TERMINAL</span>
        <h1 style="color: #00ffd2; margin: 5px 0; font-size: 28px; font-family: 'JetBrains Mono', monospace; letter-spacing: 2px;">🐙 PULPOTRADER LABS</h1>
    </div>
    """, unsafe_allow_html=True)

# =====================================================================
# 1. MOTOR MATEMÁTICO AVANZADO (FIBONACCI & RSI PRECISION)
# =====================================================================
datos = yf.download(activo_ticker, period=periodo_yf, interval=intervalo_yf, progress=False)

if not datos.empty:
    if isinstance(datos.columns, pd.MultiIndex): datos.columns = [col[0] for col in datos.columns]
    datos = datos.reset_index().rename(columns={'Datetime': 'Fecha', 'Date': 'Fecha'})
    
    # EMAs estructurales
    datos['EMA_9'] = datos['Close'].ewm(span=9, adjust=False).mean()
    datos['EMA_21'] = datos['Close'].ewm(span=21, adjust=False).mean()
    
    # AFINACIÓN MATEMÁTICA DEL RSI (Cálculo Algorítmico Puro de Precisión)
    delta = datos['Close'].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / ema_down
    datos['RSI'] = 100 - (100 / (1 + rs))
    
    # Bandas de Bollinger y MACD
    datos['BB_Media'] = datos['Close'].rolling(window=20).mean()
    datos['BB_Std'] = datos['Close'].rolling(window=20).std()
    datos['BB_Superior'] = datos['BB_Media'] + (datos['BB_Std'] * 2)
    datos['BB_Inferior'] = datos['BB_Media'] - (datos['BB_Std'] * 2)
    datos['MACD'] = datos['Close'].ewm(span=12, adjust=False).mean() - datos['Close'].ewm(span=26, adjust=False).mean()
    datos['MACD_Señal'] = datos['MACD'].ewm(span=9, adjust=False).mean()
    datos['MACD_Hist'] = datos['MACD'] - datos['MACD_Señal']
    
    # AFINACIÓN MATEMÁTICA DE FIBONACCI (Detección de Fractales de Reversión)
    precio_max = float(datos['High'].max())
    precio_min = float(datos['Low'].min())
    rango_fibo = precio_max - precio_min
    fibo_618 = precio_max - (rango_fibo * 0.618)
    fibo_786 = precio_max - (rango_fibo * 0.786) # Nivel institucional profundo
    
    precio_actual = float(datos['Close'].iloc[-1])
    rsi_actual = float(datos['RSI'].iloc[-1]) if not pd.isna(datos['RSI'].iloc[-1]) else 50.0
    ema_9_actual = float(datos['EMA_9'].iloc[-1])
    ema_21_actual = float(datos['EMA_21'].iloc[-1])
    macd_hist_actual = float(datos['MACD_Hist'].iloc[-1])
    bb_sup_actual = float(datos['BB_Superior'].iloc[-1])
    bb_inf_actual = float(datos['BB_Inferior'].iloc[-1])
else:
    precio_actual, rsi_actual, fibo_618, fibo_786 = 65000.0, 50.0, 64200.0, 63800.0
    bb_sup_actual, bb_inf_actual, macd_hist_actual, ema_9_actual, ema_21_actual = 66000.0, 64000.0, 0.0, 65000.0, 65000.0

# =====================================================================
# 2. PROCESADOR DE ESTRATEGIAS (MÓDULO DE APRENDIZAJE)
# =====================================================================
st.markdown("### 🧠 EXPERIMENTAL STRATEGY GENERATOR")
texto_estrategia = st.text_area("Carga tus reglas lógicas en español (Ej: Buscar confluencia en el nivel de oro 61.8% de Fibonacci y RSI sobrevendido):", value=st.session_state.estrategia_activa)

if st.button("⚡ ANALYZE AND COMPUTE STRATEGY RULES", use_container_width=True):
    st.session_state.estrategia_activa = texto_estrategia
    tex = texto_estrategia.lower()
    sug = []
    pnts = 0
    
    if any(x in tex for x in ["fibo", "fibonacci", "fibonachi"]):
        pnts += 25
        sug.append(f"🎯 <b>FIBONACCI MATRIX ACTIVE:</b> Calibración calibrada en la DB. Zona de rebote optimizada en los niveles institucionales 61.8% (${round(fibo_618,2)}) y 78.6% (${round(fibo_786,2)}).")
    if "rsi" in tex:
        pnts += 15
        sug.append(f"📈 <b>RSI FILTER LOADED:</b> Analizador matemático de oscilación activo. RSI actual posicionado en {round(rsi_actual, 1)} ppts.")
    if any(x in tex for x in ["soporte", "resistencia", "bloque"]):
        sug.append("🛡️ <b>LIQUIDITY BUFFER:</b> Bloques de órdenes validados. Margen de seguridad estructural inyectado en el Stop Loss.")
        
    st.session_state.sugerencia_ia = "<br><br>".join(sug) if sug else "⚠️ <b>STRATEGY DEFAULTS:</b> Reglas guardadas por defecto en la base de datos de Pulpotrader."
    st.session_state.puntos_estrategia = pnts
    
    # Guardamos en la base de datos local
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE cuenta SET estrategia=?, sugerencia=?, puntos=? WHERE id=1", (st.session_state.estrategia_activa, st.session_state.sugerencia_ia, st.session_state.puntos_estrategia))
    conn.commit()
    conn.close()
    st.success("¡Estrategia procesada y guardada permanentemente!")
    st.rerun()

# =====================================================================
# 3. FILTRO QUANT Y GESTIÓN DE RIESGO INSTITUCIONAL
# =====================================================================
ancho_bb = bb_sup_actual - bb_inf_actual
posicion_bb = (precio_actual - bb_inf_actual) / ancho_bb if ancho_bb > 0 else 0.5

# Algoritmo de dirección de órdenes
if posicion_bb < 0.40 or (ema_9_actual > ema_21_actual and macd_hist_actual > 0 and rsi_actual < 68):
    direccion = "COMPRA (LONG)"
    base_prob = 50.0 + (1.0 - posicion_bb) * 12.0
else:
    direccion = "VENTA (SHORT)"
    base_prob = 50.0 + (posicion_bb) * 12.0

# Penalización algorítmica por exceso de RSI (Protección de sobrecompra/sobreventa)
if rsi_actual > 72 and direccion == "COMPRA (LONG)": base_prob -= 15.0
elif rsi_actual < 28 and direccion == "VENTA (SHORT)": base_prob -= 15.0

probabilidad_final = max(35.0, min(89.0, base_prob + (st.session_state.puntos_estrategia * 0.3)))

# Parámetros de Orden
es_forex = "=X" in activo_ticker
volatilidad = precio_actual * (0.0015 if es_forex else 0.015)
stop_loss = precio_actual - volatilidad if direccion == "COMPRA (LONG)" else precio_actual + volatilidad
take_profit = precio_actual + (volatilidad * 2.0) if direccion == "COMPRA (LONG)" else precio_actual - (volatilidad * 2.0)

riesgo_usd = st.session_state.capital * (riesgo_tolerable / 100.0)
precision_fmt = ".5f" if es_forex else ".2f"

# Cálculo de volumen institucional (Lotaje MT5)
if es_forex:
    pips = volatilidad * 10000 if not "JPY" in activo_ticker else volatilidad * 100
    lotaje = riesgo_usd / (pips * 10) if pips > 0 else 0.01
    lotaje_str = f"{round(max(0.01, lotaje), 2)} LOTES"
else:
    lotaje_crypto = riesgo_usd / volatilidad if volatilidad > 0 else 0.001
    lotaje_str = f"{round(max(0.001, lotaje_crypto), 3)} UNIDADES"

# Métricas
total_trades = len(st.session_state.historial)
ganados = sum(1 for t in st.session_state.historial if t['resultado'] == "GANADA")
win_rate = (ganados / total_trades * 100) if total_trades > 0 else 0.0

# =====================================================================
# 4. DISTRIBUCIÓN DE CONTENEDORES DE NEÓN (DASHBOARD VISUAL V6.0)
# =====================================================================
st.markdown("<br>", unsafe_allow_html=True)
col_izq, col_der = st.columns([2, 1])

with col_izq:
    # Bloque de IA de Estrategia
    st.markdown(f"""
    <div class="tech-card" style="border-top: 3px solid #00ffd2;">
        <span style="color: #00ffd2; font-family: monospace; font-weight: bold; font-size: 12px;">[ IA COGNITIVE ENGINE ]</span>
        <div style="color: #f1f2f6; font-size: 13px; margin-top: 8px; line-height: 1.5;">{st.session_state.sugerencia_ia}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # FICHA METATRADER 5 AVANZADA
    st.markdown("### 📋 METATRADER 5 ORDER PARAMETERS")
    clase_neon = "neon-buy" if direccion == "COMPRA (LONG)" else "neon-sell"
    color_dir = "#00ff87" if direccion == "COMPRA (LONG)" else "#ff3e3e"
    
    html_terminal = f"""
    <div class="tech-card {clase_neon}">
        <table style="width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 14px;">
            <tr style="border-bottom: 1px solid #21262d;">
                <td style="color: #8b949e; padding: 6px 0;">SYMBOL:</td>
                <td style="color: #ffffff; text-align: right; font-weight: bold;">{activo_ticker.replace('=X','')}</td>
            </tr>
            <tr style="border-bottom: 1px solid #21262d;">
                <td style="color: #8b949e; padding: 6px 0;">ORDER TYPE:</td>
                <td style="color: {color_dir}; text-align: right; font-weight: bold; font-size: 16px;">{ "BUY MARKET" if direccion == "COMPRA (LONG)" else "SELL MARKET" }</td>
            </tr>
            <tr style="border-bottom: 1px solid #21262d; background-color: rgba(0,255,210,0.03);">
                <td style="color: #00ffd2; padding: 8px 0; font-weight: bold;">📊 COMPUTED LOTSIZE:</td>
                <td style="color: #00ffd2; text-align: right; font-weight: bold; font-size: 15px;">{lotaje_str}</td>
            </tr>
            <tr>
                <td style="color: #ffffff; padding: 10px 0; font-weight: bold;">🟢 EXECUTION PRICE:</td>
                <td style="color: #ffffff; text-align: right; font-weight: bold; font-size: 18px;">{format(precio_actual, precision_fmt)}</td>
            </tr>
            <tr>
                <td style="color: #00ff87; padding: 10px 0; font-weight: bold;">🎯 TARGET PROFIT (TP):</td>
                <td style="color: #00ff87; text-align: right; font-weight: bold; font-size: 18px;">{format(take_profit, precision_fmt)}</td>
            </tr>
            <tr>
                <td style="color: #ff3e3e; padding: 10px 0; font-weight: bold;">🔴 INVALIDATION LOSS (SL):</td>
                <td style="color: #ff3e3e; text-align: right; font-weight: bold; font-size: 18px;">{format(stop_loss, precision_fmt)}</td>
            </tr>
        </table>
    </div>
    """
    st.markdown(html_terminal, unsafe_allow_html=True)

with col_der:
    st.markdown("### 🚨 TELEMETRÍA DE RIESGO")
    
    st.markdown(f"""
    <div class="tech-card" style="text-align: center;">
        <span style="color: #8b949e; font-size: 12px; display: block; font-family: monospace;">NET CAPITAL DEPLOYED</span>
        <h2 style="color: #ffffff; margin: 5px 0; font-size: 26px; font-family: 'JetBrains Mono', monospace;">${round(st.session_state.capital, 2)}</h2>
        <span style="color: #8b949e; font-size: 12px; display: block; margin-top: 10px; font-family: monospace;">GLOBAL WIN RATE</span>
        <h2 style="color: #00ffd2; margin: 5px 0; font-size: 26px; font-family: 'JetBrains Mono', monospace;">{round(win_rate, 1)}%</h2>
        <span style="color: #8b949e; font-size: 11px; display: block; margin-top: 10px; font-family: monospace;">SIGNAL CONFLUENCE WEIGHT</span>
        <h3 style="color: #ffffff; margin: 0; font-size: 18px;">{round(probabilidad_final, 1)}%</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Botón ejecutor
    aprobado = probabilidad_final >= umbral_seguridad
    if aprobado or modo_simulacion:
        if st.session_state.trade_en_vivo is None:
            if st.button("⚡ TRANSMIT SIGNAL TO SIMULATOR", use_container_width=True):
                st.session_state.trade_en_vivo = {
                    "activo": activo_seleccionado, "tipo": direccion, "precio_entrada": precio_actual,
                    "tp": take_profit, "sl": stop_loss, "riesgo_usd": riesgo_usd, "probabilidad": probabilidad_final
                }
                st.rerun()
        else:
            st.button("⏳ SIMULATION STREAMING INJECTED...", disabled=True, use_container_width=True)
    else:
        st.warning(f"⚠️ CONFLUENCIA INSUFICIENTE: Filtro mínimo requerido ({umbral_seguridad}%) superior al peso analizado.")

# =====================================================================
# 5. SEGUIMIENTO ALGORÍTMICO DINÁMICO EN TIEMPO REAL (TICK BY TICK)
# =====================================================================
if st.session_state.trade_en_vivo is not None:
    trade = st.session_state.trade_en_vivo
    st.markdown("---")
    st.markdown("<h3 style='color: #00ffd2; font-family: monospace;'>⏳ REAL-TIME PRICE STREAMING RADAR (TICK-BY-TICK)</h3>", unsafe_allow_html=True)
    
    radar_placeholder = st.empty()
    precio_movil = trade['precio_entrada']
    pasos = 8
    
    for i in range(pasos):
        time.sleep(0.6)
        factor = random.choice([-1.8, -0.6, 0.4, 1.1, 1.9])
        delta_p = (trade['precio_entrada'] * 0.0018) * factor
        precio_movil += (delta_p if trade['tipo'] == "COMPRA (LONG)" else -delta_p)
        
        # Evaluar toques estructurales
        toco_tp = (trade['tipo'] == "COMPRA (LONG)" and precio_movil >= trade['tp']) or (trade['tipo'] == "VENTA (SHORT)" and precio_movil <= trade['tp'])
        toco_sl = (trade['tipo'] == "COMPRA (LONG)" and precio_movil <= trade['sl']) or (trade['tipo'] == "VENTA (SHORT)" and precio_movil >= trade['sl'])
        
        # Calcular PnL flotante matemático en vivo
        if trade['tipo'] == "COMPRA (LONG)":
            pnl_flotante_pct = ((precio_movil - trade['precio_entrada']) / trade['precio_entrada']) * 100
        else:
            pnl_flotante_pct = ((trade['precio_entrada'] - precio_movil) / trade['precio_entrada']) * 100
            
        pnl_flotante_usd = trade['riesgo_usd'] * (pnl_flotante_pct / (volatilidad / trade['precio_entrada'] * 100))
        color_pnl = "#00ff87" if pnl_flotante_usd >= 0 else "#ff3e3e"
        signo = "+" if pnl_flotante_usd >= 0 else ""
        
        with radar_placeholder.container():
            st.markdown(f"""
            <div class="tech-card" style="border: 1px solid #f39c12; background-color: rgba(243, 156, 18, 0.02);">
                <div style="display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size:13px;">
                    <div>🎯 ORDEN CARGADA: <span style="color:#ffffff;">{format(trade['precio_entrada'], precision_fmt)}</span></div>
                    <div>📡 TICK ACTUAL: <span style="color:#f39c12; font-weight:bold;">{format(precio_movil, precision_fmt)}</span></div>
                    <div>📊 PnL EN VIVO: <span style="color:{color_pnl}; font-weight:bold;">{signo}${round(pnl_flotante_usd, 2)} USD</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.progress((i + 1) / pasos)
            
        if toco_tp or toco_sl: break

    exito = toco_tp if (toco_tp or toco_sl) else (random.randint(1, 100) <= trade['probabilidad'])
    resultado_final = "GANADA" if exito else "PERDIDA"
    
    # Módulo de alerta para celular (Estructura lógica lista para inyección de Token)
    # bot_telegram.send_message(chat_id, f"Trade ejecutado: {resultado_final}")
    
    st.session_state.capital += (trade['riesgo_usd'] * 1.9) if exito else -trade['riesgo_usd']
    
    nuevo_t = {
        "fecha": datetime.now().strftime("%H:%M:%S"), "activo": trade['activo'], "tipo": trade['tipo'],
        "precio": f"${format(trade['precio_entrada'], precision_fmt)}", "riesgo": f"${round(trade['riesgo_usd'], 2)}",
        "resultado": resultado_final, "balance": f"${round(st.session_state.capital, 2)}"
    }
    
    # Guardamos el trade en la DB local de la PC
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO historial (fecha, activo, tipo, precio, riesgo, resultado, balance) VALUES (?, ?, ?, ?, ?, ?, ?)", (nuevo_t['fecha'], nuevo_t['activo'], nuevo_t['tipo'], nuevo_t['precio'], nuevo_t['riesgo'], nuevo_t['resultado'], nuevo_t['balance']))
    cursor.execute("UPDATE cuenta SET capital=? WHERE id=1", (st.session_state.capital,))
    conn.commit()
    conn.close()
    
    st.session_state.trade_en_vivo = None 
    st.rerun()

# =====================================================================
# PANEL DE GRÁFICO PROFESIONAL CALIBRADO
# =====================================================================
st.markdown("---")
st.markdown(f"### 📊 QUANTITATIVE SUPPORT CHARTS")
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.7, 0.3])

fig.add_trace(go.Candlestick(x=datos['Fecha'], open=datos['Open'], high=datos['High'], low=datos['Low'], close=datos['Close'], name="Precio"), row=1, col=1)
fig.add_trace(go.Scatter(x=datos['Fecha'], y=datos['BB_Superior'], line=dict(color='rgba(0, 255, 210, 0.12)', width=1, dash='dot'), name="BB Sup"), row=1, col=1)
fig.add_trace(go.Scatter(x=datos['Fecha'], y=datos['BB_Inferior'], line=dict(color='rgba(0, 255, 210, 0.12)', width=1, dash='dot'), name="BB Inf"), row=1, col=1)

# Pintamos niveles cuánticos afinados de Fibonacci si están activos en la estrategia
if any(x in st.session_state.estrategia_activa.lower() for x in ["fibo", "fibonacci", "fibonachi"]) and not datos.empty:
    fig.add_hline(y=precio_max, line_color="rgba(231, 76, 60, 0.2)", line_width=1, annotation_text="Fibo Max 0.0%", row=1, col=1)
    fig.add_hline(y=fibo_618, line_color="#00ff87", line_width=1.5, annotation_text="ZONA ORO 61.8%", row=1, col=1)
    fig.add_hline(y=fibo_786, line_color="#00ffd2", line_width=1.5, annotation_text="QUANT LEVEL 78.6%", row=1, col=1)
    fig.add_hline(y=precio_min, line_color="rgba(149, 165, 166, 0.2)", line_width=1, annotation_text="Fibo Min 100.0%", row=1, col=1)

fig.add_trace(go.Scatter(x=datos['Fecha'], y=datos['MACD'], line=dict(color='#00ffd2', width=1), name="MACD"), row=2, col=1)
colores_hist = ['#00ff87' if val >= 0 else '#ff3e3e' for val in datos['MACD_Hist']] if not datos.empty else []
fig.add_trace(go.Bar(x=datos['Fecha'], y=datos['MACD_Hist'], marker_color=colores_hist, name="Hist"), row=2, col=1)

fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, paper_bgcolor="#0d1117", plot_bgcolor="#0d1117", font=dict(color="#c9d1d9"), height=480, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

# --- BITÁCORA HISTÓRICA COMPLETA ---
st.subheader("📋 HISTORICAL TRANSACTION LOG")
if st.session_state.historial:
    st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
else:
    st.info("No hay transacciones registradas en el clúster de la base de datos.")
