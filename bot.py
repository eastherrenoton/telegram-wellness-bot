import os
import threading
import random
from datetime import datetime
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

Write a short encouraging message about:
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
# EMOJI REACTION
# =========================

async def react_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    emojis = ["🎉","👏","🔥","💪","🥳","✨"]

    await context.bot.set_message_reaction(
        chat_id=update.effective_chat.id,
        message_id=update.message.message_id,
        reaction=[ReactionTypeEmoji(random.choice(emojis))]
    )
# =========================
# SEND NORMAL POLL
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
            "🏋️ Gym / Workout",
            "🚶 Walk / Exercise",
            "🧘 Yoga / Meditation",
            "📖 Reading",
            "💧 Drank Water",
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
        question="☕ Time for a quick 5 minute break. Are you stepping away from the screen?",
        options=[
            "✅ Yes, taking a break",
            "💻 Still working"
        ],
        is_anonymous=False
    )

    active_polls[poll.poll.id] = "morning break"

# =========================
# WATER REMINDER
# =========================

async def water_reminder(app):

    message = ai_message("remind the team to drink water and stay hydrated")

    await app.bot.send_message(
        chat_id=GROUP_ID,
        text=f"💧 {message}"
    )

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
        message = ai_message(f"congratulate {user} for completing {topic}")
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

        message = ai_message(f"wish {user} a positive energetic good morning")

        await update.message.reply_text(message)

    elif any(word in text for word in [
        "gym","workout","exercise","training","fitness","bodybuilding","cardio","running","jogging","sprint",
"walk","walking","steps","cycling","biking","yoga","stretch","stretching","meditation","meditate",
"mindfulness","breathing","pranayama","pilates","aerobics","dance","zumba","sports","badminton",
"football","cricket","tennis","swimming","hiking","climbing","pushups","pushup","squats","plank",
"deadlift","benchpress","lifting","weights","strength","core","abs","fitnessroutine","trainingday",
"morningrun","eveningrun","trailrun","intervaltraining","strengthtraining","mobility","mobilitywork",
"resistance","calisthenics","ropejump","skipping","mountainclimber","lunges","burpees","legday",
"upperbody","lowerbody","hiit","fitnessgoal","fitnessjourney",

# Wellness & Mind
"meditationpractice","breathwork","mindtraining","selfreflection","gratitude","gratitudepractice",
"journaling","mindset","positivethinking","selfawareness","mindclarity","focuspractice",
"mindfulnesspractice","deepbreathing","calmness","peacefulmind","mentalwellness","selfgrowth",
"personaldevelopment","emotionalbalance","innerpeace","focuswork","disciplinepractice",

# Reading & Learning
"read","reading","book","books","study","studying","learning","knowledge","selflearning","research",
"ebook","audiobook","journal","writing","notes","notetaking","revision","practice","skill","skills",
"onlinecourse","courselearning","languagelearning","englishpractice","vocabulary","readinghabit",
"writinghabit","learninghabit","studysession","knowledgegain","education","braintraining","thinking",

# Hydration & Health
"water","hydration","drinkwater","hydrate","waterintake","stayhydrated","drinkmorewater",
"waterbreak","hydrationbreak","watergoal","drinkwaternow","hydrationcheck","healthwater",

# Healthy Lifestyle
"earlywake","earlymorning","sunrise","morningroutine","eveningroutine","selfcare","wellness",
"mentalhealth","positivity","positiveenergy","motivation","inspiration","energyboost","freshstart",
"selfdiscipline","productivity","planning","goalsetting","goaltracking","habittracking","routine",

# Nature & Fresh Air
"sunlight","freshair","nature","naturewalk","gardenwalk","terracewalk","morningwalk","eveningwalk",
"parkwalk","sunbathing","grounding","outdoorwalk","freshbreeze","openair","greenery","naturetime",

# Work & Focus
"deepwork","timemanagement","planningday","reviewday","weeklyreview","organizing","declutter",
"minimalism","cleanworkspace","focusmode","productivework","taskplanning","goalreview",

# Creativity
"drawing","painting","creativework","artpractice","designpractice","musicpractice","instrumentpractice",
"writingpractice","creativewriting","sketching","illustration","digitalart","artlearning",

# Brain Exercise
"puzzle","crossword","brainexercise","logictraining","memorytraining","thinkingpractice",
"mentalexercise","brainworkout","focusgame","problem-solving","strategythinking",

# Personal Growth
"confidence","growthmindset","selfimprovement","personalgrowth","learningdaily","practicehabit",
"skillbuilding","disciplinebuilding","progress","consistency","dailyimprovement","habitpractice",

# Healthy Habits Actions
"gymdone","workoutdone","rundone","walkdone","readdone","yogadone","meditated","hydrated",
"studydone","stretchdone","trainingdone","fitnessdone","habitdone","practicecompleted",

# Mobility & Recovery
"stretchroutine","mobilityroutine","cooldown","warmup","bodymovement","activebreak",
"recoveryexercise","recoveryroutine","musclestretch","jointmobility","flexibility",

# Productivity
"planningroutine","morningplanning","taskreview","goalreview","dailyreview","selfevaluation",
"progresscheck","habitreview","timeaudit","workfocus","productivehours","workdiscipline",

# Community & Kindness
"kindness","helping","support","community","teamwork","encouragement","mentoring","sharingknowledge",
"guidance","collaboration","volunteer","charity","service",

# Calm Activities
"silencetime","quiettime","reflectiontime","thinkingtime","peacefulmoment","slowbreathing",
"mindreset","energyreset","mentalbreak","claritytime","awarenesspractice"
    ]):

        daily_scores[user] += 2

        message = ai_message(
            f"{user} shared this message about a healthy activity: {update.message.text}. Praise them."
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

    # 9:30 Work start
    scheduler.add_job(
        send_poll,
        "cron",
        hour=9,
        minute=30,
        args=[app, "ask team if they are ready to start work"]
    )

    # 10:30 Habit poll
    scheduler.add_job(
        send_habit_poll,
        "cron",
        hour=10,
        minute=30,
        args=[app]
    )

    # 10:31 Break poll
    scheduler.add_job(
        send_break_poll,
        "cron",
        hour=10,
        minute=31,
        args=[app]
    )

    # 11:30 Break reminder
    scheduler.add_job(
        send_poll,
        "cron",
        hour=11,
        minute=30,
        args=[app, "remind team to take a 15 minute break"]
    )

    # 1:00 Lunch poll
    scheduler.add_job(
        send_poll,
        "cron",
        hour=13,
        minute=0,
        args=[app, "announce lunch time"]
    )

    # 5:00 Stretch break
    scheduler.add_job(
        send_poll,
        "cron",
        hour=17,
        minute=0,
        args=[app, "time for a quick stretch break"]
    )

    # 7:00 Daily summary
    scheduler.add_job(
        daily_winner,
        "cron",
        hour=19,
        minute=0,
        args=[app]
    )

    # Hourly water reminder starting 10:40
    scheduler.add_job(
        water_reminder,
        "interval",
        hours=1,
        start_date=datetime.now(pytz.timezone("Asia/Kolkata")).replace(hour=10, minute=40, second=0),
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

    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    async def start_scheduler(application):
        setup_schedule(application)

    app.post_init = start_scheduler

    print("🌿 Groq Wellness Bot Running")

    app.run_polling(close_loop=False)
