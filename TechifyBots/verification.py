import asyncio
import hashlib
import time
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import UserNotParticipant
from database import db
from vars import *
import requests
import aiohttp

# Store temporary verification tokens
verification_tokens = {}

class ShortenerAPI:
    """Handle URL shortening for verification"""
    
    @staticmethod
    def shorten_url(long_url, api_key, base_url):
        """Shorten URL using shortener API"""
        try:
            api_url = f"https://{base_url}/api"
            params = {
                'api': api_key,
                'url': long_url
            }
            response = requests.get(api_url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == 'success':
                return data.get('shortenedUrl')
            else:
                print(f"Shortener error: {data}")
                return None
        except Exception as e:
            print(f"Error shortening URL: {e}")
            return None
    
    @staticmethod
    def get_shortener_for_stage(stage):
        """Get shortener credentials based on verification stage"""
        if stage == 1:
            return SHORTENER_API1, SHORTENER_WEBSITE1, TUTORIAL1
        elif stage == 2:
            return SHORTENER_API2, SHORTENER_WEBSITE2, TUTORIAL2
        elif stage == 3:
            return SHORTENER_API3, SHORTENER_WEBSITE3, TUTORIAL3
        else:
            return SHORTENER_API1, SHORTENER_WEBSITE1, TUTORIAL1

def generate_verification_token(user_id, stage):
    """Generate unique verification token"""
    timestamp = int(time.time())
    token_data = f"{user_id}:{stage}:{timestamp}:{API_HASH}"
    token = hashlib.sha256(token_data.encode()).hexdigest()[:16]
    
    verification_tokens[token] = {
        "user_id": user_id,
        "stage": stage,
        "created_at": timestamp,
        "used": False
    }
    
    # Clean old tokens (older than 1 hour)
    current_time = int(time.time())
    expired_tokens = [t for t, data in verification_tokens.items() 
                      if current_time - data["created_at"] > 3600]
    for t in expired_tokens:
        del verification_tokens[t]
    
    return token

def get_verification_url(token):
    """Generate verification callback URL"""
    # This should be your bot's deep link or callback URL
    return f"https://t.me/{ADMIN_USERNAME}?start=verify_{token}"

async def send_verification_message(client, user_id, stage, reason="verification_required"):
    """Send verification message with shortlink"""
    
    # Generate token
    token = generate_verification_token(user_id, stage)
    
    # Get verification URL
    verify_url = get_verification_url(token)
    
    # Get shortener for this stage
    api_key, base_url, tutorial_url = ShortenerAPI.get_shortener_for_stage(stage)
    
    # Shorten the verification URL
    short_url = ShortenerAPI.shorten_url(verify_url, api_key, base_url)
    
    if not short_url:
        # Fallback: use long URL or error message
        short_url = verify_url
    
    # Create message based on stage and reason
    if reason == "free_trial_expired":
        header = "🚫 <b>Free Trial Expired</b>"
        description = f"""
You have used all your <b>{FREE_DAILY_LIMIT}</b> free videos for today.

To continue accessing unlimited videos, please complete the verification below.
"""
    elif reason == "verification_expired":
        header = "⏰ <b>Verification Expired</b>"
        description = f"""
Your previous verification has expired.

Please complete <b>Stage {stage}</b> verification to continue enjoying unlimited access.
"""
    else:
        header = f"🔐 <b>Verification Stage {stage} Required</b>"
        description = """
To access unlimited videos, please complete the verification process.
This helps us keep the bot running for everyone.
"""
    
    # Calculate expiry time
    expiry_hours = VERIFY_STAGES.get(stage, 300) // 3600
    if expiry_hours == 0:
        expiry_text = f"{VERIFY_STAGES.get(stage, 300) // 60} minutes"
    else:
        expiry_text = f"{expiry_hours} hours"
    
    text = f"""
{header}

{description}

<b>📋 Instructions:</b>
1️⃣ Click the <b>Verify Now</b> button below
2️⃣ Complete the shortlink process
3️⃣ Click <b>✅ I've Completed</b> button
4️⃣ Return to bot to get unlimited access

<b>⏳ Verification Valid for:</b> {expiry_text}
<b>🎁 After Verification:</b> Unlimited videos until expiry

<blockquote><b>💡 Note:</b> Premium users can skip verification. Type /myplan to check your status.</blockquote>
"""
    
    # Create buttons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Verify Now", url=short_url)],
        [InlineKeyboardButton("📖 How to Verify", url=tutorial_url)],
        [InlineKeyboardButton("✅ I've Completed", callback_data=f"check_verify_{token}")],
        [InlineKeyboardButton("💎 Get Premium", callback_data="premium_info")]
    ])
    
    try:
        await client.send_message(
            user_id,
            text,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        return True
    except Exception as e:
        print(f"Error sending verification message: {e}")
        return False

async def handle_video_request(client, message):
    """Main function to handle video requests with verification"""
    user_id = message.from_user.id
    
    # Check if user is banned
    if db.is_banned(user_id):
        await message.reply("🚫 You are banned from using this bot.")
        return False
    
    # Check if maintenance mode (you can add this to vars.py)
    # if MAINTENANCE_MODE and user_id != ADMIN_ID:
    #     await message.reply("🔧 Bot is under maintenance. Please try again later.")
    #     return False
    
    # Check access
    can_access, reason, data = db.can_access_video(user_id)
    
    if can_access:
        if reason == "premium":
            # Premium user - direct access
            db.increment_video_count(user_id)
            return True
        
        elif reason == "verified":
            # Verified user - direct access
            db.increment_video_count(user_id)
            stage = data.get("stage", 0)
            
            # Optional: Show verification status occasionally
            # if random.random() < 0.1:  # 10% chance
            #     await message.reply(f"✅ Verified (Stage {stage}) - Unlimited access active")
            
            return True
        
        elif reason == "free_trial":
            # Free trial user
            remaining = data.get("remaining", 0)
            used = data.get("used", 0)
            
            db.increment_free_video(user_id)
            
            # Warning if last free video
            if remaining == 1:
                await message.reply(
                    f"⚠️ <b>This is your last free video!</b>\n\n"
                    f"You've used {used + 1}/{FREE_DAILY_LIMIT} free videos today.\n"
                    f"Complete verification for unlimited access or upgrade to premium.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔐 Verify Now", callback_data="start_verify")],
                        [InlineKeyboardButton("💎 Get Premium", callback_data="premium_info")]
                    ])
                )
            
            return True
    
    else:
        # Cannot access - need verification
        if reason == "need_verification":
            next_stage = data.get("next_stage", 1)
            await send_verification_message(client, user_id, next_stage, "free_trial_expired")
            return False
        
        elif reason == "need_next_verification":
            next_stage = data.get("next_stage", 1)
            await send_verification_message(client, user_id, next_stage, "verification_expired")
            return False
        
        elif reason == "all_verifications_expired":
            await message.reply(
                "🚫 <b>All Verifications Used</b>\n\n"
                "You have completed all 3 verification stages.\n"
                "Please upgrade to premium for unlimited access or wait for daily reset.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 Get Premium", callback_data="premium_info")]
                ])
            )
            return False
    
    return False

