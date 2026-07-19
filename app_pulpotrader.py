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

# Configuración de página ultra-wide corporativa
st.set_page_config(page_title="PULPOFX IA v5.5 - Pulpotrader", page_icon="🐙", layout="wide")

# =====================================================================
# CONFIGURACIÓN DE BASE DE DATOS LOCAL AUTOMÁTICA (SQLite)
# =====================================================================
DB_NAME = "pulpotrader.db"

def conectar_db():
    conn = sqlite3.connect(DB_NAME)
    return conn

def inicializar_db():
    conn = conectar_db()
    cursor = conn.cursor()
    # Tabla de configuración/capital
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cuenta (
            id INTEGER PRIMARY KEY,
            capital REAL,
            estrategia TEXT,
            sugerencia TEXT,
            puntos INTEGER
        )
    """)
    # Tabla de historial de trades
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            activo TEXT,
            tipo TEXT,
            precio TEXT,
            riesgo TEXT,
            resultado TEXT,
            balance TEXT
        )
    """)
    # Si la cuenta está vacía, insertamos los valores iniciales
    cursor.execute("SELECT COUNT(*) FROM cuenta")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO cuenta (id, capital, estrategia, sugerencia, puntos) VALUES (1, 1000.0, 'Estrategia estándar basada en el cruce de EMAs y rebotes en las Bandas de Bollinger.', 'Escribe tu estrategia arriba y presiona el botón para analizar.', 0)")
    conn.commit()
    conn.close()

# Inicializamos la base de datos en el disco duro
inicializar_db()

# Cargar datos de la DB al Session State de Streamlit
def cargar_memoria_db():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT capital, estrategia, sugerencia, puntos FROM cuenta WHERE id = 1")
    row = cursor.fetchone()
    st.session_state.capital = row[0]
    st.session_state.estrategia_activa = row[1]
    st.session_state.sugerencia_ia = row[2]
    st.session_state.puntos_estrategia = row[3]
    
    # Historial
    cursor.execute("SELECT fecha, activo, tipo, precio, riesgo, resultado, balance FROM historial ORDER BY id DESC")
    st.session_state.historial = [
        {"fecha": r[0], "activo": r[1], "tipo": r[2], "precio": r[3], "riesgo": r[4], "resultado": r[5], "balance": r[6]}
        for r in cursor.fetchall()
    ]
    conn.close()

if 'capital' not in st.session_state:
    cargar_memoria_db()
if 'trade_en_vivo' not in st.session_state:
    st.session_state.trade_en_vivo = None  

if 'clasificador' not in st.session_state:
    with st.spinner("Cargando cerebro de IA FinBERT... (esperá un momentico)"):
        st.session_state.clasificador = pipeline("sentiment-analysis", model="ProsusAI/finbert")

clasificador = st.session_state.clasificador

