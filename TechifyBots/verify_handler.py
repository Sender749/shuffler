from pyrogram import Client, filters
from pyrogram.types import Message
from Database.maindb import mdb
from vars import LOG_CHNL
import pytz
from datetime import datetime

@Client.on_message(filters.command("start") & filters.private)
async def verification_start_handler(client: Client, message: Message):

    try:
        args = message.text.split(" ", 1)

        # Normal /start (no verify data)
        if len(args) < 2:
            return

        data = args[1]
        user_id = message.from_user.id
        ist = pytz.timezone("Asia/Kolkata")

        # ===== FIRST VERIFICATION =====
        if data.startswith("verify_") and not data.startswith("verify2_") and not data.startswith("verify3_"):

            hash = data.split("_", 2)[2]

            info = await mdb.get_verify_id_info(user_id, hash)
            if not info:
                return await message.reply("❌ Invalid or expired verification link")

            await mdb.update_user(user_id, {
                "last_verified": datetime.now(ist)
            })

            await mdb.update_verify_id_info(user_id, hash, {"verified": True})

            print(f"[VERIFY] User {user_id} completed verification 1")

            await message.reply(
                "✅ **Verification Completed!**\n\n"
                "Now you can enjoy unlimited videos until expiry.\n"
                "Use /getvideos"
            )

            # Log
            if LOG_CHNL:
                await client.send_message(
                    LOG_CHNL,
                    f"[VERIFY-LOG] User {user_id} completed level 1"
                )

            return


        # ===== SECOND VERIFICATION =====
        if data.startswith("verify2_"):

            hash = data.split("_", 2)[2]

            info = await mdb.get_verify_id_info(user_id, hash)
            if not info:
                return await message.reply("❌ Invalid or expired verification link")

            await mdb.update_user(user_id, {
                "second_time_verified": datetime.now(ist)
            })

            await mdb.update_verify_id_info(user_id, hash, {"verified": True})

            print(f"[VERIFY] User {user_id} completed verification 2")

            await message.reply(
                "✅ **Second Verification Completed!**\n\n"
                "You can continue watching videos.\n"
                "Use /getvideos"
            )

            if LOG_CHNL:
                await client.send_message(
                    LOG_CHNL,
                    f"[VERIFY-LOG] User {user_id} completed level 2"
                )

            return


        # ===== THIRD VERIFICATION =====
        if data.startswith("verify3_"):

            hash = data.split("_", 2)[2]

            info = await mdb.get_verify_id_info(user_id, hash)
            if not info:
                return await message.reply("❌ Invalid or expired verification link")

            await mdb.update_user(user_id, {
                "third_time_verified": datetime.now(ist)
            })

            await mdb.update_verify_id_info(user_id, hash, {"verified": True})

            print(f"[VERIFY] User {user_id} completed verification 3")

            await message.reply(
                "✅ **Final Verification Completed!**\n\n"
                "Enjoy unlimited access!\n"
                "Use /getvideos"
            )

            if LOG_CHNL:
                await client.send_message(
                    LOG_CHNL,
                    f"[VERIFY-LOG] User {user_id} completed level 3"
                )

            return

    except Exception as e:
        print(f"[VERIFY-HANDLER] Error: {e}")
