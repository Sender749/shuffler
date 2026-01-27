from pyrogram import Client, filters
from pyrogram.types import *
from vars import *
from Database.maindb import mdb
from Database.userdb import udb
from datetime import datetime
import pytz, random, asyncio
from .fsub import get_fsub
from Script import text

async def get_updated_limits():
        global FREE_LIMIT, PRIME_LIMIT
        limits = await mdb.get_global_limits()
        FREE_LIMIT = limits["free_limit"]
        PRIME_LIMIT = limits["prime_limit"]
        return limits

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    if await udb.is_user_banned(message.from_user.id):
        await message.reply("**🚫 You are banned from using this bot**",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Support 🧑‍💻", url=f"https://t.me/{ADMIN_USERNAME}")]]))
        return
    if IS_FSUB and not await get_fsub(client, message):return
    if await udb.get_user(message.from_user.id) is None:
        await udb.addUser(message.from_user.id, message.from_user.first_name)
        bot = await client.get_me()
        await client.send_message(
            LOG_CHNL,
            text.LOG.format(
                message.from_user.id,
                getattr(message.from_user, "dc_id", "N/A"),
                message.from_user.first_name or "N/A",
                f"@{message.from_user.username}" if message.from_user.username else "N/A",
                bot.username
            )
        )
    await message.reply_photo(
        photo=random.choice(PICS),
        caption=text.START.format(message.from_user.mention),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎥 Get More Videos", callback_data="getvideos_cb")],
            [InlineKeyboardButton("🍿 𝖡𝗎𝗒 𝖲𝗎𝖻𝗌𝖼𝗋𝗂𝗉𝗍𝗂𝗈𝗇 🍾", callback_data="pro")],
            [InlineKeyboardButton("ℹ️ 𝖠𝖻𝗈𝗎𝗍", callback_data="about"),
             InlineKeyboardButton("📚 𝖧𝖾𝗅𝗉", callback_data="help")] 
        ])
    )

async def send_random_video_logic(client: Client, user, chat_id, reply_func):
    limits = await get_updated_limits()
    if limits.get('maintenance', False):
        await reply_func("**🛠️ Bot Under Maintenance — Back Soon!**")
        return
    user_id = user.id
    db_user = await mdb.get_user(user_id)
    plan = db_user.get("plan", "free")
    if plan == "prime":
        videos = await mdb.get_all_videos()
    else:
        videos = await mdb.get_free_videos()

    if not videos:
        await reply_func("No videos available at the moment.")
        return
    random_video = random.choice(videos)
    daily_count = db_user.get("daily_count", 0)
    daily_limit = db_user.get("daily_limit", FREE_LIMIT)
    if daily_count > daily_limit:
        await reply_func(
            f"**🚫 You've reached your daily limit of {daily_limit} videos.\n\n"
            f">Limit will reset every day at 5 AM (IST).**"
        )
        return
    try:
        caption_text = ("<b><blockquote>⚠️ This file will auto delete in 5 minutes!</blockquote></b>\n\n")
        dy = await client.copy_message(
                chat_id=chat_id,
                from_chat_id=DATABASE_CHANNEL_ID,
                message_id=random_video["video_id"],
                caption=caption_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Again", callback_data="getvideos_cb")]]))
        await mdb.increment_daily_count(user_id)
        await asyncio.sleep(300)
        await dy.delete()
    except Exception as e:
        print(f"Error sending video: {e}")
        await reply_func("Failed to send video..")

@Client.on_message(filters.command("getvideos") & filters.private)
async def send_random_video(client: Client, message: Message):
    if await udb.is_user_banned(message.from_user.id):
        await message.reply(
            "**🚫 You are banned from using this bot**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Support 🧑‍💻", url=f"https://t.me/{ADMIN_USERNAME}")]]))
        return
    if IS_FSUB and not await get_fsub(client, message):
        return
    await send_random_video_logic(
        client=client,
        user=message.from_user,
        chat_id=message.chat.id,
        reply_func=message.reply_text
    )

@Client.on_message(filters.command("index") & filters.private)
async def index_cmd(client: Client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await mdb.set_index_state(message.from_user.id, {
        "step": "await_channel"
    })
    await message.reply_text(
        "📥 **Index Mode Started**\n\n"
        "➡️ Send **last message from the indexing channel with tag**",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")]]))

@Client.on_message(filters.private)
async def index_flow_handler(client: Client, message: Message):
    state = await mdb.get_index_state(message.from_user.id)
    if not state:
        return
    if isinstance(DATABASE_CHANNEL_ID, int):
        allowed_channels = {DATABASE_CHANNEL_ID}
    else:
        allowed_channels = set(DATABASE_CHANNEL_ID)
    if state["step"] == "await_channel":
        channel = None
        if message.forward_origin and message.forward_origin.chat:
            channel = message.forward_origin.chat
        elif message.sender_chat:
            channel = message.sender_chat
        if not channel:
            await message.reply_text(
                "❌ Please forward or send a message **from the channel**."
            )
            return
        channel_id = channel.id
        if channel_id not in allowed_channels:
            await message.reply_text("❌ This channel is not allowed for indexing.")
            return
        try:
            bot_id = (await client.get_me()).id
            member = await client.get_chat_member(channel_id, bot_id)
            if member.status not in ("administrator", "owner"):
                await message.reply_text("❌ Bot is not admin in this channel.")
                return
        except Exception:
            await message.reply_text("❌ Failed to verify bot permissions.")
            return
        await mdb.set_index_state(message.from_user.id, {
            "step": "await_skip",
            "channel_id": channel_id
        })
        await message.delete()
        await client.send_message(
            message.chat.id,
            "📌 **Send skip value**\n\n"
            "• `0` → index all files\n"
            "• message link\n"
            "• message id",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")]
            ])
        )
        return
    if state["step"] == "await_skip":
        channel_id = state["channel_id"]
        try:
            if message.text == "0":
                start_id = 0
            elif message.text and "t.me" in message.text:
                start_id = int(message.text.rsplit("/", 1)[-1])
            elif message.text:
                start_id = int(message.text)
            else:
                raise ValueError
        except Exception:
            await message.reply_text(
                "❌ Invalid input.\n\nSend `0`, message link, or message id."
            )
            return
        await message.delete()
        await mdb.set_index_state(message.from_user.id, {
            "step": "indexing",
            "channel_id": channel_id,
            "start_id": start_id,
            "cancel": False
        })
        await client.send_message(
            message.chat.id,
            "⏳ **Indexing started...**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel Indexing", callback_data="cancel_index")]
            ])
        )
        await start_indexing(client, message.from_user.id)

async def start_indexing(client: Client, admin_id: int):
    state = await mdb.get_index_state(admin_id)
    channel_id = state["channel_id"]
    start_id = state["start_id"]
    indexed = duplicate = skipped = 0
    async for msg in client.iter_history(channel_id):
        if start_id and msg.id <= start_id:
            break
        state = await mdb.get_index_state(admin_id)
        if not state or state.get("cancel"):
            break
        if not msg.video and not msg.document:
            skipped += 1
            continue
        if await mdb.video_exists(msg.id):
            duplicate += 1
            continue
        await mdb.add_video({
            "video_id": msg.id,
            "chat_id": channel_id
        })
        indexed += 1
    await mdb.clear_index_state(admin_id)
    await client.send_message(
        admin_id,
        f"✅ **Indexing Completed**\n\n"
        f"📥 Indexed: `{indexed}`\n"
        f"♻️ Duplicates: `{duplicate}`\n"
        f"⏭ Skipped: `{skipped}`"
    )









