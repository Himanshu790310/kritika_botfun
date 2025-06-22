import os
import logging
import google.generativeai as genai
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ContextTypes
)
from flask import Flask, request, jsonify

# Initialize Flask app for Cloud Function
app = Flask(__name__)

# ======================
# CONFIGURATION
# ======================
TELEGRAM_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
GEMINI_API_KEY = os.environ['GOOGLE_API_KEY']

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

# ======================
# TELEGRAM WEBHOOK SETUP
# ======================
def setup_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return application

bot_application = setup_bot()

# ======================
# HANDLERS (Same as before)
# ======================
async def start(update: Update, context: CallbackContext):
    # ... (same start handler as before)

async def handle_message(update: Update, context: CallbackContext):
    # ... (same message handler as before)

# ======================
# CLOUD FUNCTION ENTRY POINT
# ======================
@app.route('/webhook', methods=['POST'])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot_application.bot)
        await bot_application.process_update(update)
    return jsonify(success=True)

@app.route('/set_webhook', methods=['GET'])
async def set_webhook():
    url = f"https://{os.environ.get('GOOGLE_CLOUD_PROJECT')}.cloudfunctions.net/webhook"
    await bot_application.bot.set_webhook(url)
    return jsonify(success=True, url=url)

# For local testing
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
