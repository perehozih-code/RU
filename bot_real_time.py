import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

async def parse_wildberries(page, query):
    url = f'https://www.wildberries.ru/catalog/0/search.aspx?search={query}'
    results = []
    try:
        await page.goto(url, timeout=15000)
        await page.wait_for_selector('.product-card', timeout=10000)
        cards = await page.query_selector_all('.product-card')
        for card in cards[:5]:
            try:
                title = await card.query_selector_eval('.goods-name', 'el => el.textContent')
                price_raw = await card.query_selector_eval('.lower-price', 'el => el.textContent')
                price = float(price_raw.replace('â', '').replace('â', '').replace(' ', '').replace(',', '.').strip())
                href = await card.query_selector_eval('a', 'el => el.href')
                image = await card.query_selector_eval('img', 'el => el.src')
                results.append({
                    'title': title.strip(),
                    'marketplace': 'Wildberries',
                    'price': price,
                    'url': href,
                    'image': image
                })
            except Exception as e:
                logger.warning(f"Wildberries parse error item: {e}")
    except PlaywrightTimeoutError:
        logger.warning("Wildberries: Timeout or no results found")
    except Exception as e:
        logger.error(f"Wildberries parsing failed: {e}")
    return results

async def parse_ozon(page, query):
    url = f'https://www.ozon.ru/search/?text={query}'
    results = []
    try:
        await page.goto(url, timeout=15000)
        await page.wait_for_selector('div[data-widget="searchResultsV2"] div[role="listitem"]', timeout=10000)
        cards = await page.query_selector_all('div[data-widget="searchResultsV2"] div[role="listitem"]')
        for card in cards[:5]:
            try:
                title = await card.query_selector_eval('a span', 'el => el.textContent')
                price_raw = await card.query_selector_eval('span[data-widget="price"]', 'el => el.textContent')
                price = float(price_raw.replace('â', '').replace('â', '').replace(' ', '').replace(',', '.').strip())
                href = await card.query_selector_eval('a', 'el => el.href')
                image = await card.query_selector_eval('img', 'el => el.src')
                results.append({
                    'title': title.strip(),
                    'marketplace': 'Ozon',
                    'price': price,
                    'url': href,
                    'image': image
                })
            except Exception as e:
                logger.warning(f"Ozon parse error item: {e}")
    except PlaywrightTimeoutError:
        logger.warning("Ozon: Timeout or no results found")
    except Exception as e:
        logger.error(f"Ozon parsing failed: {e}")
    return results

async def parse_yandex_market(page, query):
    url = f'https://market.yandex.ru/search?text={query}'
    results = []
    try:
        await page.goto(url, timeout=15000)
        await page.wait_for_selector('div[data-zone-name="search-result"]', timeout=10000)
        cards = await page.query_selector_all('div[data-zone-name="search-result"]')
        for card in cards[:5]:
            try:
                title = await card.query_selector_eval('h3 a', 'el => el.textContent')
                price_raw = await card.query_selector_eval('[data-auto="mainPrice"]', 'el => el.textContent')
                price = float(''.join(filter(str.isdigit, price_raw)))
                href = await card.query_selector_eval('h3 a', 'el => el.href')
                image = await card.query_selector_eval('img', 'el => el.src')
                results.append({
                    'title': title.strip(),
                    'marketplace': 'Yandex.Market',
                    'price': price,
                    'url': href,
                    'image': image
                })
            except Exception as e:
                logger.warning(f"Yandex Market parse error item: {e}")
    except PlaywrightTimeoutError:
        logger.warning("Yandex Market: Timeout or no results found")
    except Exception as e:
        logger.error(f"Yandex Market parsing failed: {e}")
    return results

async def search_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if len(query) < 2:
        await update.message.reply_text("Пожалуйста, введи минимум 2 символа для поиска.")
        return

    await update.message.reply_text(f"Ищу «{query}» на маркетплейсах, это займет до 15 секунд...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        tasks = [
            parse_wildberries(page, query),
            parse_ozon(page, query),
            parse_yandex_market(page, query)
        ]
        results = await asyncio.gather(*tasks)

        await browser.close()

    all_results = [item for sublist in results for item in sublist]

    if not all_results:
        await update.message.reply_text("Ничего не найдено по твоему запросу.")
        return

    for item in all_results:
        caption = (
            f"<b>{item['title']}</b>\n"
            f"Маркетплейс: {item['marketplace']}\n"
            f"Цена: {item['price']} ₽"
        )
        keyboard = InlineKeyboardMarkup.from_button(
            InlineKeyboardButton("Перейти к товару", url=item['url'])
        )
        await update.message.reply_photo(
            photo=item['image'] or "https://via.placeholder.com/300x200",
            caption=caption,
            parse_mode='HTML',
            reply_markup=keyboard
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь название товара, и я найду цены на Wildberries, Ozon и Яндекс.Маркете."
    )

def main():
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        print("Установи переменную окружения TELEGRAM_BOT_TOKEN с токеном бота")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_products))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()