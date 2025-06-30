import asyncio
import os
import json
from datetime import datetime
import random
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from TEAMZYRO import user_collection
from TEAMZYRO import app

# --- Use correct path for sukh.json ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORDS_PATH = os.path.join(BASE_DIR, "../../sukh.json")
with open(WORDS_PATH, "r", encoding="utf-8") as f:
    WORDS = set([w.strip().lower() for w in json.load(f)])

ROUND_TIME = 35  # seconds

# Structure: {chat_id: {word: str, players: set, winner: int or None}}
games = {}

@app.on_message(filters.command("play"))
async def play_command(client, message: Message):
    buttons = [
        [
            InlineKeyboardButton("2 Players", callback_data="start_2"),
            InlineKeyboardButton("4 Players", callback_data="start_4"),
        ]
    ]
    await message.reply_text(
        "Choose the number of players:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"^start_(2|4)$"))
async def start_game(client, callback_query):
    num_players = int(callback_query.matches[0].group(1))
    chat_id = callback_query.message.chat.id

    if chat_id in games:
        await callback_query.answer("Game already running in this chat.")
        return

    word = random.choice(list(WORDS))
    games[chat_id] = {
        "word": word,
        "players": set(),
        "winner": None,
        "start_time": datetime.utcnow()
    }

    await callback_query.message.reply_text(
        f"Word guessing game started for {num_players} players!\n"
        f"First to guess the word gets 50 coins!\n"
        f"Time: {ROUND_TIME}s\n"
        f"Word: {' '.join('_' for _ in word)}\n\n"
        f"Reply in chat with your guess!"
    )

    try:
        await asyncio.wait_for(monitor_guesses(client, chat_id, word, num_players), timeout=ROUND_TIME)
    except asyncio.TimeoutError:
        # Time's up
        if games.get(chat_id, {}).get("winner") is None:
            await client.send_message(chat_id, f"⏱ Time's up! No one guessed the word.\nThe word was: <b>{word}</b>", parse_mode="html")
        games.pop(chat_id, None)

async def monitor_guesses(client, chat_id, word, num_players):
    from pyrogram.handlers import MessageHandler

    guessed = asyncio.Event()

    async def guess_handler(c, m: Message):
        if m.chat.id != chat_id or m.from_user is None:
            return
        user_id = m.from_user.id
        first_name = m.from_user.first_name
        user_guess = m.text.strip().lower()
        if user_guess == word.lower():
            if games[chat_id]["winner"] is None:
                games[chat_id]["winner"] = user_id
                games[chat_id]["players"].add(user_id)
                await update_user_win(user_id, chat_id, first_name)
                await m.reply(
                    f"🎉 <a href='tg://user?id={user_id}'>{first_name}</a> guessed it right! +50 coins awarded.",
                )
                guessed.set()
        else:
            games[chat_id]["players"].add(user_id)

        if len(games[chat_id]["players"]) >= num_players:
            guessed.set()

    handler = MessageHandler(guess_handler)
    client.add_handler(handler)

    await guessed.wait()

    client.remove_handler(handler)
    games.pop(chat_id, None)

async def update_user_win(user_id, chat_id, first_name):
    now = datetime.utcnow()
    await user_collection.update_one(
        {"id": user_id},
        {
            "$set": {"first_name": first_name},
            "$inc": {"coins": 50},
            "$push": {"wins": {"timestamp": now, "chat_id": chat_id}}
        },
        upsert=True
    )
    
@app.on_message(filters.command("end"))
async def end_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id in games and games[chat_id]["status"] != "ended":
        games[chat_id]["status"] = "ended"
        # Cancel timeout if exists
        if games[chat_id].get("timeout_task"):
            games[chat_id]["timeout_task"].cancel()
            games[chat_id]["timeout_task"] = None
        await message.reply("Game ended!")
    else:
        await message.reply("No active game to end.")