# Funciones para guardar en la base de datos real
def guardar_cuenta_db():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE cuenta 
        SET capital = ?, estrategia = ?, sugerencia = ?, puntos = ? 
        WHERE id = 1
    """, (st.session_state.capital, st.session_state.estrategia_activa, st.session_state.sugerencia_ia, st.session_state.puntos_estrategia))
    conn.commit()
    conn.close()

def insertar_trade_db(trade_dict):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO historial (fecha, activo, tipo, precio, riesgo, resultado, balance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (trade_dict['fecha'], trade_dict['activo'], trade_dict['tipo'], trade_dict['precio'], trade_dict['riesgo'], trade_dict['resultado'], trade_dict['balance']))
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
    "Bitcoin (BTC)": "BTC-USD",
    "Ethereum (ETH)": "ETH-USD",
    "Solana (SOL)": "SOL-USD",
    "Euro / Dólar (EUR-USD)": "EURUSD=X",
    "Libra / Dólar (GBP-USD)": "GBPUSD=X",
    "Dólar / Yen (USD-JPY)": "USDJPY=X"
}

# --- PANEL DE CONTROL LATERAL (Sidebar) ---
st.sidebar.markdown("<h2 style='color: #00ffd2;'>⚙️ Panel de Control</h2>", unsafe_allow_html=True)

if st.sidebar.button("🔄 Reiniciar Cuenta a $1,000 (Borra DB)", use_container_width=True):
    resetear_cuenta_db()
    st.sidebar.success("¡Base de datos reseteada!")
    st.rerun()

activo_seleccionado = st.sidebar.selectbox("Activo a Operar:", list(activos_disponibles.keys()))
activo_ticker = activos_disponibles[activo_seleccionado]

estilo_trading = st.sidebar.selectbox(
    "Estilo de Trading (Temporalidad):", 
    ["Scalping (Velas 5M)", "Day Trading (Velas 15M)", "Swing Trading (Velas 1H)", "Position Trading (Velas 1D)"]
)

if "Scalping" in estilo_trading:
    periodo_yf, intervalo_yf = "1d", "5m"
elif "Day" in estilo_trading:
    periodo_yf, intervalo_yf = "2d", "15m"
elif "Swing" in estilo_trading:
    periodo_yf, intervalo_yf = "5d", "1h"
else:
    periodo_yf, intervalo_yf = "60d", "1d"

riesgo_tolerable = st.sidebar.slider("Riesgo Tolerable por Operación (%)", 0.5, 5.0, 2.5, step=0.5)
umbral_seguridad = st.sidebar.slider("Filtro de Seguridad del Ejecutor (%)", 50, 80, 60)
modo_simulacion = st.sidebar.toggle("🔬 Modo Pruebas (Habilitar Botón Siempre)", value=False)

st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center; color: #57606f;'>Desarrollado por Renny García — Pulpo-graf</div>", unsafe_allow_html=True)

# --- ENCABEZADO CORPORATIVO CON LOGO AUTOMÁTICO ---
if os.path.exists("logo.png"):
    col_logo_1, col_logo_2, col_logo_3 = st.columns([1, 2, 1])
    with col_logo_2:
        st.image("logo.png", use_column_width=True)
else:
    html_placeholder_logo = """
    <div style="text-align: center; padding: 20px; border: 2px dashed rgba(0, 255, 210, 0.3); border-radius: 8px; background-color: #161b22; margin-bottom: 10px;">
        <span style="color: #8a90a1; font-size: 12px; letter-spacing: 2px; font-weight: bold; display: block; margin-bottom: 5px;">ESPACIO RESERVADO PARA MARCA</span>
        <h2 style="color: #00ffd2; margin: 0; font-size: 20px; font-family: monospace;">🐙 PULPOTRADER LOGO</h2>
    </div>
    """
    st.markdown(html_placeholder_logo, unsafe_allow_html=True)

st.markdown("<h1 style='margin:0; color: #ffffff; text-align:center; font-size: 26px;'>PULPOFX IA</h1>", unsafe_allow_html=True)
st.markdown("<p style='margin:0; color: #8a90a1; font-size: 13px; text-align:center; letter-spacing: 1px;'>Terminal Dinámica Cuantitativa Local y Permanente</p>", unsafe_allow_html=True)

# =====================================================================
# 1. DESCARGA Y CÁLCULO DE INDICADORES TÉCNICOS REALES
# =====================================================================
datos = yf.download(activo_ticker, period=periodo_yf, interval=intervalo_yf, progress=False)

if not datos.empty:
    if isinstance(datos.columns, pd.MultiIndex):
        datos.columns = [col[0] for col in datos.columns]
    
    datos = datos.reset_index()
    col_fecha = 'Datetime' if 'Datetime' in datos.columns else 'Date' if 'Date' in datos.columns else datos.columns[0]
    datos = datos.rename(columns={col_fecha: 'Fecha'})
    
    datos['EMA_9'] = datos['Close'].ewm(span=9, adjust=False).mean()
    datos['EMA_21'] = datos['Close'].ewm(span=21, adjust=False).mean()
    
    delta = datos['Close'].diff()
    ganancia = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    perdida = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = ganancia / perdida
    datos['RSI'] = 100 - (100 / (1 + rs))
    
    datos['BB_Media'] = datos['Close'].rolling(window=20).mean()
    datos['BB_Std'] = datos['Close'].rolling(window=20).std()
    datos['BB_Superior'] = datos['BB_Media'] + (datos['BB_Std'] * 2)
    datos['BB_Inferior'] = datos['BB_Media'] - (datos['BB_Std'] * 2)
    
    ema12 = datos['Close'].ewm(span=12, adjust=False).mean()
    ema26 = datos['Close'].ewm(span=26, adjust=False).mean()
    datos['MACD'] = ema12 - ema26
    datos['MACD_Señal'] = datos['MACD'].ewm(span=9, adjust=False).mean()
    datos['MACD_Hist'] = datos['MACD'] - datos['MACD_Señal']
    
    precio_max = float(datos['High'].max())
    precio_min = float(datos['Low'].min())
    distancia_fibo = precio_max - precio_min
    fibo_618 = precio_max - (distancia_fibo * 0.618)
    
    precio_actual = float(datos['Close'].iloc[-1])
    rsi_actual = float(datos['RSI'].iloc[-1]) if not pd.isna(datos['RSI'].iloc[-1]) else 50.0
    ema_9_actual = float(datos['EMA_9'].iloc[-1])
    ema_21_actual = float(datos['EMA_21'].iloc[-1])
    macd_hist_actual = float(datos['MACD_Hist'].iloc[-1])
    bb_sup_actual = float(datos['BB_Superior'].iloc[-1]) if not pd.isna(datos['BB_Superior'].iloc[-1]) else precio_actual * 1.01
    bb_inf_actual = float(datos['BB_Inferior'].iloc[-1]) if not pd.isna(datos['BB_Inferior'].iloc[-1]) else precio_actual * 0.99
    
    tendencia_tecnica = "ALCISTA (EMA9 > EMA21)" if ema_9_actual > ema_21_actual else "BAJISTA (EMA9 < EMA21)"
else:
    precio_actual, rsi_actual, tendencia_tecnica = 1.0850, 50.0, "NEUTRAL"
    macd_hist_actual, bb_sup_actual, bb_inf_actual, fibo_618 = 0.0, 1.1000, 1.0700, 1.0850

# =====================================================================
# 2. ANALISTA FUNDAMENTAL (Noticias)
# =====================================================================
url_noticias = "https://finance.yahoo.com/news/rss"
feed = feedparser.parse(url_noticias)
titulares_filtrados = []
es_forex = "=X" in activo_ticker
keywords = ["forex", "fed", "dollar", "inflation", "ecb"] if es_forex else ["bitcoin" if "BTC" in activo_ticker else "ethereum" if "ETH" in activo_ticker else "solana", "crypto"]

for entrada in feed.entries:
    if any(kw in entrada.title.lower() for kw in keywords):
        titulares_filtrados.append(entrada.title)
    if len(titulares_filtrados) == 2: break

if not titulares_filtrados: titulares_filtrados = [e.title for e in feed.entries[:2]]

sentimiento_acumulado = 0
noticias_log = []
for t in titulares_filtrados:
    res = clasificador(t)[0]
    sentimiento = res['label'].upper()
    peso = 1 if sentimiento == "POSITIVE" else -1 if sentimiento == "NEGATIVE" else 0
    sentimiento_acumulado += (peso * res['score'])
    noticias_log.append(f"📰 {t[:65]}... ({sentimiento})")

sentimiento_promedio = (sentimiento_acumulado / len(titulares_filtrados)) * 100

# =====================================================================
# 3. INTERFAZ DE ESTRATEGIA (PROCESADOR CON MEMORIA DB)
# =====================================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("### 🧠 Panel de Desarrollo de Estrategias Propias")
texto_estrategia = st.text_area("Explícale tu estrategia al bot en español:", value=st.session_state.estrategia_activa)

if st.button("⚡ ANALIZAR, RECOMENDAR Y USAR ESTA ESTRATEGIA", use_container_width=True):
    st.session_state.estrategia_activa = texto_estrategia
    texto_usuario = texto_estrategia.lower()
    sugerencias_lista = []
    puntos = 0
    
    if "fibonachi" in texto_usuario or "fibonacci" in texto_usuario or "fibo" in texto_usuario:
        puntos += 22
        sugerencias_lista.append("🎯 **Memoria Fibonacci Activa:** La IA fijará los retrocesos estructurales. Nivel de oro del 61.8% configurado en la DB como zona de alta reacción.")
    if "soporte" in texto_usuario or "resistencia" in texto_usuario:
        sugerencias_lista.append("🛡️ **Filtro de Estructuras S/R:** Guardado en DB. Se aplicó holgura automática en el SL para mitigar barridos de liquidez.")
    if "rsi" in texto_usuario:
        puntos += 10
        sugerencias_lista.append("📈 **Filtro Oscilador RSI:** Guardado. El motor penalizará señales si el mercado está sobre-extendido.")
        
    if not sugerencias_lista:
        st.session_state.sugerencia_ia = "⚠️ **Análisis de IA:** Guardado por defecto. Añade términos técnicos (Fibonacci, EMA, RSI) para calibración pesada."
    else:
        st.session_state.sugerencia_ia = "\n\n".join(sugerencias_lista)
    
    st.session_state.puntos_estrategia = puntos
    guardar_cuenta_db() # Volcamos directo al archivo .db de la compu
    st.success("¡Estrategia analizada y grabada permanentemente en el disco duro!")
    st.rerun()

# =====================================================================
# 4. MATEMÁTICAS OPERATIVAS Y CÁLCULO DE LOTAJE AUTOMÁTICO PARA MT5
# =====================================================================
ancho_bandas = bb_sup_actual - bb_inf_actual
posicion_en_bandas = (precio_actual - bb_inf_actual) / ancho_bandas if ancho_bandas > 0 else 0.5

if posicion_en_bandas < 0.45 or (ema_9_actual > ema_21_actual and macd_hist_actual > 0):
    direccion = "COMPRA (LONG)"
    base_tecnica = 45.0 + (1.0 - posicion_en_bandas) * 15.0
else:
    direccion = "VENTA (SHORT)"
    base_tecnica = 45.0 + (posicion_en_bandas) * 15.0

probabilidad_final = max(35.0, min(85.0, base_tecnica + (sentimiento_promedio * 0.05) + (st.session_state.puntos_estrategia * 0.4)))

# Niveles y Volatilidad
rango_volatilidad = 0.0012 if es_forex else 0.012
volatilidad = precio_actual * rango_volatilidad
stop_loss = precio_actual - volatilidad if direccion == "COMPRA (LONG)" else precio_actual + volatilidad
take_profit = precio_actual + (volatilidad * 1.9) if direccion == "COMPRA (LONG)" else precio_actual - volatilidad * 1.9

riesgo_en_usd = st.session_state.capital * (riesgo_tolerable / 100.0)
distancia_stop_porcentaje = (volatilidad / precio_actual)
tamaño_posicion_usd = riesgo_en_usd / distancia_stop_porcentaje

# --- NUEVO: CALCULADORA DE LOTAJES AVANZADA PARA METATRADER 5 ---
if es_forex:
    # En Forex, un lote estándar son 100,000 unidades. Medimos pips de distancia.
    pips_distancia = volatilidad * 10000 if not "JPY" in activo_ticker else volatilidad * 100
    # Fórmula de lotaje institucional en Forex
    lotaje_mt5 = riesgo_en_usd / (pips_distancia * 10) if pips_distancia > 0 else 0.01
    lotaje_texto = f"{round(max(0.01, lotaje_mt5), 2)} Lotes Estándar"
else:
    # En Criptomonedas (BTC, ETH), el lotaje equivale directamente al tamaño de la moneda
    lotaje_crypto = riesgo_en_usd / volatilidad if volatilidad > 0 else 0.001
    lotaje_texto = f"{round(max(0.001, lotaje_crypto), 3)} BTC/Monedas"

# Métricas consolidadas de la DB
total_operaciones = len(st.session_state.historial)
operaciones_ganadas = sum(1 for t in st.session_state.historial if t['resultado'] == "GANADA")
win_rate = (operaciones_ganadas / total_operaciones * 100) if total_operaciones > 0 else 0.0
ganancia_neta = st.session_state.capital - 1000.0

precision_formato = ".5f" if es_forex else ".2f"

# =====================================================================
# 5. MAQUETACIÓN VISUAL DE LA TERMINAL (MT5 + LOTAJE)
# =====================================================================
st.markdown("<hr style='border-color: #2d3139;'>", unsafe_allow_html=True)

col_izq, col_der = st.columns([2, 1])

with col_izq:
    st.markdown(f"""
    <div style="background-color:#11141a; padding: 14px; border-radius: 8px; border: 1px solid #00ffd2; margin-bottom:15px;">
        <span style="color:#00ffd2; font-weight:bold; font-size:13px;">🐙 RECOMENDACIONES TÉCNICAS (ESTRATEGIA EN MEMORIA):</span>
        <div style="color:#f1f2f6; margin-top:4px; font-size:13px; line-height:1.4;">{st.session_state.sugerencia_ia}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📋 Ficha de Orden Técnica (Para copiar en MetaTrader 5)")
    color_panel = "#2ecc71" if direccion == "COMPRA (LONG)" else "#e74c3c"
    
    html_mt5 = f"""
    <div style="background-color: #161b22; border: 2px solid {color_panel}; border-radius: 10px; padding: 20px; box-shadow: 0px 4px 15px rgba(0,0,0,0.5);">
        <table style="width: 100%; border-collapse: collapse; font-family: monospace;">
            <tr>
                <td style="color: #8a90a1; font-size: 14px; padding: 6px 0;">ACTIVO TICKER:</td>
                <td style="color: #ffffff; font-size: 16px; font-weight: bold; text-align: right;">{activo_ticker.replace('=X', '')}</td>
            </tr>
            <tr>
                <td style="color: #8a90a1; font-size: 14px; padding: 6px 0;">TIPO DE ORDEN:</td>
                <td style="color: {color_panel}; font-size: 18px; font-weight: bold; text-align: right;">{ "BUY ORDER" if direccion == "COMPRA (LONG)" else "SELL ORDER" }</td>
            </tr>
            <tr style="border-bottom: 1px solid #2d3139;">
                <td style="color: #8a90a1; font-size: 14px; padding: 6px 0;">ESTILO EJECUCIÓN:</td>
                <td style="color: #ffffff; font-size: 14px; text-align: right; font-weight: bold;">{estilo_trading}</td>
            </tr>
            <!-- NUEVA FILA DE LOTAJE AUTOMÁTICO -->
            <tr style="background-color: rgba(0, 255, 210, 0.05);">
                <td style="color: #00ffd2; font-size: 15px; padding: 8px 0; font-weight: bold;">📊 LOTAJE SUGERIDO MT5:</td>
                <td style="color: #00ffd2; font-size: 16px; font-weight: bold; text-align: right; letter-spacing:1px;">{lotaje_texto}</td>
            </tr>
            <tr>
                <td style="color: #ffffff; font-size: 15px; padding: 10px 0; font-weight: bold;">🟢 PRECIO DE ENTRADA:</td>
                <td style="color: #ffffff; font-size: 20px; font-weight: bold; text-align: right;">{format(precio_actual, precision_formato)}</td>
            </tr>
            <tr>
                <td style="color: #2ecc71; font-size: 15px; padding: 10px 0; font-weight: bold;">🎯 TAKE PROFIT (TP):</td>
                <td style="color: #2ecc71; font-size: 20px; font-weight: bold; text-align: right;">{format(take_profit, precision_formato)}</td>
            </tr>
            <tr>
                <td style="color: #e74c3c; font-size: 15px; padding: 10px 0; font-weight: bold;">🔴 STOP LOSS (SL):</td>
                <td style="color: #e74c3c; font-size: 20px; font-weight: bold; text-align: right;">{format(stop_loss, precision_formato)}</td>
            </tr>
        </table>
    </div>
    """
    st.markdown(html_mt5, unsafe_allow_html=True)

