import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters.command import Command
from aiogram.types import Message
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from curl_cffi import requests

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = os.getenv("USER_ID") 
URL = "https://www.olx.ua/uk/list/q-nintendo-ds/?search%5Border%5D=created_at%3Adesc"
CHECK_INTERVAL = 300 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_last_id():
    if os.path.exists("last_id.txt"):
        with open("last_id.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

def save_last_id(new_id):
    with open("last_id.txt", "w", encoding="utf-8") as f:
        f.write(str(new_id))

def get_organic_ads():
    try:
        logging.info("Роблю запит до OLX...")
        response = requests.get(URL, impersonate="chrome120")
        
        if response.status_code != 200:
            logging.error(f"Помилка сайту: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        
        cards = soup.find_all("div", attrs={"data-cy": "l-card"})
        if not cards:
            cards = soup.select('div[class*="css-1sw7q4x"]')

        if not cards:
            logging.warning("Не знайдено карток.")
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

            title_tag = card.find("h4")
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
        current_ads = get_organic_ads()
        last_known_id = get_last_id()
        
        if current_ads:
            if not last_known_id:
                newest_ad_id = current_ads[0]["id"]
                save_last_id(newest_ad_id)
                logging.info(f"Ініціалізація: збережено останній ID {newest_ad_id}")
            
            else:
                new_items_to_send = []
                
                for ad in current_ads:
                    if ad["id"] == last_known_id:
                        break
                    new_items_to_send.append(ad)
                
                if new_items_to_send:
                    logging.info(f"Знайдено {len(new_items_to_send)} нових оголошень!")
                    
                    save_last_id(current_ads[0]["id"])
                    
                    for item in reversed(new_items_to_send):
                        text = (
                            f"🔥 <b>Нове оголошення!</b>\n"
                            f"📦 {item['title']}\n"
                            f"💰 {item['price']}\n\n"
                            f"👉 {item['link']}"
                        )
                        try:
                            await bot.send_message(MY_ID, text, parse_mode="HTML")
                            await asyncio.sleep(1) 
                        except Exception as e:
                            logging.error(f"Помилка відправки: {e}")
                else:
                    logging.info("Нових оголошень немає.")
        
        await asyncio.sleep(CHECK_INTERVAL)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Моніторинг запущено! Чекай на Nintendo DS :)")

async def main():
    asyncio.create_task(monitor_olx())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинений")