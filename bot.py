import os
import threading
from collections import defaultdict
from telegram import Update
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
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = -1003838176853
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

daily_scores = defaultdict(int)
active_polls = {}

# =========================
# AI MESSAGE GENERATOR
# =========================

def ai_message(topic):

    prompt = f"""
You are a friendly office wellness assistant in a team chat.

Write a short natural message about:
{topic}

Keep it under 2 sentences.
Friendly tone.
"""

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
    )

    return chat_completion.choices[0].message.content


# =========================
# SEND POLL
# =========================

async def send_poll(app, topic):

    question = ai_message(topic)

    poll = await app.bot.send_poll(
        chat_id=GROUP_ID,
        question=question,
        options=["Yes 👍", "No 👎"],
        is_anonymous=False
    )

    active_polls[poll.poll.id] = poll.message_id


# =========================
# POLL ANSWER HANDLER
# =========================

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):

    answer = update.poll_answer
    user = answer.user.first_name
    option = answer.option_ids[0]

    if option == 0:
        daily_scores[user] += 1
        message = ai_message(f"congratulate {user} for following healthy habit")
    else:
        message = ai_message(f"encourage {user} to take a short refreshment break")

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

    text = update.message.text.lower()
    user = update.message.from_user.first_name

    # 🌞 Good Morning
    if "good morning" in text:
        message = ai_message(f"wish {user} a positive energetic good morning")
        await update.message.reply_text(message)

    # 🏃 Exercise detection
    elif any(word in text for word in ["gym", "exercise", "walk", "yoga"]):
        daily_scores[user] += 2
        message = ai_message(f"praise {user} for doing exercise in the morning")
        await update.message.reply_text(message)

    # 📚 Reading detection
    elif "read" in text:
        daily_scores[user] += 1
        message = ai_message(f"encourage {user} for reading habit")
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

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        send_poll,
        "cron",
        hour=9,
        minute=30,
        args=[app, "ask team if they are ready to start work"]
    )

    scheduler.add_job(
        send_poll,
        "cron",
        hour=13,
        minute=0,
        args=[app, "announce lunch time"]
    )

    scheduler.add_job(
        daily_winner,
        "cron",
        hour=19,
        minute=0,
        args=[app]
    )

    scheduler.start()


# =========================
# MAIN (WINDOWS SAFE)
# =========================

if __name__ == "__main__":

    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    async def start_scheduler(application):
        setup_schedule(application)

    app.post_init = start_scheduler

    print("🌿 Groq Wellness Bot Running")

    app.run_polling(close_loop=False)
