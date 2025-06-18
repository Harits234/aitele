import streamlit as st
import websocket
import json
import threading
import pandas as pd
import requests
import numpy as np

# ===== KONFIGURASI BOT TELEGRAM =====
BOT_TOKEN = "8125493408:AAGnuSkf_BwscznH9B_gjzSTNOrVgSd0jos"
CHAT_ID = "5622746102"
SYMBOL = "frxXAUUSD"
DURATION = 60  # timeframe 1 menit
CANDLE_LIMIT = 100

candles = []

# ===== FUNGSI TELEGRAM =====
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

# ===== PERHITUNGAN INDIKATOR MANUAL =====
def calculate_indicators(df):
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
    df['sar'] = calculate_parabolic_sar(df)
    return df

def calculate_parabolic_sar(df, af=0.02, max_af=0.2):
    length = len(df)
    sar = [df['low'][0]]
    ep = df['high'][0]
    trend = 1
    af_val = af

    for i in range(1, length):
        prev_sar = sar[-1]
        if trend == 1:
            curr_sar = prev_sar + af_val * (ep - prev_sar)
            if df['low'][i] < curr_sar:
                trend = -1
                curr_sar = ep
                ep = df['low'][i]
                af_val = af
            else:
                if df['high'][i] > ep:
                    ep = df['high'][i]
                    af_val = min(af_val + af, max_af)
        else:
            curr_sar = prev_sar + af_val * (ep - prev_sar)
            if df['high'][i] > curr_sar:
                trend = 1
                curr_sar = ep
                ep = df['high'][i]
                af_val = af
            else:
                if df['low'][i] < ep:
                    ep = df['low'][i]
                    af_val = min(af_val + af, max_af)
        sar.append(curr_sar)
    return sar

# ===== CEK SINYAL =====
def check_signal(df):
    latest = df.iloc[-1]
    confidence = 0
    reasons = []

    # Bollinger Band
    if latest['close'] < latest['bb_lower']:
        confidence += 1
        reasons.append("Close < Lower BB")
    elif latest['close'] > latest['bb_upper']:
        confidence += 1
        reasons.append("Close > Upper BB")

    # EMA
    if latest['close'] > latest['ema50']:
        confidence += 1
        reasons.append("Close > EMA50")
    elif latest['close'] < latest['ema50']:
        confidence += 1
        reasons.append("Close < EMA50")

    # SAR
    if latest['close'] > latest['sar']:
        confidence += 1
        reasons.append("SAR below price")
    elif latest['close'] < latest['sar']:
        confidence += 1
        reasons.append("SAR above price")

    # Kirim sinyal atau info
    if confidence >= 2:
        direction = "BUY" if latest['close'] > latest['ema50'] else "SELL"
        msg = f"📊 Signal: {direction} on XAUUSD (1M)\nConfidence: {confidence}/3 ({int((confidence/3)*100)}%)\nReason:\n- " + "\n- ".join(reasons)
        send_telegram_message(msg)
        st.success(msg)
    else:
        msg = f"❌ Tidak ada sinyal valid untuk XAUUSD (1M)\nConfidence: {confidence}/3"
        send_telegram_message(msg)
        st.warning(msg)

# ===== PROSES CANDLE =====
def process_candle(data):
    global candles
    ohlc = data['ohlc']
    candles.append([
        float(ohlc['open']),
        float(ohlc['high']),
        float(ohlc['low']),
        float(ohlc['close'])
    ])
    if len(candles) > CANDLE_LIMIT:
        candles = candles[-CANDLE_LIMIT:]

    df = pd.DataFrame(candles, columns=['open', 'high', 'low', 'close'])
    if len(df) >= 55:
        df = calculate_indicators(df)
        check_signal(df)

# ===== CALLBACK WEBSOCKET =====
def on_message(ws, message):
    data = json.loads(message)
    if data['msg_type'] == 'ohlc':
        process_candle(data)

def on_open(ws):
    msg = {
        "ticks_history": SYMBOL,
        "adjust_start_time": 1,
        "count": 1,
        "granularity": DURATION,
        "style": "candles",
        "subscribe": 1
    }
    ws.send(json.dumps(msg))

def on_error(ws, error):
    st.error(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    st.warning("WebSocket closed")

# ===== JALANKAN BOT WEBSOCKET =====
def run_bot():
    send_telegram_message("✅ Bot sinyal XAUUSD aktif di Streamlit Cloud.")
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp(
        "wss://ws.binaryws.com/websockets/v3?app_id=1089",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# ===== UI STREAMLIT =====
st.set_page_config(page_title="Bot Sinyal Trading", layout="centered")
st.title("🤖 Bot Sinyal Trading XAUUSD (Deriv WebSocket)")
st.caption("Real-time | EMA50 + BB + SAR | TF: 1M")

if st.button("🚀 Jalankan Bot"):
    thread = threading.Thread(target=run_bot)
    thread.daemon = True
    thread.start()
    st.success("✅ Bot sedang berjalan... sinyal dikirim via Telegram tiap candle.")
