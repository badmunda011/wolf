from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from TEAMZYRO import app, user_collection
import html

FILTERS = {
    "all_time": "All Time",
    "today": "Today",
    "this_week": "This Week",
    "this_month": "This Month",
    "this_year": "This Year",
    "this_chat": "This Chat"
}

def get_time_filter(filter_key):
    now = datetime.utcnow()
    if filter_key == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif filter_key == "this_week":
        return now - timedelta(days=now.weekday())
    elif filter_key == "this_month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif filter_key == "this_year":
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return None  # all time

def leaderboard_buttons(active):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                ("✅ " if active == "all_time" else "") + "All Time", callback_data="lb_all_time"),
            InlineKeyboardButton(
                ("✅ " if active == "today" else "") + "Today", callback_data="lb_today"),
            InlineKeyboardButton(
                ("✅ " if active == "this_week" else "") + "This Week", callback_data="lb_this_week"),
        ],
        [
            InlineKeyboardButton(
                ("✅ " if active == "this_month" else "") + "This Month", callback_data="lb_this_month"),
            InlineKeyboardButton(
                ("✅ " if active == "this_year" else "") + "This Year", callback_data="lb_this_year"),
            InlineKeyboardButton(
                ("✅ " if active == "this_chat" else "") + "This Chat", callback_data="lb_this_chat"),
        ]
    ])

@app.on_message(filters.command("leaderboard"))
async def leaderboard_command(client, message):
    await show_leaderboard(client, message, "all_time")

@app.on_callback_query(filters.regex(r"^lb_(\w+)$"))
async def leaderboard_callback(client, callback_query):
    filter_key = callback_query.matches[0].group(1)
    await show_leaderboard(client, callback_query.message, filter_key, callback_query=callback_query)

async def show_leaderboard(client, msg, filter_key, callback_query=None):
    chat_id = msg.chat.id if hasattr(msg, "chat") else None
    filter_date = get_time_filter(filter_key)
    leaderboard_data = []

    # Sabhi users fetch karo
    users = await user_collection.find({}).to_list(length=0)
    for user in users:
        wins = user.get("wins", [])
        user_coins = 0

        # Filter lagao har win pe
        for win in wins:
            win_time = win.get("timestamp")
            win_chat = win.get("chat_id")
            # timestamp field string ho toh parse karo
            if isinstance(win_time, str):
                try:
                    win_time = datetime.fromisoformat(win_time)
                except Exception:
                    continue
            # Filter logic
            if filter_key == "all_time":
                user_coins += 1
            elif filter_key == "today" and win_time and win_time >= filter_date:
                user_coins += 1
            elif filter_key == "this_week" and win_time and win_time >= filter_date:
                user_coins += 1
            elif filter_key == "this_month" and win_time and win_time >= filter_date:
                user_coins += 1
            elif filter_key == "this_year" and win_time and win_time >= filter_date:
                user_coins += 1
            elif filter_key == "this_chat" and win_chat == chat_id:
                user_coins += 1

        if user_coins > 0:
            leaderboard_data.append({
                "id": user.get("id"),
                "first_name": user.get("first_name", "Unknown"),
                "coins": user_coins
            })

    # Sort karo sabse jyada coins walo ke hisab se
    leaderboard = sorted(leaderboard_data, key=lambda x: x["coins"], reverse=True)[:10]

    text = f"<b>🏆 Leaderboard ({FILTERS.get(filter_key, 'All Time')})</b>\n\n"
    for idx, user in enumerate(leaderboard, 1):
        first_name = html.escape(user.get("first_name", "Unknown"))[:15]
        coins = user.get("coins", 0)
        user_id = user.get("id")
        medal = "👑 " if idx == 1 else ""
        text += f"{medal}{idx}. <a href='tg://user?id={user_id}'><b>{first_name}</b></a>: {coins} coins\n"

    if not leaderboard:
        text += "Koi record nahi mila."

    if callback_query:
        await callback_query.edit_message_text(
            text, reply_markup=leaderboard_buttons(filter_key), disable_web_page_preview=True)
    else:
        await msg.reply_text(
            text, reply_markup=leaderboard_buttons(filter_key), disable_web_page_preview=True)
