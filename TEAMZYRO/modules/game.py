import json
import random
import asyncio
import os
from TEAMZYRO import *
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORDS_PATH = os.path.join(BASE_DIR, "../../sukh.json")
with open(WORDS_PATH, "r", encoding="utf-8") as f:
    WORDS = set([w.strip().lower() for w in json.load(f)])

games = {}  # chat_id: game_data

TIMEOUT_SECONDS = 25  # <-- Bas yahan se timeout control hoga

# ----------- COINS UPDATE FUNCTION (NEW) -----------
from TEAMZYRO import user_collection

async def update_coins(user_id, first_name, coins):
    await user_collection.update_one(
        {"id": user_id},
        {
            "$set": {"first_name": first_name},
            "$inc": {"coins": coins}
        },
        upsert=True
    )

# ---------------------------------------------------

def get_random_word(used_words):
    available = [w for w in WORDS if 3 <= len(w) <= 6 and w not in used_words]
    return random.choice(available) if available else None

def is_valid_word(word, last_letter, used_words):
    word = word.lower()
    return (
        word in WORDS and
        word not in used_words and
        word[0] == last_letter and
        3 <= len(word) <= 6 and
        " " not in word
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
        "message_id": None,
        "scores": {user_id: 0 for user_id in [user_id]},
        "current_turn": None  # Added to track the current turn's player
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
    games[chat_id]["scores"][user_id] = 0
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
    game["current_turn"] = player  # Track current turn's player
    game["turn_start_time"] = asyncio.get_event_loop().time()
    await client.send_message(
        chat_id,
        f"Game started!\nFirst word: <b>{word.capitalize()}</b>\n\n{await mention_player(client, player)}'s turn. Send a word starting with <b>{word[-1].upper()}</b> ({TIMEOUT_SECONDS} seconds!)",
    )
    # Start timeout for first turn
    game["timeout_task"] = asyncio.create_task(word_timeout(client, chat_id, player, TIMEOUT_SECONDS))

async def word_timeout(client, chat_id, player, timeout):
    try:
        await asyncio.sleep(timeout)
        if chat_id not in games or games[chat_id]["status"] != "running":
            return
        game = games[chat_id]
        # Check if the player is still the current turn's player
        if game.get("current_turn") != player:
            return
        # Cancel timeout task
        if game.get("timeout_task"):
            game["timeout_task"] = None
        loser = player
        idx = game["players"].index(loser)
        # Remove loser from the game for next turn calculation
        remaining_players = [p for i, p in enumerate(game["players"]) if i != idx]
        num_players = len(game["players"])
        winner = None

        # Coin/scoring system
        if num_players == 2:
            winner = remaining_players[0] if remaining_players else None
            if winner:
                game["scores"][winner] += 50

                # --------- DATABASE UPDATE (NEW) -----------
                user = await client.get_users(winner)
                await update_coins(winner, user.first_name, 50)
                loser_user = await client.get_users(loser)
                await update_coins(loser, loser_user.first_name, 0)
                # --------------------------------------------

            game["scores"][loser] = 0
            score_text = f"{await mention_player(client, winner)} wins and gets 50 coins!\n{await mention_player(client, loser)} gets 0 coins."
        elif num_players == 4:
            # Distribute 50 coins by speed
            turn_end_time = asyncio.get_event_loop().time()
            game["scores"][loser] = 0
            winner_idx = (game["turn"] + 1) % len(remaining_players)
            winner = remaining_players[winner_idx] if remaining_players else None

            # Calculate time taken by each player, assign coins
            total_time = 0
            times = {}
            for uid in remaining_players:
                times[uid] = game.get(f"user_time_{uid}", 0)
                total_time += times[uid]
            if total_time == 0:
                for uid in remaining_players:
                    game["scores"][uid] += 17

                    # ------------- DATABASE UPDATE --------------
                    user = await client.get_users(uid)
                    await update_coins(uid, user.first_name, 17)
                    # --------------------------------------------
            else:
                for uid in remaining_players:
                    coins = min(50, max(1, int((1 - (times[uid] / total_time)) * 50)))
                    game["scores"][uid] += coins

                    # ----------- DATABASE UPDATE -------------
                    user = await client.get_users(uid)
                    await update_coins(uid, user.first_name, coins)
                    # -----------------------------------------

            # Loser gets 0 coins in DB as well
            loser_user = await client.get_users(loser)
            await update_coins(loser, loser_user.first_name, 0)

            score_text = "Coin Distribution:\n"
            for uid in remaining_players:
                score_text += f"{await mention_player(client, uid)}: {game['scores'][uid]} coins\n"
            score_text += f"\n{await mention_player(client, loser)} gets 0 coins."
        else:
            score_text = ""
        await client.send_message(
            chat_id,
            f"⏰ <b>Time's up!</b>\n{await mention_player(client, loser)} didn't reply in time.\n{score_text}"
        )
        game["status"] = "ended"
    except asyncio.CancelledError:
        pass  # Handle task cancellation gracefully

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
    # Ignore messages that are not from the player whose turn it is
    if user_id != player:
        return

    word = message.text.strip().lower()
    if not (3 <= len(word) <= 6):
        return
    if " " in word:
        return

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
    # Time calculation for scoring
    now_time = asyncio.get_event_loop().time()
    turn_time = now_time - game.get("turn_start_time", now_time)
    game[f"user_time_{user_id}"] = game.get(f"user_time_{user_id}", 0) + turn_time

    game["used_words"].add(word)
    game["last_word"] = word
    game["last_letter"] = word[-1]
    game["turn"] += 1
    game["turn_start_time"] = asyncio.get_event_loop().time()
    # Check if any possible next word exists
    possible = [w for w in WORDS if w not in game["used_words"] and w[0] == game["last_letter"] and 3 <= len(w) <= 6]
    if not possible:
        await message.reply(f"No more possible words!\n🏆 {await mention_player(client, user_id)} wins!")
        game["scores"][user_id] += 50  # winner gets 50

        # -------- DATABASE UPDATE (NEW) ----------
        user = await client.get_users(user_id)
        await update_coins(user_id, user.first_name, 50)
        # -----------------------------------------

        game["status"] = "ended"
        return
    # Next turn
    next_player = game["players"][game["turn"] % num_players]
    game["current_turn"] = next_player  # Update current turn's player
    await client.send_message(
        chat_id,
        f"<b>{word.capitalize()}</b> accepted!\nNow {await mention_player(client, next_player)}'s turn. Send a word starting with <b>{game['last_letter'].upper()}</b> ({TIMEOUT_SECONDS} seconds!)",
    )
    game["timeout_task"] = asyncio.create_task(word_timeout(client, chat_id, next_player, TIMEOUT_SECONDS))

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
