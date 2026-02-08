from pyrogram import Client, filters
from vars import ADMIN_ID, ADMIN_USERNAME, IS_FSUB
from pyrogram.types import *
from Database.userdb import udb
from .fsub import get_fsub
from Database.maindb import mdb
import pytz

@Client.on_message(filters.command("myplan") & filters.private)
async def my_plan(client, message):
    if await udb.is_user_banned(message.from_user.id):
        await message.reply("**🚫 You are banned from using this bot**",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Support 🧑‍💻", url=f"https://t.me/{ADMIN_USERNAME}")]]))
        return
    if IS_FSUB and not await get_fsub(client, message):return
    global_limits = await mdb.get_global_limits()
    FREE_LIMIT = global_limits["free_limit"]
    user_id = message.from_user.id
    user = await mdb.get_user(user_id)
    plan = user.get("plan", "free")
    daily_count = user.get("daily_count", 0)
    daily_limit = user.get("daily_limit", FREE_LIMIT)
    free_trial_count = user.get("free_trial_count", 0)
    prime_expiry = user.get("prime_expiry")
    
    status_text = f">**Plan Details**\n\n"
    status_text += f"**User: {message.from_user.mention}**\n"
    status_text += f"**User id: {user_id}**\n"
    status_text += f"**User Plan: {plan.capitalize()}**\n"
    
    if plan == "free" and IS_VERIFY:
        from vars import FREE_VIDEOS_COUNT, VERIFY_EXPIRE_TIME
        
        # Show free trial status
        status_text += f"\n**📦 Free Trial:**\n"
        status_text += f"**Used Today: {free_trial_count}/{FREE_VIDEOS_COUNT}**\n"
        
        # Check verification status
        user_verified = await mdb.is_user_verified(user_id)
        is_second_verified = await mdb.user_verified(user_id)
        is_second_shortener = await mdb.use_second_shortener(user_id, VERIFY_EXPIRE_TIME)
        is_third_shortener = await mdb.use_third_shortener(user_id, VERIFY_EXPIRE_TIME)
        
        status_text += f"\n**🔐 Verification Status:**\n"
        
        if not user_verified:
            status_text += f"**✗ Not Verified (0/3)**\n"
            status_text += f"**⚠️ Complete verification to get unlimited access!**\n"
        elif user_verified and not is_second_shortener:
            status_text += f"**✓ Verified (1/3) - Active**\n"
            status_text += f"**⏰ Valid until midnight IST**\n"
        elif user_verified and is_second_shortener and not is_second_verified:
            status_text += f"**⚠️ First verification expired**\n"
            status_text += f"**➜ Complete 2nd verification (2/3)**\n"
        elif is_second_verified and not is_third_shortener:
            status_text += f"**✓ Verified (2/3) - Active**\n"
            status_text += f"**⏰ Valid until midnight IST**\n"
        elif is_second_verified and is_third_shortener:
            status_text += f"**⚠️ Second verification expired**\n"
            status_text += f"**➜ Complete 3rd verification (3/3)**\n"
        else:
            status_text += f"**✓ All Verified (3/3) - Active**\n"
            status_text += f"**⏰ Valid until midnight IST**\n"
            
    elif plan == "prime":
        status_text += f"**Daily Limit: {daily_limit}**\n"
        status_text += f"**Today Used: {daily_count}/{daily_limit}**\n"
        status_text += f"**Total Remaining: {daily_limit - daily_count}**\n"
        
        if prime_expiry:
            IST = pytz.timezone('Asia/Kolkata')
            if prime_expiry and prime_expiry.tzinfo is None:
                prime_expiry = prime_expiry.astimezone(IST)
            status_text += f"\n**💎 Premium Status: Active**\n"
            status_text += f"**Expire Time: {prime_expiry.strftime('%I:%M %p IST')}**\n"
            status_text += f"**Expire Date: {prime_expiry.strftime('%d/%m/%Y')}**\n"
    else:
        status_text += f"**Daily Limit: {daily_limit}**\n"
        status_text += f"**Today Used: {daily_count}/{daily_limit}**\n"
        status_text += f"**Total Remaining: {daily_limit - daily_count}**\n"
        
    if daily_count >= daily_limit and plan == "free":
         status_text += "\n**⚠️ You've reached your daily limit.**"
         
    await message.reply_text(status_text)

@Client.on_message(filters.command("prime") & filters.private)
async def add_prime(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.delete()
        await message.reply_text("**🚫 You're not authorized to use this command...**")
        return
    if len(message.command) != 3:
        await message.reply_text("**Usage: /prime {user_id} {duration}{unit}\n\nExample: /prime 123456789 2d\n\nUnits:\ns = seconds\nm = minutes\nh = hours\nd = days\ny = years**")
        return
    try:
        user_id = int(message.command[1])
        duration_input = message.command[2]
        import re
        match = re.match(r'(\d+)([smhdy])', duration_input)
        if not match:
            await message.reply_text("**⚠️ Invalid duration format. Use format like: 2d, 30m, 24h**")
            return
        amount, unit = match.groups()
        duration_str = f"{amount} {unit}"
        success = await mdb.add_prime(user_id, duration_str)
        if success:
            await message.reply_text(f"**✅ User {user_id} has been successfully added to the Prime Plan for {duration_str}.**")
            await client.send_message(chat_id=user_id, text="**🎉 Hey, You've been upgraded to a Premier user, check your plan by using /myplan**")
        else:
            await message.reply_text("**❌ Failed to add user to premium plan. Please check the user ID and duration format.**")
    except ValueError:
        await message.reply_text("**⚠️ Invalid user ID or duration format.**")
    except Exception as e:
        await message.reply_text(f"**❌ An error occurred: {str(e)}**")

@Client.on_message(filters.command("remove") & filters.private)
async def remove_prime(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.delete()
        await message.reply_text("**🚫 You're not authorized to use this command...**")
        return
    if len(message.command) != 2:
        await message.reply_text("**Usage: /remove {user_id}**")
        return
    k = int(message.command[1])
    await mdb.remove_premium(k)
    await message.reply_text(f"**User {k} has been removed from the Prime Plan**")
    await client.send_message(chat_id=k, text="**Your premium access has been removed by the admin.**")

@Client.on_message(filters.command("setlimit") & filters.private)
async def set_limit(client, message):
    if message.from_user.id != ADMIN_ID:
        message.delete()
        await message.reply_text("**🚫 You're not authorized to use this command...**")
        return
    if len(message.command) != 3:
        await message.reply_text("**Usage: /setlimit {free / prime} {new_value}**")
        return
    limit_type = message.command[1].lower()
    try:
        new_value = int(message.command[2])
    except ValueError:
        await message.reply_text("**⚠️ Please provide a valid number for the new limit value**")
        return
    if limit_type not in ("free", "prime"):
        await message.reply_text("**⚠️ Invalid limit type. Use 'free' or 'prime'**")
        return
    await mdb.update_global_limit(limit_type, new_value)
    await message.reply_text(f"**✅ {limit_type.capitalize()} limit updated to {new_value} for all users**")
