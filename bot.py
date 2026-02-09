from vars import *
import time
from pytz import timezone
from datetime import datetime
import os
from pyrogram import Client
import asyncio

class Bot(Client):
    def __init__(self):
        super().__init__(
            "techifybots",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="TechifyBots"),
            workers=200,
            sleep_threshold=15,
            # Add network retry configuration
            no_updates=False,
            max_concurrent_transmissions=1
        )
        self.START_TIME = time.time()

    async def start(self):
        # Skip internal web server since gunicorn is already running
        print("Connecting to Telegram...")
        
        # Retry connection with exponential backoff
        max_retries = 5
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                await super().start()
                me = await self.get_me()
                print(f"✅ Bot Started as {me.first_name}")
                print("✅ Bot started successfully!")
                
                # Send startup messages
                if isinstance(ADMIN_ID, int):
                    try:
                        await self.send_message(ADMIN_ID, f"**{me.first_name} is started...**")
                    except Exception as e:
                        print(f"⚠️ Error sending message to admin: {e}")

                if LOG_CHNL:
                    try:
                        now = datetime.now(timezone("Asia/Kolkata"))
                        msg = (
                            f"**{me.mention} is restarted!**\n\n"
                            f"📅 Date : `{now.strftime('%d %B, %Y')}`\n"
                            f"⏰ Time : `{now.strftime('%I:%M:%S %p')}`\n"
                            f"🌐 Timezone : `Asia/Kolkata`"
                        )
                        await self.send_message(LOG_CHNL, msg)
                    except Exception as e:
                        print(f"⚠️ Error sending to LOG_CHANNEL: {e}")
                
                return  # Success, exit retry loop
                
            except Exception as e:
                print(f"❌ Connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    print(f"⏳ Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print("❌ All connection attempts failed!")
                    raise

    async def stop(self, *args):
        try:
            await super().stop()
            me = await self.get_me()
            print(f"{me.first_name} Bot stopped.")
        except:
            print("Bot stopped.")

bot = Bot()