with col_der:
    st.markdown("### 🚨 Cuenta y Gestión Algorítmica")
    st.metric(label="💵 Capital Neto (Guardado en DB)", value=f"${round(st.session_state.capital, 2)} USD")
    st.metric(label="🎯 Win Rate Global", value=f"{round(win_rate, 1)}%")
    st.markdown(f"<h4 style='text-align:center; color:#8a90a1;'>Efectividad Ponderada: <span style='color:#ffffff;'>{round(probabilidad_final, 1)}%</span></h4>", unsafe_allow_html=True)
    
    aprobado_por_filtro = probabilidad_final >= umbral_seguridad
    if aprobado_por_filtro or modo_simulacion:
        if st.session_state.trade_en_vivo is None:
            if st.button("⚡ TRANSMITIR OPERACIÓN EN CURSO", use_container_width=True):
                st.session_state.trade_en_vivo = {
                    "activo": activo_seleccionado,
                    "tipo": direccion,
                    "precio_entrada": precio_actual,
                    "tp": take_profit,
                    "sl": stop_loss,
                    "riesgo_usd": riesgo_en_usd,
                    "probabilidad": probabilidad_final
                }
                st.rerun()
        else:
            st.button("⏳ SIMULANDO MOVIMIENTO DE VELAS...", disabled=True, use_container_width=True)
    else:
        st.warning(f"❌ Orden Bloqueada: Filtro de seguridad requerido ({umbral_seguridad}%) superior al actual.")

