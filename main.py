import os
import logging
from telegram import Update, ChatMember
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_joined(user_id, context):
    try:
        member = await context.bot.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in [ChatMember.MEMBER, ChatMember.OWNER, ChatMember.ADMINISTRATOR]
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    joined = await check_joined(user_id, context)
    if not joined:
        await update.message.reply_text(
            f"🚫 You must join {FORCE_CHANNEL} to use this bot.\n\n👉 Join and then press /start again."
        )
        return
    await update.message.reply_text("✅ Send me any message, photo, or file, and I will forward it to my owner!")
    users = context.application.user_data.setdefault("users", set())
    users.add(user_id)

async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    joined = await check_joined(user_id, context)
    if not joined:
        await update.message.reply_text(
            f"⚠️ Join {FORCE_CHANNEL} first.\n\nPress /start after joining."
        )
        return
    if ADMIN_ID:
        try:
            await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
        except Exception as e:
            logger.error(f"Error forwarding: {e}")

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👤 Your Info:\n\nID: `{user.id}`\nName: {user.first_name}\nUsername: @{user.username if user.username else 'N/A'}",
        parse_mode="Markdown"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Only admin can broadcast.")
    if context.args:
        text = " ".join(context.args)
        sent = 0
        for user_id in context.application.user_data.get("users", []):
            try:
                await context.bot.send_message(user_id, text)
                sent += 1
            except:
                continue
        await update.message.reply_text(f"✅ Broadcast sent to {sent} users.")
    else:
        await update.message.reply_text("❗ Use: `/broadcast your message here`", parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", user_info))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.ALL, forward_all))
    logger.info("Bot started.")
    app.run_polling()

if __name__ == "__main__":
    main()
