from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultGame
)
from telegram.ext import (
    ContextTypes, CommandHandler, Application, InlineQueryHandler
)
from TEAMZYRO import application

GAME_SHORT_NAME = "my_html5_game"  # BotFather me registered short name
GAME_URL = "https://yourdomain.com/game/index.html"

# Play Command
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("▶️ Play Now", callback_game={"game_short_name": GAME_SHORT_NAME})]
    ]
    await update.message.reply_game(GAME_SHORT_NAME, reply_markup=InlineKeyboardMarkup(keyboard))

# Inline Query Handler for Games
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query  # User ka search query
    results = [
        InlineQueryResultGame(
            id="1",
            game_short_name=GAME_SHORT_NAME
        )
    ]
    await update.inline_query.answer(results, cache_time=10)

# Game Leaderboard Command
async def gameboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Pehle game message pe reply karo jo bot ne bheja tha.")
        return

    game_message = update.message.reply_to_message
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_id = game_message.message_id

    try:
        scores = await context.bot.get_game_high_scores(user_id=user_id, chat_id=chat_id, message_id=message_id)
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching leaderboard: {e}")
        return

    if not scores:
        await update.message.reply_text("❌ Koi score nahi mila.")
        return

    text = "🏆 Game Leaderboard:\n\n"
    for idx, score in enumerate(scores, 1):
        text += f"{idx}. {score.user.first_name} - {score.score} points\n"

    await update.message.reply_text(text)

# Register handlers
application.add_handler(CommandHandler("start", Start))
application.add_handler(CommandHandler("gameboard", gameboard))
application.add_handler(InlineQueryHandler(inline_query))  # <-- Yeh line add karein!