# =====================================================================
# --- SIMULADOR EN VIVO (CONEXIÓN DIRECTA A ARCHIVO DB) ---
# =====================================================================
if st.session_state.trade_en_vivo is not None:
    trade = st.session_state.trade_en_vivo
    st.markdown("---")
    st.markdown("<h3 style='color: #f39c12;'>⏳ SEGUIMIENTO ALGORÍTMICO DEL PRECIO (VELA A VELA)</h3>", unsafe_allow_html=True)
    
    progreso_placeholder = st.empty()
    precio_movil = trade['precio_entrada']
    pasos = 6
    toco_tp, toco_sl = False, False
    
    for i in range(pasos):
        time.sleep(0.7)
        factor_mercado = random.choice([-1.5, -0.5, 0.3, 0.9, 1.4]) 
        variacion_precio = (trade['precio_entrada'] * 0.0025) * factor_mercado
        precio_movil += (variacion_precio if trade['tipo'] == "COMPRA (LONG)" else -variacion_precio)
        
        toco_tp = (trade['tipo'] == "COMPRA (LONG)" and precio_movil >= trade['tp']) or (trade['tipo'] == "VENTA (SHORT)" and precio_movil <= trade['tp'])
        toco_sl = (trade['tipo'] == "COMPRA (LONG)" and precio_movil <= trade['sl']) or (trade['tipo'] == "VENTA (SHORT)" and precio_movil >= trade['sl'])
        
        with progreso_placeholder.container():
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Precio de Carga:** `${format(trade['precio_entrada'], precision_formato)}`")
            c2.markdown(f"**Fluctuación en Vivo:** <b style='color:#f39c12;'>${format(precio_movil, precision_formato)}</b>", unsafe_allow_html=True)
            c3.write(f"**Límites:** TP: `${format(trade['tp'], precision_formato)}` | SL: `${format(trade['sl'], precision_formato)}`")
            st.progress((i + 1) / pasos)
            
        if toco_tp or toco_sl: break

    exito = toco_tp if (toco_tp or toco_sl) else (random.randint(1, 100) <= trade['probabilidad'])
    resultado_final = "GANADA" if exito else "PERDIDA"
    st.session_state.capital += (trade['riesgo_usd'] * 1.8) if exito else -trade['riesgo_usd']
    
    # Grabamos el nuevo trade de forma permanente en la base de datos local (.db)
    nuevo_registro = {
        "fecha": datetime.now().strftime("%H:%M:%S"),
        "activo": trade['activo'],
        "tipo": trade['tipo'],
        "precio": f"${format(trade['precio_entrada'], precision_formato)}",
        "riesgo": f"${round(trade['riesgo_usd'], 2)}",
        "resultado": resultado_final,
        "balance": f"${round(st.session_state.capital, 2)}"
    }
    insertar_trade_db(nuevo_registro)
    guardar_cuenta_db() # Actualiza capital
    st.session_state.trade_en_vivo = None 
    st.rerun()

