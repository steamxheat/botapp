import asyncio
from telethon import TelegramClient, events, Button

API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'
BOT_TOKEN = '7638076310:AAHL2G37wOaOmZNjS65sffUkQuz44xvHyJ8'

client = TelegramClient('bot_session', API_ID, API_HASH)

@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.reply(
        "🎁 Telegram Gifts\n\nПолучите ваш NFT подарок:\n\nhttp://localhost:3000/webapp",
        buttons=[
            [Button.url("🎁 ПОЛУЧИТЬ ПОДАРОК", "http://localhost:3000/webapp")]
        ]
    )

async def main():
    await client.start(bot_token=BOT_TOKEN)
    print("🤖 Бот запущен!")
    await client.run_until_disconnected()

asyncio.run(main())
