import os
import asyncio
from telethon import TelegramClient, events, Button

API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'
BOT_TOKEN = os.getenv('BOT_TOKEN', '7638076310:AAHL2G37wOaOmZNjS65sffUkQuz44xvHyJ8')

client = TelegramClient('bot_session', API_ID, API_HASH)

@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    web_app_url = os.getenv('WEB_APP_URL', 'https://your-app-name.onrender.com/gift_webapp.html')
    
    await event.reply(
        "🎁 Telegram Gifts\n\nПолучите ваш NFT подарок:\n\n" + web_app_url,
        buttons=[
            [Button.url("🎁 ПОЛУЧИТЬ ПОДАРОК", web_app_url)]
        ]
    )

async def main():
    await client.start(bot_token=BOT_TOKEN)
    print("🤖 Бот запущен!")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())