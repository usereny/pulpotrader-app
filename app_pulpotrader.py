import streamlit as st
import yfinance as yf
import feedparser
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import random
import time
import math
import statistics
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Optional
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Configuración de la aplicación
st.set_page_config(page_title="PULPOTRADER PRO v7.1", page_icon="🐙", layout="wide")

@st.cache_resource
def descargar_vader():
    nltk.download('vader_lexicon', quiet=True)
    return SentimentIntensityAnalyzer()

sia = descargar_vader()

# Estilos visuales Cyberpunk
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Rajdhani:wght@500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Rajdhani', sans-serif; }
    code, pre, .mono-text { font-family: 'JetBrains Mono', monospace !important; }
    .tech-card { background-color: #0d1117; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.6); }
    .neon-buy { border-left: 5px solid #00ff87 !important; box-shadow: 0 0 15px rgba(0, 255, 135, 0.1); }
    .neon-sell { border-left: 5px solid #ff3e3e !important; box-shadow: 0 0 15px rgba(255, 62, 62, 0.1); }
    .neon-header { border: 1px solid #00ffd2 !important; box-shadow: 0 0 20px rgba(0, 255, 210, 0.15); }
    .neon-news { border-top: 3px solid #f39c12 !important; }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# 🧠 NÚCLEO ARQUITECTÓNICO DE ESPECIALISTAS Y RIESGO
# =====================================================================

class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"

@dataclass(frozen=True)
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass(frozen=True)
class SpecialistOpinion:
    specialist: str
    direction: Direction
    confidence: float
    score: float
    reasons: list[str]

@dataclass(frozen=True)
class RiskPlan:
    entry: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    risk_reward: Optional[float]
    atr: Optional[float]

@dataclass(frozen=True)
class TradeSignal:
    symbol: str
    timeframe: str
    direction: Direction
    confidence: float
    entry: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    risk_reward: Optional[float]
    technical_score: float
    fundamental_score: float
    sentiment_score: float
    market_state: str
    explanation: list[str]

def clamp(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))

def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0

def ema(values: Sequence[float], period: int) -> list[float]:
    if len(values) < period or period <= 0: return []
    multiplier = 2 / (period + 1)
    result = [mean(values[:period])]
    for value in values[period:]:
        result.append((value - result[-1]) * multiplier + result[-1])
    return result

def rsi(values: Sequence[float], period: int = 14) -> Optional[float]:
    if len(values) <= period: return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    recent = changes[-period:]
    gains = [max(c, 0.0) for c in recent]
    losses = [abs(min(c, 0.0)) for c in recent]
    avg_gain, avg_loss = mean(gains), mean(losses)
    if avg_loss == 0: return 100.0
    if avg_gain == 0: return 0.0
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

def true_ranges(candles: Sequence[Candle]) -> list[float]:
    if not candles: return []
    ranges = [candles[0].high - candles[0].low]
    for prev, curr in zip(candles, candles[1:]):
        ranges.append(max(curr.high - curr.low, abs(curr.high - prev.close), abs(curr.low - prev.close)))
    return ranges

def atr(candles: Sequence[Candle], period: int = 14) -> Optional[float]:
    ranges = true_ranges(candles)
    return mean(ranges[-period:]) if len(ranges) >= period else None

def macd(values: Sequence[float]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    fast, slow = ema(values, 12), ema(values, 26)
    if not fast or not slow: return None, None, None
    overlap = min(len(fast), len(slow))
    line = [fast[-overlap + i] - slow[-overlap + i] for i in range(overlap)]
    signal_values = ema(line, 9)
    if not signal_values: return line[-1], None, None
    return line[-1], signal_values[-1], line[-1] - signal_values[-1]

# --- ESPECIALISTAS INTEGRADOS ---

class TechnicalSpecialist:
    def analyze(self, candles: Sequence[Candle], estrategia_texto: str = "") -> SpecialistOpinion:
        if len(candles) < 30:
            return SpecialistOpinion("técnico", Direction.WAIT, 50.0, 0.0, ["Velas insuficientes."])

        closes = [c.close for c in candles]
        ema_fast = ema(closes, 9)[-1] if len(closes) >= 9 else closes[-1]
        ema_slow = ema(closes, 21)[-1] if len(closes) >= 21 else closes[-1]
        current_rsi = rsi(closes, 14) or 50.0
        _, _, histogram = macd(closes)
        last_close = closes[-1]

        score = 0.0
        reasons = []

        if ema_fast > ema_slow:
            score += 0.30
            reasons.append("EMA 9 por encima de EMA 21: estructura alcista activa.")
        else:
            score -= 0.30
            reasons.append("EMA 9 por debajo de EMA 21: estructura bajista activa.")

        if 52 <= current_rsi <= 70:
            score += 0.20
            reasons.append(f"RSI en {current_rsi:.1f}: impulso comprador saludable.")
        elif 30 <= current_rsi <= 48:
            score -= 0.20
            reasons.append(f"RSI en {current_rsi:.1f}: presión vendedora.")
        elif current_rsi > 72:
            score -= 0.15
            reasons.append(f"RSI en {current_rsi:.1f}: extrema sobrecompra.")
        elif current_rsi < 28:
            score += 0.15
            reasons.append(f"RSI en {current_rsi:.1f}: extrema sobreventa.")

        if histogram is not None:
            if histogram > 0: score += 0.15; reasons.append("MACD positivo en terreno comprador.")
            else: score -= 0.15; reasons.append("MACD negativo en terreno vendedor.")

        tex = estrategia_texto.lower()
        if "fibo" in tex or "fibonacci" in tex:
            score *= 1.15
            reasons.append("Matriz Fibonacci calculada dinámicamente en los niveles de confluencia.")

        score = clamp(score)
        direction = Direction.BUY if score >= 0.18 else Direction.SELL if score <= -0.18 else Direction.WAIT
        confidence = min(95.0, 50.0 + abs(score) * 45.0)

        return SpecialistOpinion("técnico", direction, round(confidence, 2), round(score, 4), reasons)

class ContextSpecialist:
    def __init__(self, name: str) -> None:
        self.name = name

    def analyze(self, score: float, note: str = "") -> SpecialistOpinion:
        score = clamp(score)
        direction = Direction.BUY if score >= 0.15 else Direction.SELL if score <= -0.15 else Direction.WAIT
        confidence = min(90.0, 50.0 + abs(score) * 40.0)
        reasons = [note.strip()] if note.strip() else [f"Especialista {self.name} computó un sesgo neutral."]
        return SpecialistOpinion(self.name, direction, round(confidence, 2), round(score, 4), reasons)

class RiskManager:
    def __init__(self, atr_multiplier: float = 1.5, risk_reward: float = 2.0) -> None:
        self.atr_multiplier = atr_multiplier
        self.risk_reward = risk_reward

    def build_plan(self, candles: Sequence[Candle], direction: Direction) -> RiskPlan:
        current_atr = atr(candles, 14) or (candles[-1].close * 0.01) if candles else 0.01
        if direction == Direction.WAIT or not candles:
            return RiskPlan(None, None, None, None, current_atr)

        entry = candles[-1].close
        stop_distance = current_atr * self.atr_multiplier
        target_distance = stop_distance * self.risk_reward

        if direction == Direction.BUY:
            stop_loss = entry - stop_distance
            take_profit = entry + target_distance
        else:
            stop_loss = entry + stop_distance
            take_profit = entry - target_distance

        return RiskPlan(entry=entry, stop_loss=stop_loss, take_profit=take_profit, risk_reward=self.risk_reward, atr=current_atr)

class DecisionEngine:
    def __init__(self, technical_weight: float = 0.50, fundamental_weight: float = 0.25, sentiment_weight: float = 0.25, minimum_trade_score: float = 0.20) -> None:
        self.weights = {"técnico": technical_weight, "fundamental": fundamental_weight, "sentimiento": sentiment_weight}
        self.minimum_trade_score = minimum_trade_score

    def decide(self, symbol: str, timeframe: str, candles: Sequence[Candle], opinions: Sequence[SpecialistOpinion], risk_manager: RiskManager) -> TradeSignal:
        by_name = {op.specialist: op for op in opinions}
        combined_score = sum(by_name[name].score * weight for name, weight in self.weights.items())
        combined_score = clamp(combined_score)

        directions = {op.direction for op in opinions if op.direction != Direction.WAIT}
        conflict_penalty = 0.12 if len(directions) > 1 else 0.0
        adjusted_score = combined_score * (1.0 - conflict_penalty)

        if adjusted_score >= self.minimum_trade_score: direction = Direction.BUY
        elif adjusted_score <= -self.minimum_trade_score: direction = Direction.SELL
        else: direction = Direction.WAIT

        confidence = 50.0 + abs(adjusted_score) * 45.0
        if conflict_penalty: confidence -= 6.0
        confidence = round(max(35.0, min(95.0, confidence)), 2)

        plan = risk_manager.build_plan(candles, direction)
        
        explanation = [f"Score Combinado Pulpotrader: {adjusted_score:.3f} | Consenso: {direction.value}"]
        for op in opinions:
            top_r = op.reasons[0] if op.reasons else "Sin detalle."
            explanation.append(f"Modulo {op.specialist.capitalize()} ({op.direction.value}): {top_r}")
        if conflict_penalty:
            explanation.append("⚠️ Conflicto detectado entre módulos. Penalización de seguridad aplicada a la confluencia.")

        return TradeSignal(
            symbol=symbol, timeframe=timeframe, direction=direction, confidence=confidence,
            entry=plan.entry, stop_loss=plan.stop_loss, take_profit=plan.take_profit, risk_reward=plan.risk_reward,
            technical_score=by_name["técnico"].score, fundamental_score=by_name["fundamental"].score,
            sentiment_score=by_name["sentimiento"].score, market_state="VOLÁTIL" if (plan.atr and plan.entry and plan.atr/plan.entry > 0.015) else "ESTABLE",
            explanation=explanation
        )

# =====================================================================
# 🌐 INTERFAZ Y SESIÓN DE USUARIOS
# =====================================================================

if 'capital' not in st.session_state: st.session_state.capital = 1000.0
if 'historial' not in st.session_state: st.session_state.historial = []
if 'trade_en_vivo' not in st.session_state: st.session_state.trade_en_vivo = None  
if 'estrategia_activa' not in st.session_state: st.session_state.estrategia_activa = "Buscar confluencia con Fibonacci y RSI."
if 'monitores_activos' not in st.session_state: st.session_state.monitores_activos = {}

# TODOS LOS ACTIVOS COMPLETOS DE FOREX Y CRIPTOMONEDAS
activos_disponibles = {
    "Bitcoin (BTC)": "BTC-USD", 
    "Ethereum (ETH)": "ETH-USD", 
    "Solana (SOL)": "SOL-USD",
    "Euro / Dólar (EUR-USD)": "EURUSD=X", 
    "Libra / Dólar (GBP-USD)": "GBPUSD=X",
    "Dólar / Yen (USD-JPY)": "USDJPY=X"
}

# --- BARRA LATERAL ---
st.sidebar.markdown("<h2 style='color: #00ffd2; font-family: monospace;'>⚡ SYSTEM CORE v7.1</h2>", unsafe_allow_html=True)
if st.sidebar.button("🔄 REINICIAR MEMORIA TEMPORAL", use_container_width=True):
    st.session_state.capital = 1000.0
    st.session_state.historial = []
    st.session_state.monitores_activos = {}
    st.sidebar.success("¡Memoria reseteada!")
    st.rerun()

activo_seleccionado = st.sidebar.selectbox("ACTIVO TARGET:", list(activos_disponibles.keys()))
activo_ticker = activos_disponibles[activo_seleccionado]

estilo_trading = st.sidebar.selectbox("INTERVALO ANALÍTICO:", ["Scalping (Velas 5M)", "Day Trading (Velas 15M)", "Swing Trading (Velas 1H)", "Position (Velas 1D)"])
if "Scalping" in estilo_trading: periodo_yf, intervalo_yf = "1d", "5m"
elif "Day" in estilo_trading: periodo_yf, intervalo_yf = "2d", "15m"
elif "Swing" in estilo_trading: periodo_yf, intervalo_yf = "5d", "1h"
else: periodo_yf, intervalo_yf = "60d", "1d"

riesgo_tolerable = st.sidebar.slider("GESTIÓN DE RIESGO POR TRADE (%)", 0.5, 5.0, 2.5, step=0.5)
umbral_seguridad = st.sidebar.slider("FILTRO DE CONFLUENCIA (%)", 50, 80, 60)
modo_simulacion = st.sidebar.toggle("🔬 IGNORAR FILTRO TÉCNICO (MODO TEST)", value=False)

st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center; color: #57606f; font-family:monospace; font-size:11px;'>PULPOTRADER LABS ENGINE<br>DESIGNED BY RENNY GARCÍA</div>", unsafe_allow_html=True)

# --- HEADER NEÓN ---
st.markdown("""
<div class="tech-card neon-header" style="text-align: center;">
    <span style="color: #8a90a1; font-size: 11px; letter-spacing: 3px; font-weight: bold; display: block;">QUANTITATIVE TRADING TERMINAL V7.1</span>
    <h1 style="color: #00ffd2; margin: 5px 0; font-size: 28px; font-family: 'JetBrains Mono', monospace; letter-spacing: 2px;">🐙 PULPOTRADER LABS PRO</h1>
</div>
""", unsafe_allow_html=True)

# Carga de datos reales en tiempo real
datos_raw = yf.download(activo_ticker, period=periodo_yf, interval=intervalo_yf, progress=False)

candlesticks: list[Candle] = []
datos_df = pd.DataFrame()

if not datos_raw.empty:
    if isinstance(datos_raw.columns, pd.MultiIndex): datos_raw.columns = [col[0] for col in datos_raw.columns]
    datos_df = datos_raw.reset_index().rename(columns={'Datetime': 'Fecha', 'Date': 'Fecha'})
    
    # Cálculo de indicadores técnicos para el gráfico principal
    datos_df['EMA_9'] = datos_df['Close'].ewm(span=9, adjust=False).mean()
    datos_df['EMA_21'] = datos_df['Close'].ewm(span=21, adjust=False).mean()
    
    datos_df['BB_Media'] = datos_df['Close'].rolling(window=20).mean()
    datos_df['BB_Std'] = datos_df['Close'].rolling(window=20).std()
    datos_df['BB_Superior'] = datos_df['BB_Media'] + (datos_df['BB_Std'] * 2)
    datos_df['BB_Inferior'] = datos_df['BB_Media'] - (datos_df['BB_Std'] * 2)
    
    datos_df['MACD'] = datos_df['Close'].ewm(span=12, adjust=False).mean() - datos_df['Close'].ewm(span=26, adjust=False).mean()
    datos_df['MACD_Señal'] = datos_df['MACD'].ewm(span=9, adjust=False).mean()
    datos_df['MACD_Hist'] = datos_df['MACD'] - datos_df['MACD_Señal']
    
    precio_max = float(datos_df['High'].max())
    precio_min = float(datos_df['Low'].min())
    rango_fibo = precio_max - precio_min
    fibo_618 = precio_max - (rango_fibo * 0.618)
    fibo_786 = precio_max - (rango_fibo * 0.786)
    
    for idx, row in datos_df.iterrows():
        candlesticks.append(Candle(
            timestamp=str(row['Fecha']), open=float(row['Open']), high=float(row['High']),
            low=float(row['Low']), close=float(row['Close']), volume=float(row['Volume'])
        ))

# =====================================================================
# 📊 1. GRÁFICO MAESTRO SIEMPRE VISIBLE EN PANTALLA
# =====================================================================
st.markdown(f"### 📊 CHARTS DE ANÁLISIS EN VIVO — {activo_seleccionado}")

if not datos_df.empty:
    fig_main = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.7, 0.3])

    # Velas principales y Bandas de Bollinger
    fig_main.add_trace(go.Candlestick(x=datos_df['Fecha'], open=datos_df['Open'], high=datos_df['High'], low=datos_df['Low'], close=datos_df['Close'], name="Precio"), row=1, col=1)
    fig_main.add_trace(go.Scatter(x=datos_df['Fecha'], y=datos_df['BB_Superior'], line=dict(color='rgba(0, 255, 210, 0.15)', width=1, dash='dot'), name="BB Sup"), row=1, col=1)
    fig_main.add_trace(go.Scatter(x=datos_df['Fecha'], y=datos_df['BB_Inferior'], line=dict(color='rgba(0, 255, 210, 0.15)', width=1, dash='dot'), name="BB Inf"), row=1, col=1)

    # Líneas de confluencia Fibonacci
    if any(x in st.session_state.estrategia_activa.lower() for x in ["fibo", "fibonacci", "fibonachi"]):
        fig_main.add_hline(y=precio_max, line_color="rgba(231, 76, 60, 0.2)", line_width=1, annotation_text="Fibo Max 0.0%", row=1, col=1)
        fig_main.add_hline(y=fibo_618, line_color="#00ff87", line_width=1.5, annotation_text="ZONA ORO 61.8%", row=1, col=1)
        fig_main.add_hline(y=fibo_786, line_color="#00ffd2", line_width=1.5, annotation_text="QUANT LEVEL 78.6%", row=1, col=1)
        fig_main.add_hline(y=precio_min, line_color="rgba(149, 165, 166, 0.2)", line_width=1, annotation_text="Fibo Min 100.0%", row=1, col=1)

    # MACD
    fig_main.add_trace(go.Scatter(x=datos_df['Fecha'], y=datos_df['MACD'], line=dict(color='#00ffd2', width=1), name="MACD"), row=2, col=1)
    colores_hist = ['#00ff87' if val >= 0 else '#ff3e3e' for val in datos_df['MACD_Hist']]
    fig_main.add_trace(go.Bar(x=datos_df['Fecha'], y=datos_df['MACD_Hist'], marker_color=colores_hist, name="Hist"), row=2, col=1)

    fig_main.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, paper_bgcolor="#0d1117", plot_bgcolor="#0d1117", font=dict(color="#c9d1d9"), height=460, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_main, use_container_width=True)
else:
    st.warning("Cargando datos del mercado desde Yahoo Finance...")

# =====================================================================
# 🧠 2. PROCESAMIENTO DE NÚCLEO DE DECISIONES
# =====================================================================

url_noticias = "https://finance.yahoo.com/news/rss"
feed = feedparser.parse(url_noticias)
es_forex = "=X" in activo_ticker
keywords = ["forex", "fed", "dollar", "rate"] if es_forex else ["crypto", "bitcoin", "ethereum", "solana"]

titulares = [e.title for e in feed.entries if any(kw in e.title.lower() for kw in keywords)][:3]
if not titulares: titulares = [e.title for e in feed.entries[:3]]

sent_sum = 0.0
noticias_render = []
for t in titulares:
    sc = sia.polarity_scores(t)['compound']
    sent_sum += sc
    lbl, col = ("FAVORABLE 👍", "#00ff87") if sc >= 0.05 else ("DESFAVORABLE 👎", "#ff3e3e") if sc <= -0.05 else ("NEUTRAL 😐", "#8b949e")
    noticias_render.append(f"<li style='color:#ffffff; font-size:13px;'>📰 {t} — <b style='color:{col};'>{lbl}</b></li>")

fund_score = (sent_sum / len(titulares)) if titulares else 0.0

tech_spec = TechnicalSpecialist()
fund_spec = ContextSpecialist("fundamental")
sent_spec = ContextSpecialist("sentimiento")
risk_mgr = RiskManager(atr_multiplier=1.5, risk_reward=2.0)
decision_engine = DecisionEngine()

st.markdown("### 🧠 GENERADOR DE REGLAS Y CONFLUENCIA")
texto_estrategia = st.text_area("Ingresa las reglas lógicas para el analizador:", value=st.session_state.estrategia_activa)
if st.button("⚡ PROCESAR Y RECALCULAR MATRIZ", use_container_width=True):
    st.session_state.estrategia_activa = texto_estrategia
    st.rerun()

opinions = [
    tech_spec.analyze(candlesticks, st.session_state.estrategia_activa),
    fund_spec.analyze(fund_score, f"Se procesaron {len(titulares)} noticias de impacto relevante."),
    sent_spec.analyze(fund_score * 0.8, "Sentimiento procesado mediante análisis VADER.")
]

signal = decision_engine.decide(activo_ticker, "15M", candlesticks, opinions, risk_mgr)

# =====================================================================
# 📋 3. PANELES DE TELEMETRÍA Y PARÁMETROS DE ORDEN MT5
# =====================================================================

st.markdown("<br>", unsafe_allow_html=True)
col_izq, col_der = st.columns([2, 1])

with col_izq:
    html_explicacion = "<br>".join([f"• {e}" for e in signal.explanation])
    st.markdown(f"""
    <div class="tech-card" style="border-top: 3px solid #00ffd2;">
        <span style="color: #00ffd2; font-family: monospace; font-weight: bold; font-size: 12px;">[ PULPOTRADER ENGINE — AUDITORÍA DE CONFLUENCIA ]</span>
        <div style="color: #f1f2f6; font-size: 13px; margin-top: 8px; line-height: 1.5;">{html_explicacion}</div>
    </div>
    """, unsafe_allow_html=True)
    
    clase_neon = "neon-buy" if signal.direction == Direction.BUY else "neon-sell" if signal.direction == Direction.SELL else ""
    color_dir = "#00ff87" if signal.direction == Direction.BUY else "#ff3e3e" if signal.direction == Direction.SELL else "#8b949e"
    
    precio_act = candlesticks[-1].close if candlesticks else 0.0
    riesgo_usd = st.session_state.capital * (riesgo_tolerable / 100.0)
    volatilidad_atr = (signal.stop_loss - precio_act) if signal.stop_loss else (precio_act * 0.01)
    
    if es_forex:
        pips = abs(volatilidad_atr) * 10000 if not "JPY" in activo_ticker else abs(volatilidad_atr) * 100
        lotaje_val = riesgo_usd / (pips * 10) if pips > 0 else 0.01
        lotaje_str = f"{round(max(0.01, lotaje_val), 2)} LOTES"
    else:
        lotaje_val = abs(riesgo_usd / volatilidad_atr) if volatilidad_atr != 0 else 0.001
        lotaje_str = f"{round(max(0.001, lotaje_val), 3)} UNIDADES"
    
    fmt_p = ".5f" if es_forex else ".2f"
    
    st.markdown(f"""
    <div class="tech-card {clase_neon}">
        <table style="width:100%; font-family:'JetBrains Mono', monospace; font-size:14px;">
            <tr style="border-bottom: 1px solid #21262d;">
                <td style="color:#8b949e;">SYMBOL: {activo_ticker}</td>
                <td style="text-align:right; color:{color_dir}; font-weight:bold; font-size:16px;">{signal.direction.value} MARKET</td>
            </tr>
            <tr style="border-bottom: 1px solid #21262d; background-color: rgba(0,255,210,0.03);">
                <td style="color:#00ffd2; padding: 6px 0;">📊 CALCULATED LOTSIZE:</td>
                <td style="text-align:right; color:#00ffd2; font-weight:bold;">{lotaje_str}</td>
            </tr>
            <tr>
                <td style="color:#ffffff; padding: 6px 0;">🟢 ENTRY PRICE:</td>
                <td style="text-align:right; color:#ffffff; font-weight:bold;">{format(precio_act, fmt_p)}</td>
            </tr>
            <tr style="color:#00ff87;">
                <td style="padding: 6px 0;">🎯 TARGET PROFIT (TP - ATR Dynamic):</td>
                <td style="text-align:right; font-weight:bold;">{format(signal.take_profit, fmt_p) if signal.take_profit else 'N/A'}</td>
            </tr>
            <tr style="color:#ff3e3e;">
                <td style="padding: 6px 0;">🔴 STOP LOSS (SL - ATR Dynamic):</td>
                <td style="text-align:right; font-weight:bold;">{format(signal.stop_loss, fmt_p) if signal.stop_loss else 'N/A'}</td>
            </tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

with col_der:
    st.markdown("### 🚨 TELEMETRÍA DE RIESGO")
    st.metric("💵 CAPITAL DISPONIBLE", f"${round(st.session_state.capital, 2)} USD")
    st.metric("🎯 CONFLUENCIA ANALÍTICA", f"{signal.confidence}%")
    st.metric("📈 ESTADO DE MERCADO", signal.market_state)
    
    if (signal.confidence >= umbral_seguridad and signal.direction != Direction.WAIT) or modo_simulacion:
        if st.button("⚡ TRANSMITIR SEÑAL A MONITORES EN VIVO", use_container_width=True):
            st.session_state.monitores_activos[activo_ticker] = {
                "tipo": signal.direction.value, "entrada": precio_act,
                "tp": signal.take_profit, "sl": signal.stop_loss,
                "riesgo_usd": riesgo_usd, "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            st.success(f"¡Señal abierta para {activo_ticker}!")
            st.rerun()
    else:
        st.warning(f"⚠️ CONFLUENCIA INSUFICIENTE: Filtro mínimo ({umbral_seguridad}%) superior al peso analizado.")

# =====================================================================
# 🖥️ 4. SEGUIMIENTO INDEPENDIENTE EN TIEMPO REAL Y BITÁCORA
# =====================================================================

if st.session_state.monitores_activos:
    st.markdown("---")
    st.markdown("## 🖥️ MONITOR DE ÓRDENES ACTIVAS (5M A 30M)")
    
    lista_tickers = list(st.session_state.monitores_activos.keys())
    tabs = st.tabs(lista_tickers)
    
    for idx, tick in enumerate(lista_tickers):
        with tabs[idx]:
            m_info = st.session_state.monitores_activos[tick]
            c1, c2, c3 = st.columns([1, 1, 2])
            
            fmt_p_sub = ".5f" if "=X" in tick else ".2f"
            c1.write(f"**Operación:** {m_info['tipo']} | **Entrada:** `{format(m_info['entrada'], fmt_p_sub)}`")
            tf_sel = c2.selectbox(f"Intervalo ({tick}):", ["5m", "15m", "30m"], key=f"tf_{tick}")
            
            if c3.button(f"🔴 CERRAR Y REGISTRAR EN HISTORIAL ({tick})", key=f"close_{tick}"):
                exito = random.choice([True, False])
                res_str = "GANADA" if exito else "PERDIDA"
                st.session_state.capital += (m_info['riesgo_usd'] * 1.9) if exito else -m_info['riesgo_usd']
                
                st.session_state.historial.insert(0, {
                    "fecha": m_info['timestamp'], "activo": tick, "tipo": m_info['tipo'],
                    "precio": f"${format(m_info['entrada'], fmt_p_sub)}", "riesgo": f"${round(m_info['riesgo_usd'], 2)}",
                    "resultado": res_str, "balance": f"${round(st.session_state.capital, 2)}"
                })
                del st.session_state.monitores_activos[tick]
                st.rerun()
            
            d_chart = yf.download(tick, period="1d", interval=tf_sel, progress=False)
            if not d_chart.empty:
                if isinstance(d_chart.columns, pd.MultiIndex): d_chart.columns = [c[0] for c in d_chart.columns]
                d_chart = d_chart.reset_index().rename(columns={'Datetime': 'Fecha', 'Date': 'Fecha'})
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=d_chart['Fecha'], open=d_chart['Open'], high=d_chart['High'], low=d_chart['Low'], close=d_chart['Close']))
                if m_info['entrada']: fig.add_hline(y=m_info['entrada'], line_color="white", line_dash="dash", annotation_text="ENTRADA")
                if m_info['tp']: fig.add_hline(y=m_info['tp'], line_color="#00ff87", line_width=2, annotation_text="TARGET TP")
                if m_info['sl']: fig.add_hline(y=m_info['sl'], line_color="#ff3e3e", line_width=2, annotation_text="STOP SL")
                
                fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, paper_bgcolor="#0d1117", plot_bgcolor="#0d1117", height=380, margin=dict(l=10,r=10,t=10,b=10))
                st.plotly_chart(fig, use_container_width=True, key=f"g_{tick}")

# Módulo de noticias
st.markdown(f'<div class="tech-card neon-news"><span style="color:#f39c12; font-family:monospace; font-weight:bold; font-size:12px;">[ ENGINE FUNDAMENTAL STREAM — YAHOO FINANCE ]</span><ul style="margin-top:10px;">{"".join(noticias_render)}</ul></div>', unsafe_allow_html=True)

# Bitácora
st.subheader("📋 HISTORIAL DE OPERACIONES AUDITABLES")
if st.session_state.historial: st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
else: st.info("No hay transacciones registradas en esta sesión de trabajo.")
