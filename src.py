from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
import asyncpg
import os
import asyncio

# Load env variables
BOT_TOKEN = os.getenv("botToken")
DB_URL = os.getenv("DATABASE_PUBLIC_URL")

# Quiz questions
QUESTIONS = [
    {
        "question": "🐔 What is KEVII's JCRC President's name?\n1️⃣ Butterchicken\n2️⃣ Bhattarchicken\n3️⃣ Bhattacharya\n4️⃣ Bhattarcharya",
        "options": [1, 2, 3, 4],
        "answer": 2
    },
    {
        "question": "🐤 How many chickens are there in KE?\n1️⃣ 5\n2️⃣ 69\n3️⃣ 100\n4️⃣ Too many",
        "options": [1, 2, 3, 4],
        "answer": 3
    },
    {
        "question": "🍗 Do you like eating fried chicken?\n1️⃣ Yes\n2️⃣ No",
        "options": [1, 2],
        "answer": 0
    },
    {
        "question": "👔 Who was the KEWOC VPD? Justin _______\n1️⃣ Chan\n2️⃣ Poh\n3️⃣ Solomon\n4️⃣ Adiyoga",
        "options": [1, 2, 3, 4],
        "answer": 2
    },
    {
        "question": "🇲🇾 Which Malaysian PM stayed in KE?\n1️⃣ Horng Ern\n2️⃣ Kai Jun\n3️⃣ Yu Le\n4️⃣ Zi Jian",
        "options": [1, 2, 3, 4],
        "answer": 0
    },
    {
        "question": "🍱 On which day does the DH serve Cai Fan?\n1️⃣ Monday\n2️⃣ Tuesday\n3️⃣ Friday\n4️⃣ Saturday",
        "options": [1, 2, 3, 4],
        "answer": 1
    },
    {
        "question": "🐒 Which professor researches monkeys near KE?\n1️⃣ Sivasothi N\n2️⃣ Martin Henz\n3️⃣ Sie Min\n4️⃣ Peppe",
        "options": [1, 2, 3, 4],
        "answer": 0
    },
    {
        "question": "🏠 What is the F Block RF's last name?\n1️⃣ Timperio\n2️⃣ Giuseppe\n3️⃣ Esposito\n4️⃣ Guerriero",
        "options": [1, 2, 3, 4],
        "answer": 0
    }
]

# Dictionary to track which question each user is currently on
userProgress = {}

# Database functions
async def initDB():
    conn = await asyncpg.connect(DB_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            userId BIGINT,
            username TEXT,
            score INT,
            attempt INT,
            PRIMARY KEY(userId, attempt)
        )
    """)
    await conn.close()

async def getLatestAttempt(userId):
    conn = await asyncpg.connect(DB_URL)
    row = await conn.fetchrow(
        "SELECT attempt FROM scores WHERE userId=$1 ORDER BY attempt DESC LIMIT 1",
        userId
    )
    await conn.close()
    return row['attempt'] if row else 0

async def createAttempt(userId, username):
    attempt = await getLatestAttempt(userId) + 1
    conn = await asyncpg.connect(DB_URL)
    await conn.execute(
        "INSERT INTO scores(userId, username, score, attempt) VALUES($1, $2, 0, $3)",
        userId, username, attempt
    )
    await conn.close()
    return attempt

async def updateScore(userId, delta):
    attempt = await getLatestAttempt(userId)
    conn = await asyncpg.connect(DB_URL)
    await conn.execute(
        "UPDATE scores SET score = score + $1 WHERE userId=$2 AND attempt=$3",
        delta, userId, attempt
    )
    await conn.close()

async def getScore(userId):
    attempt = await getLatestAttempt(userId)
    conn = await asyncpg.connect(DB_URL)
    row = await conn.fetchrow(
        "SELECT score FROM scores WHERE userId=$1 AND attempt=$2",
        userId, attempt
    )
    await conn.close()
    return row["score"] if row else 0

# /start
async def start(update, context):
    userId = update.effective_user.id
    username = update.effective_user.username

    # Start at first ques
    userProgress[userId] = 0
    await update.message.reply_text("🎯 Welcome to the KEVII Quiz! Type /leaderboard to view the top players 🏆")

    # Create a new attempt row in the database
    await createAttempt(userId, username)

    # Send the first question
    await sendQuestion(update.message, update.effective_user)

# Helper function to send questions
async def sendQuestion(message, user):
    userId = user.id
    quesIndex = userProgress[userId]

    # Checks if user has finished all questions
    if quesIndex >= len(QUESTIONS):
        finalScore = await getScore(userId)
        await message.reply_text(f"🎉 Quiz complete! You scored 🏅 {finalScore}/{len(QUESTIONS)}")
        return

    question = QUESTIONS[quesIndex]

    # Create buttons for inline keyboard
    buttons = []
    for index, description in enumerate(question["options"]):
        buttons.append(InlineKeyboardButton(description, callback_data=str(index)))

    await message.reply_text(
        f"Q{quesIndex + 1}: {question['question']}",
        reply_markup=InlineKeyboardMarkup([buttons])
    )

# Helper function to process answers
async def processAnswer(update, context):
    query = update.callback_query
    await query.answer()

    userId = query.from_user.id
    quesIndex = userProgress[userId]
    question = QUESTIONS[quesIndex]

    # Check if answer is correct
    userAnswer = int(query.data)
    if userAnswer == question["answer"]:
        await updateScore(userId, 1)

    # Move to the next question
    userProgress[userId] += 1
    if userProgress[userId] < len(QUESTIONS):
        await query.message.reply_text("👉 Next question:")

    # Send next question or completion message
    await sendQuestion(query.message, query.from_user)

# Handler function to show top 5 users, sorts by descending score then by ascending attempt
async def leaderboard(update, context):
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch(
        "SELECT username, score, attempt FROM scores ORDER BY score DESC, attempt ASC LIMIT 5"
    )
    await conn.close()

    text = "🏆 *Top KEVIIANS Leaderboard* 🏆\n"
    for i, row in enumerate(rows, start=1):
        text += f"{i}. @{row['username']} Score: {row['score']} Attempt: {row['attempt']}\n"
    await update.message.reply_text(text)

async def setup():
    if not DB_URL:
        raise RuntimeError("Environment var is missing")
    await initDB()

if __name__ == "__main__":
    import asyncio

    asyncio.run(setup())

    bot = ApplicationBuilder().token(BOT_TOKEN).build()

    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("leaderboard", leaderboard))
    bot.add_handler(CallbackQueryHandler(processAnswer))

    bot.run_polling()
