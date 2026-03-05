import os
import threading
import random
import asyncio
from collections import defaultdict
from flask import Flask
import pytz

from telegram import Update, ReactionTypeEmoji
from telegram.ext import (
    ApplicationBuilder,
    PollAnswerHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from groq import Groq


# =========================
# ENV VARIABLES
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROUP_ID = -5122290062

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found")


# =========================
# GROQ CLIENT
# =========================

client = Groq(api_key=GROQ_API_KEY)


# =========================
# STORAGE
# =========================

daily_scores = defaultdict(int)
active_polls = {}


# =========================
# AI MESSAGE GENERATOR
# =========================

def ai_message(topic):

    prompt = f"""
You are a friendly office wellness assistant.

Write a short encouraging message about:
{topic}

Maximum 2 sentences.
"""

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
    )

    return chat_completion.choices[0].message.content.strip()


# =========================
# EMOJI REACTION
# =========================

async def react_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    emojis = ["🎉","👏","🔥","💪","🥳","✨","🙌"]

    await context.bot.set_message_reaction(
        chat_id=update.effective_chat.id,
        message_id=update.message.message_id,
        reaction=[ReactionTypeEmoji(random.choice(emojis))]
    )


# =========================
# NORMAL POLL
# =========================

async def send_poll(app, topic):

    question = ai_message(topic)

    poll = await app.bot.send_poll(
        chat_id=GROUP_ID,
        question=question,
        options=["Yes 👍", "No 👎"],
        is_anonymous=False
    )

    active_polls[poll.poll.id] = topic


# =========================
# MORNING HABIT POLL
# =========================

async def send_habit_poll(app):

    poll = await app.bot.send_poll(
        chat_id=GROUP_ID,
        question="🌞 What healthy habit did you complete this morning?",
        options=[
            "🏋️ Gym",
            "🚶 Walk",
            "🧘 Yoga",
            "📖 Reading",
            "💧 Water",
            "🌿 Fresh Air",
            "😅 Not Yet"
        ],
        is_anonymous=False
    )

    active_polls[poll.poll.id] = "morning habit"


# =========================
# BREAK POLL
# =========================

async def send_break_poll(app):

    poll = await app.bot.send_poll(
        chat_id=GROUP_ID,
        question="☕ Time for a quick 5 minute break. Taking it?",
        options=[
            "✅ Yes",
            "💻 Still working"
        ],
        is_anonymous=False
    )

    active_polls[poll.poll.id] = "break"


# =========================
# WATER REMINDER
# =========================

async def water_reminder(app):

    msg = ai_message("remind everyone to drink water")

    await app.bot.send_message(
        chat_id=GROUP_ID,
        text=f"💧 {msg}"
    )


# =========================
# HEARTBEAT EVERY 5 MIN
# =========================

async def heartbeat(app):

    msg = await app.bot.send_message(
        chat_id=GROUP_ID,
        text="💧 Stay hydrated guys ❤️"
    )

    await asyncio.sleep(10)

    try:
        await app.bot.delete_message(
            chat_id=GROUP_ID,
            message_id=msg.message_id
        )
    except:
        pass


# =========================
# POLL ANSWER HANDLER
# =========================

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):

    answer = update.poll_answer
    user = answer.user.first_name
    option = answer.option_ids[0]

    topic = active_polls.get(answer.poll_id, "a healthy habit")

    if option == 0:
        daily_scores[user] += 1
        message = ai_message(f"congratulate {user} for doing {topic}")
    else:
        message = ai_message(f"encourage {user} to try {topic} later")

    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=message
    )


# =========================
# MESSAGE HANDLER
# =========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.text:
        return

    await react_to_message(update, context)

    text = update.message.text.lower()
    user = update.message.from_user.first_name

    if "good morning" in text:

        message = ai_message(f"wish {user} a positive good morning")

        await update.message.reply_text(message)

    elif any(word in text for word in [
        "gym","workout","exercise","walk","running",
        "yoga","meditation","read","reading",
        "book","water","hydrate"
    ]):

        daily_scores[user] += 2

        message = ai_message(
            f"{user} shared this healthy habit: {update.message.text}. Praise them."
        )

        await update.message.reply_text(message)


# =========================
# DAILY WINNER
# =========================

async def daily_winner(app):

    if not daily_scores:
        return

    best = max(daily_scores, key=daily_scores.get)

    message = ai_message(f"announce {best} as today's wellness champion")

    await app.bot.send_message(
        chat_id=GROUP_ID,
        text=f"🏆 {message}"
    )

    daily_scores.clear()


# =========================
# SCHEDULER
# =========================

def setup_schedule(app):

    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

    scheduler.add_job(send_poll,"cron",hour=9,minute=30,
        args=[app,"ask team if they are ready to start work"])

    scheduler.add_job(send_habit_poll,"cron",hour=10,minute=30,args=[app])

    scheduler.add_job(send_break_poll,"cron",hour=10,minute=31,args=[app])

    scheduler.add_job(send_poll,"cron",hour=11,minute=30,
        args=[app,"remind team to take a 15 minute break"])

    scheduler.add_job(send_poll,"cron",hour=13,minute=0,
        args=[app,"announce lunch time"])

    scheduler.add_job(send_poll,"cron",hour=17,minute=0,
        args=[app,"time for a quick stretch break"])

    scheduler.add_job(daily_winner,"cron",hour=19,minute=0,args=[app])

    # hourly water reminder
    scheduler.add_job(water_reminder,"interval",hours=1,args=[app])

    # keep render alive every 5 minutes
    scheduler.add_job(heartbeat,"interval",minutes=5,args=[app])

    scheduler.start()


# =========================
# RENDER WEB SERVER
# =========================

web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Telegram Wellness Bot Running"


def run_web():
    port = int(os.environ.get("PORT",10000))
    web_app.run(host="0.0.0.0",port=port)


# =========================
# MAIN
# =========================

if __name__ == "__main__":

    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    async def start_scheduler(application):
        setup_schedule(application)

    app.post_init = start_scheduler

    print("🌿 Wellness Bot Running")

    app.run_polling(close_loop=False, drop_pending_updates=True)
