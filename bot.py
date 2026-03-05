import os
import threading
from collections import defaultdict
from flask import Flask

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
# DATA STORAGE
# =========================

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

    return chat_completion.choices[0].message.content.strip()

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

    if "good morning" in text:

        message = ai_message(f"wish {user} a positive energetic good morning")

        await update.message.reply_text(message)

    elif any(word in text for word in ["gym","workout","exercise","training","fitness","bodybuilding","cardio","running","jogging","sprint",
"walk","walking","steps","cycling","biking","yoga","stretch","stretching","meditation","meditate",
"mindfulness","breathing","pranayama","pilates","aerobics","dance","zumba","sports","badminton",
"football","cricket","tennis","swimming","hiking","climbing","pushups","pushup","squats","plank",
"deadlift","benchpress","lifting","weights","strength","core","abs","fitnessroutine","trainingday",

"read","reading","book","books","study","studying","learning","knowledge","selflearning","research",
"ebook","audiobook","journal","writing","notes","notetaking","revision","practice","skill","skills",

"water","hydration","drinkwater","hydrate","tea","greentea","herbaltea","healthyfood","nutrition",
"protein","vitamins","fruits","vegetables","salad","diet","balanceddiet","mealprep","breakfast",
"healthybreakfast","lunch","dinner","snacks","smoothie",

"sleep","goodsleep","earlysleep","rest","recovery","nap","relax","relaxing","calm","peace","focus",
"productivity","planning","goals","goalsetting","journaling","gratitude","reflection","discipline",

"morningroutine","eveningroutine","selfcare","wellness","mentalhealth","positivity","positive",
"motivation","inspiration","energy","freshstart","success","growth","habit","habits","routine",

"sunlight","freshair","nature","gardening","cleaning","organizing","declutter","minimalism",

"brainexercise","puzzle","readinghabit","writinghabit","coding","practicecoding","designpractice",

"languagelearning","englishpractice","vocabulary","speakingpractice",

"musicpractice","drawing","painting","creativework","artpractice",

"budgeting","financelearning","investing","saving","moneyplanning",

"charity","helping","kindness","volunteer","community","teamwork",

"mindset","selfimprovement","personaldevelopment","confidence","focuswork",

"deepwork","timemanagement","planningday","reviewday","weeklyreview",

"breathwork","coldshower","sunrisewalk","eveningwalk","naturewalk",

"gymdone","workoutdone","rundone","walkdone","readdone","yogadone","meditated","hydrated"]):

        daily_scores[user] += 2

        message = ai_message(f"praise {user} for doing exercise in the morning")

        await update.message.reply_text(message)

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

    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

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
# RENDER WEB SERVER
# =========================

web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Telegram Wellness Bot Running 🌿"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# =========================
# MAIN
# =========================

if __name__ == "__main__":

    # start web server for render
    threading.Thread(target=run_web).start()

    # telegram bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    async def start_scheduler(application):
        setup_schedule(application)

    app.post_init = start_scheduler

    print("🌿 Groq Wellness Bot Running")

    app.run_polling(close_loop=False)
