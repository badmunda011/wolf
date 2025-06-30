import json
import random
import asyncio
import os
from TEAMZYRO import *
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- Use correct path for sukh.json ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORDS_PATH = os.path.join(BASE_DIR, "../../sukh.json")
with open(WORDS_PATH, "r", encoding="utf-8") as f:
    WORDS = set([w.strip().lower() for w in json.load(f)])

games = {}  # chat_id: game_data

def get_random_word(used_words):
    available = list(WORDS - used_words)
    return random.choice(available) if available else None

def is_valid_word(word, last_letter, used_words):
    word = word.lower()
    return (
        word in WORDS and
        word not in used_words and
        word[0] == last_letter
    )

def get_keyboard(game_id, action):
    buttons = []
    if action == "join":
        buttons = [[InlineKeyboardButton("Join Game", callback_data=f"join:{game_id}")]]
    elif action == "wait":
        buttons = [[InlineKeyboardButton("Waiting for players...", callback_data="wait")]]
    return InlineKeyboardMarkup(buttons)

@app.on_message(filters.command("play"))
async def play_game(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id in games and games[chat_id]["status"] != "ended":
        await message.reply("A game is already running in this chat.")
        return
    buttons = [
        [
            InlineKeyboardButton("2 Players", callback_data="choose_players:2"),
            InlineKeyboardButton("4 Players", callback_data="choose_players:4")
        ]
    ]
    await message.reply(
        "🎮 Word Game Started!\nChoose number of players:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"^choose_players:(\d+)$"))
async def choose_players_callback(client, cq: CallbackQuery):
    chat_id = cq.message.chat.id
    user_id = cq.from_user.id
    num_players = int(cq.matches[0].group(1))
    if chat_id in games and games[chat_id]["status"] != "ended":
        await cq.answer("A game is already running in this chat.", show_alert=True)
        return
    game_id = str(chat_id)
    games[chat_id] = {
        "players": [user_id],
        "needed": num_players,
        "status": "waiting",
        "used_words": set(),
        "turn": 0,
        "last_word": None,
        "last_letter": None,
        "timeout_task": None,
        "message_id": None
    }
    msg = await cq.edit_message_text(
        f"🎮 Word Game: {num_players} players mode!\nWaiting for others to join...\nClick below to join!",
        reply_markup=get_keyboard(game_id, "join")
    )
    games[chat_id]["message_id"] = msg.id

@app.on_callback_query(filters.regex(r"^join:(.+)$"))
async def join_game(client, cq: CallbackQuery):
    game_id = cq.matches[0].group(1)
    chat_id = int(game_id)
    user_id = cq.from_user.id

    if chat_id not in games or games[chat_id]["status"] != "waiting":
        await cq.answer("No game to join!", show_alert=True)
        return
    if user_id in games[chat_id]["players"]:
        await cq.answer("You already joined!", show_alert=True)
        return
    if len(games[chat_id]["players"]) >= games[chat_id]["needed"]:
        await cq.answer("Game is full!", show_alert=True)
        return

    games[chat_id]["players"].append(user_id)
    left = games[chat_id]["needed"] - len(games[chat_id]["players"])
    if left > 0:
        await cq.edit_message_text(
            f"{len(games[chat_id]['players'])}/{games[chat_id]['needed']} players joined!\nWaiting for {left} more...",
            reply_markup=get_keyboard(game_id, "join")
        )
    else:
        games[chat_id]["status"] = "running"
        await cq.edit_message_text(
            f"All players joined! Starting game...",
            reply_markup=get_keyboard(game_id, "wait")
        )
        await asyncio.sleep(1)
        await start_game(client, chat_id)

async def start_game(client, chat_id):
    game = games[chat_id]
    word = get_random_word(game["used_words"])
    if not word:
        await client.send_message(chat_id, "No words available to start the game! Please update sukh.json.")
        games[chat_id]["status"] = "ended"
        return
    game["last_word"] = word
    game["last_letter"] = word[-1]
    game["used_words"].add(word)
    turn = game["turn"]
    player = game["players"][turn % len(game["players"])]
    await client.send_message(
        chat_id,
        f"Game started!\nFirst word: <b>{word.capitalize()}</b>\n\n{await mention_player(client, player)}'s turn. Send a word starting with <b>{word[-1].upper()}</b> (35 seconds!)",
        parse_mode="html"
    )
    # Start timeout for first turn
    game["timeout_task"] = asyncio.create_task(word_timeout(client, chat_id, player, 35))

async def word_timeout(client, chat_id, player, timeout):
    await asyncio.sleep(timeout)
    if chat_id not in games or games[chat_id]["status"] != "running":
        return
    game = games[chat_id]
    if game.get("timeout_task"):
        game["timeout_task"].cancel()
        game["timeout_task"] = None
    loser = player
    # Winner is the next person in turn order
    idx = game["players"].index(loser)
    remaining = [p for i, p in enumerate(game["players"]) if i != idx]
    winner = remaining[game["turn"] % len(remaining)] if remaining else None
    await client.send_message(
        chat_id,
        f"⏰ <b>Time's up!</b>\n{await mention_player(client, loser)} didn't reply in time.\n🏆 {await mention_player(client, winner)} wins!",
        parse_mode="html"
    )
    game["status"] = "ended"

async def mention_player(client, user_id):
    user = await client.get_users(user_id)
    return f'<a href="tg://user?id={user_id}">{user.first_name}</a>'

@app.on_message(filters.text & ~filters.command(["play", "end"]))
async def handle_word(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in games or games[chat_id]["status"] != "running":
        return
    game = games[chat_id]
    num_players = len(game["players"])
    player = game["players"][game["turn"] % num_players]
    if user_id != player:
        await message.reply("It's not your turn!")
        return
    word = message.text.strip().lower()
    last_letter = game["last_letter"]
    if word in game["used_words"]:
        await message.reply("This word has already been used! Choose a different word.")
        return
    if not is_valid_word(word, last_letter, game["used_words"]):
        await message.reply(f"Invalid word!\n- Must start with '{last_letter.upper()}'\n- Must be in the word list\n- Must not be repeated")
        return
    # Cancel timeout
    if game.get("timeout_task"):
        game["timeout_task"].cancel()
        game["timeout_task"] = None
    game["used_words"].add(word)
    game["last_word"] = word
    game["last_letter"] = word[-1]
    game["turn"] += 1
    # Check if any possible next word exists
    possible = [w for w in WORDS if w not in game["used_words"] and w[0] == game["last_letter"]]
    if not possible:
        await message.reply(f"No more possible words!\n🏆 {await mention_player(client, user_id)} wins!", parse_mode="html")
        game["status"] = "ended"
        return
    # Next turn
    next_player = game["players"][game["turn"] % num_players]
    await client.send_message(
        chat_id,
        f"<b>{word.capitalize()}</b> accepted!\nNow {await mention_player(client, next_player)}'s turn. Send a word starting with <b>{game['last_letter'].upper()}</b> (35 seconds!)",
        parse_mode="html"
    )
    game["timeout_task"] = asyncio.create_task(word_timeout(client, chat_id, next_player, 35))

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
