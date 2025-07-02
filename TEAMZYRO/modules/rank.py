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
        start_of_week = now - timedelta(days=now.weekday())
        return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    elif filter_key == "this_month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif filter_key == "this_year":
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return None  # For all_time and this_chat

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

    pipeline = []

    if filter_key == "this_chat":
        pipeline = [
            {
                "$project": {
                    "id": 1,
                    "first_name": 1,
                    "coins": {
                        "$size": {
                            "$filter": {
                                "input": "$wins",
                                "as": "win",
                                "cond": {"$eq": ["$$win.chat_id", chat_id]}
                            }
                        }
                    }
                }
            },
            {"$sort": {"coins": -1}},
            {"$limit": 10}
        ]

    elif filter_key in ["today", "this_week", "this_month", "this_year"]:
        pipeline = [
            {
                "$project": {
                    "id": 1,
                    "first_name": 1,
                    "coins": {
                        "$size": {
                            "$filter": {
                                "input": "$wins",
                                "as": "win",
                                "cond": {"$gte": ["$$win.timestamp", filter_date]}
                            }
                        }
                    }
                }
            },
            {"$sort": {"coins": -1}},
            {"$limit": 10}
        ]

    else:  # All Time
        pipeline = [
            {
                "$project": {
                    "id": 1,
                    "first_name": 1,
                    "coins": {"$size": {"$ifNull": ["$wins", []]}}
                }
            },
            {"$sort": {"coins": -1}},
            {"$limit": 10}
        ]

    leaderboard = await user_collection.aggregate(pipeline).to_list(length=10)

    text = f"<b>🏆 Leaderboard ({FILTERS.get(filter_key, 'All Time')})</b>\n\n"
    for idx, user in enumerate(leaderboard, 1):
        first_name = html.escape(user.get("first_name", "Unknown"))[:15]
        coins = user.get("coins", 0)
        user_id = user.get("id")
        medal = "👑 " if idx == 1 else ""
        text += f"{medal}{idx}. <a href='tg://user?id={user_id}'><b>{first_name}</b></a>: {coins} coins\n"

    if callback_query:
        await callback_query.edit_message_text(
            text, reply_markup=leaderboard_buttons(filter_key), disable_web_page_preview=True
        )
    else:
        await msg.reply_text(
            text, reply_markup=leaderboard_buttons(filter_key), disable_web_page_preview=True
        )
