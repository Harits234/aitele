import streamlit as st
import websocket
import json
import threading
import pandas as pd
import pandas_ta as ta
import requests

# ===== SETUP TELEGRAM =====
BOT_TOKEN = "8125493408:AAGnuSkf_BwscznH9B_gjzSTNOrVgSd0jos"
CHAT_ID = "5622746102"

# ===== SETUP PAIR DAN CANDLE =====
SYMBOL = "frxXAUUSD"  # bisa diganti frxEURUSD, frxGBPUSD
DURATION = 60  # 1 menit
CANDLE_LIMIT = 55

# ===== STATE CANDLE =====
candles = []

# ===== KIRIM PESAN TELEGRAM =====
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

# ===== CEK SINYAL DARI KOMBINASI 3 INDIKATOR =====
def check_signal(df):
    latest = df.iloc[-1]
    valid = {
        "bb": False,
        "sar": False,
        "ema": False
    }

    # Cek BB
    if latest['close'] < latest['BBL_20_2.0']:
        valid["bb"] = "buy"
    elif latest['close'] > latest['BBU_20_2.0']:
        valid["bb"] = "sell"

    # Cek SAR
    if latest['sar'] < latest['close']:
        valid["sar"] = "buy"
    elif latest['sar'] > latest['close']:
        valid["sar"] = "sell"

    # Cek EMA
    if latest['close'] > latest['ema50']:
        valid["ema"] = "buy"
    elif latest['close'] < latest['ema50']:
        valid["ema"] = "sell"

    all_values = list(valid.values())
    buy_count = all_values.count("buy")
    sell_count = all_values.count("sell")

    if buy_count >= 2:
        confidence = int((buy_count / 3) * 100)
        return f"📈 BUY Signal on XAUUSD (1M)\nConfidence: {confidence}%"
    elif sell_count >= 2:
        confidence = int((sell_count / 3) * 100)
        return f"📉 SELL Signal on XAUUSD (1M)\nConfidence: {confidence}%"

    return None

# ===== PROSES CANDLE MASUK =====
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
    df['ema50'] = ta.ema(df['close'], length=50)
    bb = ta.bbands(df['close'], length=20)
    df = df.join(bb)
    df['sar'] = ta.sar(df['high'], df['low'])

    signal = check_signal(df)
    if signal:
        send_telegram_message(signal)
        st.success(signal)

# ===== CALLBACK WEBSOCKET =====
def on_message(ws, message):
    data = json.loads(message)
    if data['msg_type'] == 'ohlc':
        process_candle(data)

def on_error(ws, error):
    st.error(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    st.warning("WebSocket closed")

def on_open(ws):
    sub_msg = {
        "ticks_history": SYMBOL,
        "adjust_start_time": 1,
        "count": 1,
        "granularity": DURATION,
        "style": "candles",
        "subscribe": 1
    }
    ws.send(json.dumps(sub_msg))

# ===== JALANKAN BOT =====
def run_bot():
    send_telegram_message("✅ Bot sinyal XAUUSD telah AKTIF dan siap mengirim sinyal...")
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp(
        "wss://ws.binaryws.com/websockets/v3?app_id=1089",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# ===== STREAMLIT UI =====
st.title("📡 Bot Sinyal Trading XAUUSD - Real-time Deriv")
st.markdown("Indikator: **EMA50 + Bollinger Bands + Parabolic SAR**")
st.markdown("---")

if st.button("🚀 Jalankan Bot Sekarang"):
    t = threading.Thread(target=run_bot)
    t.daemon = True
    t.start()
    st.success("✅ Bot aktif. Tunggu sinyal dikirim ke Telegram.")
    st.info("Bot akan mengirim sinyal hanya jika minimal 2 dari 3 indikator cocok (Buy/Sell).")
