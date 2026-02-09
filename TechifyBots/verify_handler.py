from pyrogram import Client, filters
from Database.maindb import mdb
from vars import VERIFY_STAGES

@Client.on_message(filters.command("start") & filters.private)
async def timer_verify(client, message):

    args = message.text.split(" ", 1)

    if len(args) < 2:
        return

    data = args[1]
    user_id = message.from_user.id

    if data.startswith("verify3_"):
        stage = 3
    elif data.startswith("verify2_"):
        stage = 2
    elif data.startswith("verify_"):
        stage = 1
    else:
        return

    duration = VERIFY_STAGES[stage]

    await mdb.set_verify_timer(user_id, stage, duration)

    print(f"[TIMER] User {user_id} verified stage {stage} for {duration}s")

    await message.reply(
        f"✅ Verification {stage} completed!\n"
        f"⏱ Valid for {duration} seconds\n\n"
        "Use /getvideos"
    )
