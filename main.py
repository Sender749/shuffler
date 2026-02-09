import asyncio
from bot import bot

async def main():
    """Main entry point for the bot"""
    await bot.start()
    print("Bot started successfully!")
    # Keep the bot running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
