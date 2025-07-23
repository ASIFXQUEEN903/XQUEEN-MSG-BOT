import os
import logging
from telegram import Update, ChatMember, Message
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")
MONGO_URL = os.getenv("MONGO_URL")

# MongoDB setup
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["xqueen_db"]
users_col = db["users"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global map: message_id to user_id for replies
user_message_map = {}

# Save user to MongoDB
async def save_user(user_id):
    exists = await users_col.find_one({"_id": user_id})
    if not exists:
        await users_col.insert_one({"_id": user_id})

# Get all users from MongoDB
async def get_all_users():
    users = await users_col.find().to_list(length=None)
    return [user["_id"] for user in users]

# Check if user joined FORCE_CHANNEL
async def check_joined(user_id, context):
    try:
        member = await context.bot.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in [ChatMember.MEMBER, ChatMember.OWNER, ChatMember.ADMINISTRATOR]
    except:
        return False

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    joined = await check_joined(user_id, context)
    if not joined:
        await update.message.reply_text(
            f"🚫 You must join {FORCE_CHANNEL} to use this bot.\n\n👉 Join and press /start again."
        )
        return
    await save_user(user_id)
    await update.message.reply_text("✅ Send any message or file. It will be sent to the owner.")

# Handle user messages
async def relay_user_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    joined = await check_joined(user.id, context)
    if not joined:
        await update.message.reply_text(f"⚠️ Join {FORCE_CHANNEL} and press /start.")
        return

    msg: Message = update.message
    header = f"📩 Message from [{user.first_name}](tg://user?id={user.id})"
    header += f"\n🆔 ID: `{user.id}`"
    if user.username:
        header += f"\n👤 Username: @{user.username}"
    header += f"\n\n📝 Message:\n{msg.text or msg.caption or ''}"

    sent_msg = None
    try:
        if msg.text:
            sent_msg = await context.bot.send_message(ADMIN_ID, header, parse_mode="Markdown")
        elif msg.photo:
            sent_msg = await context.bot.send_photo(ADMIN_ID, photo=msg.photo[-1].file_id, caption=header, parse_mode="Markdown")
        elif msg.document:
            sent_msg = await context.bot.send_document(ADMIN_ID, document=msg.document.file_id, caption=header, parse_mode="Markdown")
        elif msg.video:
            sent_msg = await context.bot.send_video(ADMIN_ID, video=msg.video.file_id, caption=header, parse_mode="Markdown")
        elif msg.audio:
            sent_msg = await context.bot.send_audio(ADMIN_ID, audio=msg.audio.file_id, caption=header, parse_mode="Markdown")
        else:
            await context.bot.send_message(ADMIN_ID, header + "\n⚠️ Unsupported content")
    except Exception as e:
        logger.error(f"Relay error: {e}")
        await update.message.reply_text("❌ Failed to send to owner.")
        return

    if sent_msg:
        user_message_map[sent_msg.message_id] = user.id
        await update.message.reply_text("✅ Your message has been sent to the owner.")

# Handle owner's reply
async def handle_owner_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    reply_to = update.message.reply_to_message
    if not reply_to:
        return

    user_id = user_message_map.get(reply_to.message_id)
    if not user_id:
        await update.message.reply_text("⚠️ Could not find user to reply.")
        return

    try:
        msg = update.message
        if msg.text:
            await context.bot.send_message(user_id, f"💬 Reply from owner:\n{msg.text}")
        elif msg.photo:
            await context.bot.send_photo(user_id, photo=msg.photo[-1].file_id, caption=msg.caption or "")
        elif msg.document:
            await context.bot.send_document(user_id, document=msg.document.file_id, caption=msg.caption or "")
        elif msg.video:
            await context.bot.send_video(user_id, video=msg.video.file_id, caption=msg.caption or "")
        elif msg.audio:
            await context.bot.send_audio(user_id, audio=msg.audio.file_id, caption=msg.caption or "")
    except Exception as e:
        logger.error(f"Reply send failed: {e}")
        await update.message.reply_text("❌ Could not send reply to user.")

# /info command
async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👤 Your Info:\n\nID: `{user.id}`\nName: {user.first_name}\nUsername: @{user.username if user.username else 'N/A'}",
        parse_mode="Markdown"
    )

# /broadcast command
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Only owner can broadcast.")
    if not context.args:
        return await update.message.reply_text("❗ Use: `/broadcast your message`", parse_mode="Markdown")

    text = " ".join(context.args)
    users = await get_all_users()
    sent = 0

    for user_id in users:
        try:
            await context.bot.send_message(user_id, text)
            sent += 1
        except:
            continue

    await update.message.reply_text(f"✅ Broadcast sent to {sent} users.")

# Run bot
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", user_info))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.ALL & filters.REPLY, handle_owner_reply))
    app.add_handler(MessageHandler(filters.ALL, relay_user_msg))
    logger.info("Bot started.")
    app.run_polling()

if __name__ == "__main__":
    main()
