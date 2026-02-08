from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import Client, filters
from Script import text
from vars import ADMIN_ID
from Database.maindb import mdb
from Database.userdb import udb
from TechifyBots.cmds import send_random_video_logic, VIDEO_MSG_CACHE
from TechifyBots.fsub import get_fsub
from vars import IS_FSUB

# Use a filter to exclude index-related callbacks - this ensures index.py handlers run first
@Client.on_callback_query(~filters.regex(r"^idx_"))
async def callback_query_handler(client, query: CallbackQuery):
    
    try:
        if query.data == "start":
            await query.message.edit_caption(
                caption=text.START.format(query.from_user.mention),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🍿 𝖡𝗎𝗒 𝖲𝗎𝖻𝗌𝖼𝗋𝗂𝗉𝗍𝗂𝗈𝗇 🍾", callback_data="pro")],
                    [InlineKeyboardButton("ℹ️ 𝖠𝖻𝗈𝗎𝗍", callback_data="about"),
                     InlineKeyboardButton("📚 𝖧𝖾𝗅𝗉", callback_data="help")]
                ])
            )

        elif query.data == "help":
            await query.message.edit_caption(
                caption=text.HELP,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 𝖠𝖽𝗆𝗂𝗇 𝖢𝗈𝗆𝗆𝖺𝗇𝖽𝗌", callback_data="admincmds")],
                    [InlineKeyboardButton("↩️ 𝖡𝖺𝖼𝗄", callback_data="start"),
                     InlineKeyboardButton("❌ 𝖢𝗅𝗈𝗌𝖾", callback_data="close")]
                ])
            )

        elif query.data == "about":
            await query.message.edit_caption(
                caption=text.ABOUT,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👨‍💻 𝖣𝖾𝗏𝖾𝗅𝗈𝗉𝖾𝗋 👨‍💻", user_id=int(ADMIN_ID))],
                    [InlineKeyboardButton("↩️ 𝖡𝖺𝖼𝗄", callback_data="start"),
                     InlineKeyboardButton("❌ 𝖢𝗅𝗈𝗌𝖾", callback_data="close")]
                ])
            )

        elif query.data == "pro":
            current_limits = await mdb.get_global_limits()
            pro_text = text.PRO.format(free_limit=current_limits['free_limit'], prime_limit=current_limits['prime_limit'])
            await query.message.edit_caption(
                caption=pro_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 𝖴𝗉𝗀𝗋𝖺𝖽𝖾 / 𝖯𝖺𝗒𝗆𝖾𝗇𝗍", user_id=int(ADMIN_ID))],
                    [InlineKeyboardButton("↩️ 𝖡𝖺𝖼𝗄", callback_data="start"),
                     InlineKeyboardButton("❌ 𝖢𝗅𝗈𝗌𝖾", callback_data="close")]
                ])
            )

        elif query.data == "admincmds":
            if query.from_user.id != ADMIN_ID:
                await query.answer("You are not my admin ❌", show_alert=True)
            else:
                await query.message.edit_caption(
                    caption=text.ADMIN_COMMANDS,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("↩️ 𝖡𝖺𝖼𝗄", callback_data="help")]
                    ])
                )

        elif query.data == "close":
            await query.message.delete()

        elif query.data == "getvideos_cb":
            if await udb.is_user_banned(query.from_user.id):
                await query.answer("🚫 You are banned from using this bot", show_alert=True)
                return
            if IS_FSUB and not await get_fsub(client, query.message):
                return
            
            await query.answer("🎬 Fetching video...", show_alert=False)
            
            # Get cached message if exists
            cached_msg = VIDEO_MSG_CACHE.get(query.from_user.id)
            
            # Use message editing for smooth UX
            await send_random_video_logic(
                client=client, 
                user=query.from_user, 
                chat_id=query.message.chat.id, 
                reply_func=query.message.reply_text,
                edit_message=cached_msg  # Pass cached message for editing
            )

        elif query.data == "cancel_index":
            await mdb.set_index_state(query.from_user.id, {"cancel": True})
            await query.message.edit_text("❌ Indexing cancelled.")

    except Exception as e:
        print(f"Callback error: {e}")
        import traceback
        traceback.print_exc()
        await query.answer("⚠️ An error occurred. Try again later.", show_alert=True)
