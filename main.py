import asyncio
import os
import logging
import re 
from aiogram import Bot, Dispatcher
from aiogram.filters.command import Command
from aiogram.types import Message
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from curl_cffi import requests
from aiohttp import web

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = os.getenv("USER_ID") 
URL = "https://www.olx.ua/uk/list/q-nintendo-ds/?search%5Border%5D=created_at%3Adesc"
CHECK_INTERVAL = 60 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_last_id():
    try:
        chat = await bot.get_chat(MY_ID)
        
        if chat.pinned_message and chat.pinned_message.text:
            match = re.search(r'ID:\s*(\d+)', chat.pinned_message.text)
            if match:
                return match.group(1)
    except Exception as e:
        logging.error(f"Не вдалося перевірити закріплене повідомлення: {e}")
    return None


def get_organic_ads():
    try:
        logging.info("Роблю запит до OLX...")
        response = requests.get(URL, impersonate="chrome120")
        
        if response.status_code != 200: 
            return []
            
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all("div", attrs={"data-cy": "l-card"})
        if not cards: 
            cards = soup.select('div[class*="css-1sw7q4x"]')
            
        if not cards: 
            return []
            
        organic_ads_list = []
        for card in cards:
            link_tag = card.find("a")
            if not link_tag: continue
            
            href = link_tag.get("href", "")
            if "promoted" in href: 
                continue
                
            ad_id = card.get("id")
            if not ad_id: continue
            
            title_tag = card.find("h6")
            title = title_tag.text.strip() if title_tag else "Без назви"
            
            price_tag = card.find("p", {"data-testid": "ad-price"})
            price = price_tag.text.strip() if price_tag else "Ціна не вказана"
            
            if href and not href.startswith("http"): 
                full_link = "https://www.olx.ua" + href
            else: 
                full_link = href
                
            organic_ads_list.append({
                "id": ad_id, 
                "link": full_link, 
                "title": title, 
                "price": price
            })
            
        return organic_ads_list
    except Exception as e:
        logging.error(f"Помилка парсингу: {e}")
        return []

async def monitor_olx():
    await asyncio.sleep(5)
    while True:
        try:
            current_ads = get_organic_ads()
            last_known_id = get_last_id()
            if current_ads:
                if not last_known_id:
                    logging.info("Закріпленого повідомлення немає. Створюю точку відліку.")
                    item = current_ads[0]
                    text = (
                            f"🟢 <b>Старт моніторингу</b>\n"
                            f"📦 {item['title']}\n"
                            f"💰 {item['price']}\n"
                            f"🆔 ID: <code>{item['id']}</code>\n\n"
                            f"👉 {item['link']}"
                    )
                    msg = await bot.send_message(MY_ID, text, parse_mode="HTML")
                    await bot.pin_chat_message(MY_ID, msg.message_id, disable_notification=True)
                else:
                    new_items_to_send = []
                    for ad in current_ads:
                        if ad["id"] == last_known_id: break
                        new_items_to_send.append(ad)
                    if new_items_to_send:
                        logging.info(f"Знайдено {len(new_items_to_send)} нових оголошень!")
                        last_sent_msg = None
                            
                        for item in reversed(new_items_to_send):
                            text = (
                                    f"🔥 <b>Нове оголошення!</b>\n"
                                    f"📦 {item['title']}\n"
                                    f"💰 {item['price']}\n"
                                    f"🆔 ID: <code>{item['id']}</code>\n\n"
                                    f"👉 {item['link']}"
                                )
                            try: 
                                last_sent_msg = await bot.send_message(MY_ID, text, parse_mode="HTML")
                                await asyncio.sleep(1.5)
                            except Exception as e:
                                logging.error(f"Помилка відправки в ТГ: {e}")
                                    
                            if last_sent_msg:
                                try:
                                    await bot.unpin_all_chat_messages(MY_ID)
                                    await bot.pin_chat_message(MY_ID, last_sent_msg.message_id, disable_notification=True)
                                except Exception as e:
                                    logging.error(f"Не вдалося закріпити повідомлення: {e}")
        except Exception as e:
            logging.error(f"Глобальна помилка в циклі: {e}")
            await asyncio.sleep(60)
            
        await asyncio.sleep(CHECK_INTERVAL)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Моніторинг запущено!")

async def health_check(request):
    return web.Response(text="Bot is running")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Dummy server started on port {port}")

async def main():
    await start_dummy_server()
    
    asyncio.create_task(monitor_olx())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинений")

