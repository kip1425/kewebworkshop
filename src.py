from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from dotenv import load_dotenv
import os
import aiosqlite
import asyncio

# Load bot token from .env file
load_dotenv()
BOT_TOKEN = os.getenv("botToken")

# Questions for quiz
QUESTIONS = [
    {
        "question": "What is KEVII's JCRC President's name?",
        "options": ["Arko Butterchicken", "Arko Bhattarchicken", "Arko Bhattacharya", "Arko Bhattarcharya"],
        "answer": 2
    },
    {
        "question": "How many chickens are there in KE?",
        "options": ["5", "69", "100", "Too many"],
        "answer": 3
    },
    {
        "question": "Do you like eating fried chicken?",
        "options": ["Yes", "No"],
        "answer": 0
    }
]

# Dictionary to track which question user is on
userProgress = {}

# Database path
DB_PATH = "database.db"

# Function to initialise database
async def initDB():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                userId INTEGER,
                username TEXT,
                score INTEGER,
                attempt INTEGER,
                PRIMARY KEY(userId, attempt)
            )
        """)
        await db.commit()

# Helper function to update database
async def updateDB(userId, username, delta):
    async with aiosqlite.connect(DB_PATH) as db:
        select = await db.execute(f"SELECT MAX(attempt) FROM scores WHERE userId = {userId}")
        attempt = await select.fetchone()

        # Checks if row exists before updating db
        if attempt[0] is not None:
            await db.execute(f"UPDATE scores SET score = score + {delta} WHERE userId = {userId} AND attempt = {attempt[0]}")
        await db.commit()

# /start
async def start(update, context):
    userId = update.effective_user.id
    username = update.effective_user.username
    userProgress[userId] = 0
    await update.message.reply_text("Type /leaderboard to view leaderboard!")

    async with aiosqlite.connect(DB_PATH) as db:
        select = await db.execute(f"SELECT MAX(attempt) FROM scores WHERE userId = {userId}")
        attempt = await select.fetchone()
        newAttempt = 0

        # Checks if row exists before updating db
        if attempt[0] is not None:
            # /start creates a row with a new attempt if user already exists in db
            newAttempt = attempt[0] + 1
        await db.execute(f"INSERT INTO scores VALUES({userId}, '{username}', 0, {newAttempt})")
        await db.commit()
    await sendQuestion(update.message, update.effective_user)

# Helper function to send questions
async def sendQuestion(message, user):
    userId = user.id
    quesIndex = userProgress[userId]

    # Checks if user has finished the questions, sends a completion message if true
    if quesIndex >= len(QUESTIONS):
        async with aiosqlite.connect(DB_PATH) as db:
            select = await db.execute(f"SELECT score FROM scores WHERE userId = {userId} GROUP BY userId HAVING attempt = MAX(attempt)")
            score = await select.fetchone()
            finalScore = score[0] if score else 0
        await message.reply_text(f"🎉 Quiz complete! You scored {finalScore}/{len(QUESTIONS)}")
        return
    
    question = QUESTIONS[quesIndex]

    # Creates list of buttons for the inline keyboard
    buttons = []
    for index, description in enumerate(question["options"]):
        buttons.append(InlineKeyboardButton(description, callback_data=str(index)))

    await message.reply_text(
        f"Q{quesIndex + 1}: {question["question"]}",
        reply_markup=InlineKeyboardMarkup([buttons])
    )

# Handler to process answers
async def processAnswer(update, context):
    query = update.callback_query
    await query.answer()

    userId = query.from_user.id
    quesIndex = userProgress[userId]
    question = QUESTIONS[quesIndex]

    # Checks if answer is correct
    userAnswer = int(query.data)
    if userAnswer == question["answer"]:
        await updateDB(userId, query.from_user.username, 1)
        response = "Correct!"
    else:
        response = "Wrong!"

    await query.message.reply_text(response)

    # Updates which question user is on
    userProgress[userId] += 1

    # Only sends "Next question:" if not at last question
    if (userProgress[userId] < len(QUESTIONS)):
        await query.message.reply_text("Next question:")
    await sendQuestion(query.message, query.from_user)

# /leaderboard
async def leaderboard(update, context):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT username, score, attempt FROM scores 
            ORDER BY score DESC, attempt ASC
            LIMIT 5""")
        rows = await cursor.fetchall()
        
    text = "Top KEVIIANS:\n"
    for placing, (username, score, attempt) in enumerate(rows, start=1):
        text += f"{placing}. @{username} Score: {score} Attempt: {attempt}\n"
    await update.message.reply_text(text)

def main():
    # Initialise database
    asyncio.get_event_loop().run_until_complete(initDB())

    # Connect handlers to functions
    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("leaderboard", leaderboard))
    bot.add_handler(CallbackQueryHandler(processAnswer))

    # Run bot
    bot.run_polling()

if __name__ == "__main__":
    main()