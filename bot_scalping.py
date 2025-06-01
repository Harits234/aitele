import requests, schedule, time
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from ta.trend import EMAIndicator, PSARIndicator
from ta.volatility import BollingerBands

# ===== KONFIGURASI =====
FINNHUB_API_KEY = 'd0ttfl9r01qlvahe9nu0d0ttfl9r01qlvahe9nug'
BOT_TOKEN = '8125493408:AAGnuSkf_BwscznH9B_gjzSTNOrVgSd0jos'

# ===== PAIR YANG DIDUKUNG =====
pairs_map = {
    "XAUUSD": "OANDA:XAU_USD",
    "USDJPY": "OANDA:USD_JPY",
    "EURUSD": "OANDA:EUR_USD",
    "BTCUSD": "BINANCE:BTCUSDT"
}
pairs = list(pairs_map.keys())

# ===== PENYIMPANAN USER =====
user_pair = {}
user_chat_id = {}

# ===== LOGIKA SINYAL =====
def get_signal(symbol):
    url = f'https://finnhub.io/api/v1/forex/candle?symbol={symbol}&resolution=5&count=100&token={FINNHUB_API_KEY}'
    res = requests.get(url).json()

    if not res or 'c' not in res or len(res['c']) < 50:
        return None

    close = pd.Series(res['c'])
    high = pd.Series(res['h'])
    low = pd.Series(res['l'])

    ema50 = EMAIndicator(close=close, window=50).ema_indicator()
    psar = PSARIndicator(high=high, low=low, close=close).psar()
    bb = BollingerBands(close=close, window=20)

    last_price = close.iloc[-1]
    last_ema = ema50.iloc[-1]
    last_psar = psar.iloc[-1]
    last_upper = bb.bollinger_hband().iloc[-1]
    last_lower = bb.bollinger_lband().iloc[-1]

    # BUY
    if last_price > last_ema and last_psar < last_price and last_price <= last_lower:
        return f"📉 Sinyal BUY\nHarga: {last_price:.2f}\nEMA50: {last_ema:.2f}"
    # SELL
    elif last_price < last_ema and last_psar > last_price and last_price >= last_upper:
        return f"📈 Sinyal SELL\nHarga: {last_price:.2f}\nEMA50: {last_ema:.2f}"
    else:
        return None

# ===== TELEGRAM HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[pair] for pair in pairs]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Pilih pair untuk sinyal scalping real-time:", reply_markup=reply_markup)

async def handle_pair_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    selected = update.message.text.upper()

    if selected in pairs:
        user_pair[user_id] = selected
        user_chat_id[user_id] = chat_id
        await update.message.reply_text(f"✅ Pair {selected} dipilih.\nSinyal akan dikirim tiap 10 menit bila kondisi terpenuhi.")
    else:
        await update.message.reply_text("❌ Pair tidak dikenali. Coba lagi.")

# ===== KIRIM SINYAL =====
async def send_signals(context: ContextTypes.DEFAULT_TYPE):
    for user_id, pair in user_pair.items():
        chat_id = user_chat_id[user_id]
        symbol = pairs_map[pair]
        signal = get_signal(symbol)
        if signal:
            await context.bot.send_message(chat_id=chat_id, text=f"📡 {pair}\n{signal}")

# ===== JALANKAN BOT =====
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pair_selection))

job_queue = app.job_queue
job_queue.run_repeating(send_signals, interval=600, first=10)  # tiap 10 menit

print("🚀 Bot scalping real-time aktif...")
app.run_polling()
