import os
import logging
from telegram import Update, ChatMember, Message
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

# Check if user joined force channel
async def check_joined(user_id, context):
    try:
        member = await context.bot.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in [ChatMember.MEMBER, ChatMember.OWNER, ChatMember.ADMINISTRATOR]
    except:
        return False

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    joined = await check_joined(user_id, context)
    if not joined:
        await update.message.reply_text(
            f"🚫 You must join {FORCE_CHANNEL} to use this bot.\n\n👉 Join and then press /start again."
        )
        return
    await update.message.reply_text("✅ Send me any message, photo, or file.\nYour message will be sent to the bot owner.")
    users = context.application.user_data.setdefault("users", set())
    users.add(user_id)

# Handle user messages and relay to owner
async def relay_user_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    joined = await check_joined(user.id, context)
    if not joined:
        await update.message.reply_text(
            f"⚠️ Please join {FORCE_CHANNEL} and try again."
        )
        return

    # Format header
    header = f"📩 Message from [{user.first_name}](tg://user?id={user.id})"
    header += f"\n🆔 ID: `{user.id}`"
    if user.username:
        header += f"\n👤 Username: @{user.username}"
    header += "\n\n📝 Message:\n"

    # Send message or media with header
    msg: Message = update.message
    sent_msg = None
    try:
        if msg.text:
            sent_msg = await context.bot.send_message(ADMIN_ID, header + msg.text, parse_mode="Markdown")
        elif msg.photo:
            sent_msg = await context.bot.send_photo(ADMIN_ID, photo=msg.photo[-1].file_id, caption=header + (msg.caption or ""), parse_mode="Markdown")
        elif msg.document:
            sent_msg = await context.bot.send_document(ADMIN_ID, document=msg.document.file_id, caption=header + (msg.caption or ""), parse_mode="Markdown")
        elif msg.video:
            sent_msg = await context.bot.send_video(ADMIN_ID, video=msg.video.file_id, caption=header + (msg.caption or ""), parse_mode="Markdown")
        elif msg.audio:
            sent_msg = await context.bot.send_audio(ADMIN_ID, audio=msg.audio.file_id, caption=header + (msg.caption or ""), parse_mode="Markdown")
        else:
            await context.bot.send_message(ADMIN_ID, header + "📎 [Unsupported content]")
    except Exception as e:
        logger.error(f"Relay error: {e}")
        await update.message.reply_text("❌ Failed to send message to owner.")
        return

    # Save mapping to reply back later
    if sent_msg:
        context.application.chat_data[sent_msg.message_id] = user.id
        await update.message.reply_text("✅ Your message has been sent to the owner.")

# Owner reply — sends message back to original user
async def handle_owner_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return  # ignore if not owner

    reply_to = update.message.reply_to_message
    if not reply_to:
        return

    user_id = context.application.chat_data.get(reply_to.message_id)
    if not user_id:
        await update.message.reply_text("⚠️ Cannot find user to reply.")
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
        logger.error(f"Failed to reply to user: {e}")
        await update.message.reply_text("❌ Failed to send reply.")

# /info command
async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👤 Your Info:\n\nID: `{user.id}`\nName: {user.first_name}\nUsername: @{user.username if user.username else 'N/A'}",
        parse_mode="Markdown"
    )

# /broadcast by admin
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

# Main function
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
