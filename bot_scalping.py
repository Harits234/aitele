import logging, asyncio
import requests
import pandas as pd
import ta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, filters, ContextTypes,
    ConversationHandler
)

TOKEN = "8125493408:AAGnuSkf_BwscznH9B_gjzSTNOrVgSd0jos"
PAIR_LIST = ["XAUUSD", "USDJPY", "EURUSD", "BTCUSD"]
SELECTING_PAIR = 1
user_pairs = {}

# Logging
logging.basicConfig(level=logging.INFO)

# Format pair Deriv
def format_symbol(symbol):
    return symbol.replace("USD", "").upper() + "USD"

# Ambil data harga dari Deriv
def get_data(symbol):
    symbol = format_symbol(symbol)
    url = f"https://api.deriv.com/api/v1/ohlc/ticks?instrument={symbol}&granularity=300&count=100"
    res = requests.get(url)
    try:
        data = res.json()
        candles = data["ohlc"]
        df = pd.DataFrame(candles)
        df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)
        df["Close"] = pd.to_numeric(df["Close"])
        df["High"] = pd.to_numeric(df["High"])
        df["Low"] = pd.to_numeric(df["Low"])
        df["Open"] = pd.to_numeric(df["Open"])
        return df
    except Exception as e:
        logging.error(f"Gagal ambil data Deriv: {e}")
        return None

# Logika sinyal trading
def get_signal(symbol):
    df = get_data(symbol)
    if df is None or df.empty:
        return None

    # Indikator teknikal
    df['ema50'] = ta.trend.ema_indicator(df['Close'], window=50)
    bb = ta.volatility.BollingerBands(df['Close'], window=20)
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    df['sar'] = ta.trend.psar_up(df['High'], df['Low'], df['Close'])

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    signal = None
    if latest['Close'] > latest['ema50'] and latest['Close'] < latest['bb_lower'] and latest['Close'] > latest['sar']:
        signal = f"🔔 BUY Signal pada {symbol}\nHarga: {latest['Close']:.2f}"
    elif latest['Close'] < latest['ema50'] and latest['Close'] > latest['bb_upper'] and latest['Close'] < latest['sar']:
        signal = f"🔔 SELL Signal pada {symbol}\nHarga: {latest['Close']:.2f}"
    return signal

# Bot Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [[pair] for pair in PAIR_LIST]
    await update.message.reply_text(
        "👋 Hai! Pilih pair untuk menerima sinyal scalping:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return SELECTING_PAIR

async def select_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    pair = update.message.text.upper()
    if pair in PAIR_LIST:
        user_pairs[chat_id] = pair
        await update.message.reply_text(f"✅ Pair {pair} dipilih. Tunggu sinyal setiap 10 menit!")
    else:
        await update.message.reply_text("⚠️ Pair tidak valid.")
    return ConversationHandler.END

async def send_signals(context: ContextTypes.DEFAULT_TYPE):
    for chat_id, symbol in user_pairs.items():
        signal = get_signal(symbol)
        if signal:
            await context.bot.send_message(chat_id=chat_id, text=signal)
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"⏳ Tidak ada sinyal di {symbol} saat ini.")

# Run bot
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={SELECTING_PAIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_pair)]},
        fallbacks=[],
    )
    app.add_handler(conv_handler)

    job_queue = app.job_queue
    job_queue.run_repeating(send_signals, interval=600, first=10)  # setiap 10 menit

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
