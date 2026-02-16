import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters.command import Command
from aiogram.types import Message
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from curl_cffi import requests
from aiohttp import web  # <--- ДОДАНО: для веб-сервера

# --- НАЛАШТУВАННЯ ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = 927262799 
URL = "https://www.olx.ua/uk/list/q-nintendo-ds/?search%5Border%5D=created_at%3Adesc"
CHECK_INTERVAL = 300 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ФУНКЦІЇ ПАРСИНГУ ТА ФАЙЛІВ (Залишаємо без змін) ---
def get_last_id():
    if os.path.exists("last_id.txt"):
        with open("last_id.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

def save_last_id(new_id):
    with open("last_id.txt", "w", encoding="utf-8") as f:
        f.write(str(new_id))

def get_organic_ads():
    # ... (Ваш код парсингу без змін) ...
    # Щоб не копіювати весь код сюди, залиште вашу функцію get_organic_ads як є
    try:
        logging.info("Роблю запит до OLX...")
        response = requests.get(URL, impersonate="chrome120")
        if response.status_code != 200: return []
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all("div", attrs={"data-cy": "l-card"})
        if not cards: cards = soup.select('div[class*="css-1sw7q4x"]')
        if not cards: return []
        organic_ads_list = []
        for card in cards:
            link_tag = card.find("a")
            if not link_tag: continue
            href = link_tag.get("href", "")
            if "promoted" in href: continue
            ad_id = card.get("id")
            if not ad_id: continue
            title_tag = card.find("h6")
            title = title_tag.text.strip() if title_tag else "Без назви"
            price_tag = card.find("p", {"data-testid": "ad-price"})
            price = price_tag.text.strip() if price_tag else "Ціна не вказана"
            if href and not href.startswith("http"): full_link = "https://www.olx.ua" + href
            else: full_link = href
            organic_ads_list.append({"id": ad_id, "link": full_link, "title": title, "price": price})
        return organic_ads_list
    except Exception as e:
        logging.error(f"Помилка парсингу: {e}")
        return []

async def monitor_olx():
    # ... (Ваш код моніторингу без змін) ...
    await asyncio.sleep(5)
    while True:
        current_ads = get_organic_ads()
        last_known_id = get_last_id()
        if current_ads:
            if not last_known_id:
                save_last_id(current_ads[0]["id"])
            else:
                new_items_to_send = []
                for ad in current_ads:
                    if ad["id"] == last_known_id: break
                    new_items_to_send.append(ad)
                if new_items_to_send:
                    logging.info(f"Знайдено {len(new_items_to_send)} нових оголошень!")
                    save_last_id(current_ads[0]["id"])
                    for item in reversed(new_items_to_send):
                        text = f"🔥 <b>Нове оголошення!</b>\n📦 {item['title']}\n💰 {item['price']}\n\n👉 {item['link']}"
                        try: await bot.send_message(MY_ID, text, parse_mode="HTML")
                        except: pass
                        await asyncio.sleep(1)
        await asyncio.sleep(CHECK_INTERVAL)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Моніторинг запущено!")

# --- НОВА ЧАСТИНА: ФЕЙКОВИЙ ВЕБ-СЕРВЕР ---
async def health_check(request):
    return web.Response(text="Bot is running")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render передає порт через змінну оточення PORT. Якщо її немає, беремо 8080
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Dummy server started on port {port}")

# --- ЗАПУСК ---
async def main():
    # Запускаємо веб-сервер, щоб Render був щасливий
    await start_dummy_server()
    
    # Запускаємо ваші задачі
    asyncio.create_task(monitor_olx())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинений")