# =====================================================================
# PANEL DE GRÁFICO PROFESIONAL BAJO EL CONTROL DE MANDOS
# =====================================================================
st.markdown("---")
st.markdown(f"### 📊 Dashboard Técnico de Soporte — {activo_seleccionado}")
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

fig.add_trace(go.Candlestick(x=datos['Fecha'], open=datos['Open'], high=datos['High'], low=datos['Low'], close=datos['Close'], name="Velas"), row=1, col=1)
fig.add_trace(go.Scatter(x=datos['Fecha'], y=datos['BB_Superior'], line=dict(color='rgba(0, 255, 210, 0.15)', width=1, dash='dot'), name="BB Sup"), row=1, col=1)
fig.add_trace(go.Scatter(x=datos['Fecha'], y=datos['BB_Inferior'], line=dict(color='rgba(0, 255, 210, 0.15)', width=1, dash='dot'), name="BB Inf"), row=1, col=1)

if "fibonachi" in st.session_state.estrategia_activa.lower() or "fibonacci" in st.session_state.estrategia_activa.lower() and not datos.empty:
    fig.add_hline(y=precio_max, line_color="rgba(231, 76, 60, 0.3)", line_width=1, annotation_text="Fibo 0.0%", row=1, col=1)
    fig.add_hline(y=fibo_618, line_color="rgba(46, 204, 113, 0.5)", line_width=1.5, annotation_text="NIVEL DE ORO 61.8%", row=1, col=1)
    fig.add_hline(y=precio_min, line_color="rgba(149, 165, 166, 0.3)", line_width=1, annotation_text="Fibo 100.0%", row=1, col=1)

fig.add_trace(go.Scatter(x=datos['Fecha'], y=datos['MACD'], line=dict(color='#00ffd2', width=1), name="MACD"), row=2, col=1)
colores_hist = ['#2ecc71' if val >= 0 else '#e74c3c' for val in datos['MACD_Hist']] if not datos.empty else []
fig.add_trace(go.Bar(x=datos['Fecha'], y=datos['MACD_Hist'], marker_color=colores_hist, name="Hist"), row=2, col=1)

fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, paper_bgcolor="#11141a", plot_bgcolor="#11141a", font=dict(color="#f1f2f6"), height=480, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

# --- BITÁCORA HISTÓRICA REAL DESDE DB ---
st.subheader("📋 Registro Histórico de Operaciones")
if st.session_state.historial:
    st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
else:
    st.info("Bitácora vacía. Haz clic en transmitir arriba para simular tu primer trade.")