import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext
)
from flask import Flask, request, jsonify
from google.cloud import secretmanager

# Initialize Flask app
app = Flask(__name__)

# ======================
# LOGGING CONFIGURATION
# ======================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('EnglishTeachingBot')

# ======================
# SECRET MANAGEMENT
# ======================
def access_secret(secret_name):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode('UTF-8')

TELEGRAM_TOKEN = access_secret('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = access_secret('GOOGLE_API_KEY')

# ======================
# GEMINI AI SETUP
# ======================
genai.configure(api_key=GEMINI_API_KEY)

GENERATION_CONFIG = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2500,
}

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

SYSTEM_INSTRUCTION = """# Role: Kritika - The Perfect English Teacher for Hindi Speakers

## Core Identity:
You are Kritika, an AI English teacher specializing in teaching Hindi speakers through Hinglish. Your personality is:
- Warm and encouraging like a favorite teacher
- Patient and clear in explanations
- Culturally aware of Indian contexts
- Strict about proper English but gentle in corrections

## Teaching Methodology:
1. Concept Explanation:
   - Give Hindi explanation (Roman script)
   - Show English structure/formula
   - Provide 5 simple examples
   - Contrast with Hindi sentence structure

2. Error Correction:
   - Never say "Wrong!" - instead: "Good try! More accurately we say..."
   - Highlight mistakes gently: "Yahan 'has' ki jagah 'have' aayega because..."
   - Always provide corrected version

3. Practical Help:
   - Real-life Indian context examples
   - Pronunciation guides with Hindi phonetics
   - Short practice exercises when requested

## Communication Style:
- Language Preference:
  - If question in Hindi: Reply in Hinglish (90% Hindi + 10% English)
  - If question in English: Reply in English
  - Example: "Present perfect tense mein hum 'has/have' ke saath verb ka third form use karte hai"

- Tone:
  - Encouraging: "Bahut accha attempt! Thoda sa correction..."
  - Supportive: "Chinta mat karo, practice se perfect hoga!"
  - Respectful: "Aapka sawal bahut relevant hai"

## Special Features:
1. Instant Help:
   - When user says "help" or "samjhao":
     1. Simplify concept
     2. Give 3 basic examples
     3. Offer alternative explanation

2. Cultural Adaptation:
   - Use Indian examples: "Jaise hum 'I am going to mandir' ke jagah 'I am going to the temple' kahenge"
   - Explain Western concepts in Indian context

## Prohibitions:
- No word-for-word translations
- No romantic/political/religious examples
- Don't overwhelm with information
- Never use complex English to explain basics

## Response Format:
1. Start with greeting if new conversation
2. Explain concept in simple steps
3. Provide examples
4. End with:
   - "Aur koi doubt hai?"
   - "Mai aur madad kar sakti hoon?"

## Example Interactions:
User: "Present perfect tense samjhao"
Response:
Namaste! Present perfect tense ke baare mein samjha deti hoon:

1. Concept: Ye tense batata hai ki koi action past mein shuru hua aur uska effect present tak hai.

2. Structure:
   Subject + has/have + verb ka 3rd form

3. Examples:
   - Mai Delhi gaya hoon (I have gone to Delhi)
   - Usne khana kha liya hai (She has eaten food)
   - Humne movie dekh li hai (We have watched the movie)

4. Hindi Comparison:
    Hindi mein hum "cha hai", "liya hai" ka use karte hai
    English mein "have/has" + verb ka 3rd form

Koi aur doubt hai?"""

try:
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash-latest",
        generation_config=GENERATION_CONFIG,
        safety_settings=SAFETY_SETTINGS
    )
    logger.info("Gemini model initialized successfully")
except Exception as e:
    logger.critical(f"Failed to initialize Gemini model: {e}")
    raise

# ======================
# CONVERSATION MANAGER
# ======================
class ConversationManager:
    def __init__(self):
        self.conversations = {}
        
    async def get_chat(self, chat_id):
        if chat_id not in self.conversations:
            self.conversations[chat_id] = model.start_chat(
                history=[{"role": "user", "parts": [SYSTEM_INSTRUCTION]}]
            )
            logger.info(f"New chat session started for {chat_id}")
        return self.conversations[chat_id]

conversation_manager = ConversationManager()

# ======================
# TELEGRAM BOT SETUP
# ======================
def setup_bot_application():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    return application

bot_application = setup_bot_application()

# ======================
# TELEGRAM HANDLERS
# ======================
async def start(update: Update, context: CallbackContext):
    try:
        chat_id = update.effective_chat.id
        user = update.effective_user
        await conversation_manager.get_chat(chat_id)
        
        welcome_msg = (
            f"Namaste {user.first_name}!\n\n"
            "Main Kritika hoon - aapki personal English teacher.\n\n"
            "Mujhse aap poochh sakte hain:\n"
            "• Grammar concepts\n• Sentence corrections\n• Translations\n"
            "• Vocabulary doubts\n• Pronunciation help\n\n"
            "Koi bhi English-related problem ho, bas message kijiye!\n\n"
            "Chaliye shuru karte hain... Aaj aap kya seekhna chahenge?"
        )
        await update.message.reply_text(welcome_msg)
        logger.info(f"Sent welcome message to {chat_id}")
    except Exception as e:
        logger.error(f"Error in start handler: {e}", exc_info=True)
        if update.effective_chat:
            await update.effective_chat.send_message(
                "Kuch technical problem aa gayi hai. Kripya thodi der baad try karein."
            )

async def handle_message(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_message = update.message.text
    
    if not user_message:
        logger.warning(f"Empty message from {chat_id}")
        return

    try:
        logger.info(f"Processing message from {chat_id}: {user_message[:100]}...")
        chat = await conversation_manager.get_chat(chat_id)
        response = await chat.send_message(user_message)
        
        if response.text:
            await update.message.reply_text(response.text)
            logger.info(f"Response sent to {chat_id}")
        else:
            logger.error(f"Empty response from Gemini for {chat_id}")
            await update.message.reply_text(
                "Maaf karna, main samjha nahi. Kya aap phir se try kar sakte hain?\n\n"
                "Ya phir aap 'help' likh kar mujhe bata sakte hain ki aapko kis cheez mein difficulty aa rahi hai."
            )
    except Exception as e:
        logger.error(f"Error handling message for {chat_id}: {e}", exc_info=True)
        if update.effective_chat:
            await update.effective_chat.send_message(
                "Kuch technical problem aa raha hai. Hum team ko inform kar diya hai.\n\n"
                "Kripya kuch samay baad phir try karein. Dhanyavaad!"
            )

async def error_handler(update: Update, context: CallbackContext):
    error = context.error
    logger.error(f"Telegram error: {error}", exc_info=True)
    
    if update and update.effective_chat:
        try:
            await update.effective_chat.send_message(
                "Kuch technical problem aa gayi hai. Hum ise fix kar rahe hain.\n\n"
                "Kripya thodi der baad phir try karein. Dhanyavaad!"
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

# ======================
# CLOUD FUNCTION ENDPOINTS
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

@app.route('/')
def health_check():
    return jsonify(
        status="healthy",
        service="english-teaching-bot",
        telegram_ready=bot_application is not None,
        gemini_ready=model is not None
    )

# For local testing
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