# Callback query handler for verification check
@Client.on_callback_query(filters.regex(r"^check_verify_(.+)$"))
async def check_verification_callback(client, callback_query: CallbackQuery):
    """Handle verification completion check"""
    token = callback_query.data.split("_")[-1]
    user_id = callback_query.from_user.id
    
    if token not in verification_tokens:
        await callback_query.answer("❌ Invalid or expired verification link!", show_alert=True)
        return
    
    token_data = verification_tokens[token]
    
    # Verify token belongs to this user
    if token_data["user_id"] != user_id:
        await callback_query.answer("❌ This verification link is not for you!", show_alert=True)
        return
    
    if token_data["used"]:
        await callback_query.answer("⚠️ This verification has already been used!", show_alert=True)
        return
    
    # Mark token as used
    verification_tokens[token]["used"] = True
    
    # Set verification in database
    stage = token_data["stage"]
    expiry = db.set_verification(user_id, stage)
    
    # Calculate duration
    duration_seconds = VERIFY_STAGES.get(stage, 300)
    if duration_seconds >= 3600:
        duration_text = f"{duration_seconds // 3600} hours"
    else:
        duration_text = f"{duration_seconds // 60} minutes"
    
    # Send success message
    await callback_query.message.edit_text(
        f"✅ <b>Verification Stage {stage} Completed!</b>\n\n"
        f"🎉 You now have <b>unlimited access</b> to videos!\n"
        f"⏰ Valid until: <code>{expiry.strftime('%d %B, %Y %I:%M %p')}</code>\n"
        f"🕐 Duration: {duration_text}\n\n"
        f"<blockquote>When this expires, you'll need to complete Stage {stage + 1 if stage < 3 else 1} verification.</blockquote>\n\n"
        f"Use /getvideos to start watching!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 Get Videos", callback_data="get_videos")]
        ])
    )
    
    await callback_query.answer("✅ Verification successful!", show_alert=False)
    
    # Log verification
    if LOG_VR_CHANNEL:
        try:
            user = callback_query.from_user
            log_text = f"""
✅ <b>New Verification</b>

👤 User: {user.mention}
🆔 ID: <code>{user_id}</code>
🔐 Stage: {stage}
⏰ Expires: {expiry.strftime('%d %B, %Y %I:%M %p')}
"""
            await client.send_message(LOG_VR_CHANNEL, log_text)
        except Exception as e:
            print(f"Error logging verification: {e}")

@Client.on_callback_query(filters.regex(r"^start_verify$"))
async def start_verify_callback(client, callback_query: CallbackQuery):
    """Start verification process"""
    user_id = callback_query.from_user.id
    
    # Check current status
    can_access, reason, data = db.can_access_video(user_id)
    
    if reason == "need_verification":
        stage = data.get("next_stage", 1)
    elif reason == "need_next_verification":
        stage = data.get("next_stage", 1)
    else:
        stage = 1
    
    await callback_query.message.delete()
    await send_verification_message(client, user_id, stage, "verification_required")
    await callback_query.answer()

# Handle deep link verification
@Client.on_message(filters.private & filters.regex(r"^/start verify_(.+)$"))
async def verify_deep_link(client, message):
    """Handle verification from deep link"""
    token = message.text.split("verify_")[-1].split()[0]
    user_id = message.from_user.id
    
    if token not in verification_tokens:
        await message.reply("❌ Invalid or expired verification link!")
        return
    
    token_data = verification_tokens[token]
    
    if token_data["user_id"] != user_id:
        await message.reply("❌ This verification link is not for you!")
        return
    
    if token_data["used"]:
        await message.reply("⚠️ This verification has already been used!")
        return
    
    # Show button to complete verification
    stage = token_data["stage"]
    
    await message.reply(
        f"🔐 <b>Verification Stage {stage}</b>\n\n"
        f"Please click the button below to complete your verification:\n\n"
        f"<b>Note:</b> Only click after completing the shortlink process!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Complete Verification", callback_data=f"check_verify_{token}")],
            [InlineKeyboardButton("📖 Tutorial", url=ShortenerAPI.get_shortener_for_stage(stage)[2])]
        ])
    )

