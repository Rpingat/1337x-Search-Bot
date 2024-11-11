import os
import logging
import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
from py1337x import py1337x
from dotenv import load_dotenv
from telegraph import Telegraph

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

torrent_client = py1337x(proxy='1337x.to', cache='py1337xCache', cacheTime=500)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
SEEDR_USERNAME = os.getenv('SEEDR_USERNAME')
SEEDR_PASSWORD = os.getenv('SEEDR_PASSWORD')
telegraph = Telegraph()
telegraph.create_account(short_name="1337x_bot")

def format_results(results, start=0, end=5):
    response_text = ""
    for idx, item in enumerate(results[start:end], start=start + 1):
        torrent_info = torrent_client.info(link=item['link'])
        magnet_link = torrent_info.get('magnetLink', 'N/A')
        response_text += (
            f"🎬 <b>{idx}. {item['name']}</b>\n"
            f"    ⚙️ <b>Seeders:</b> {item['seeders']} | <b>Leechers:</b> {item['leechers']}\n"
            f"    🔗 <code>{magnet_link}</code>\n\n"
            "--------------------------------------\n\n"
        )
    return response_text

def authenticate_seedr():
    response = requests.post(
        "https://www.seedr.cc/oauth/token",
        data={
            'grant_type': 'password',
            'username': SEEDR_USERNAME,
            'password': SEEDR_PASSWORD
        }
    )
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        logger.error("Failed to authenticate with Seedr.")
        return None

def mirror_to_seedr(magnet_link):
    token = authenticate_seedr()
    if token:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.post(
            "https://www.seedr.cc/api/folder",
            headers=headers,
            data={'url': magnet_link}
        )
        if response.status_code == 200:
            folder_id = response.json().get('id')
            return f"https://www.seedr.cc/files/{folder_id}"
        else:
            logger.error("Failed to mirror to Seedr.")
            return None
    else:
        return None

async def search_1337x_with_progress(update: Update, context: CallbackContext, query: str):
    message = await update.message.reply_text("🔎 Starting search... 0%")
    for progress in range(20, 100, 20):
        await asyncio.sleep(0.5)
        await message.edit_text(f"🔎 Searching... {progress}%")
    try:
        results = torrent_client.search(query=query, category='movies', sortBy='seeders', order='desc')
        await message.edit_text("🔎 Search completed! 100%")
        await asyncio.sleep(0.5)
        return results['items'][:10]
    except Exception as e:
        logger.error(f"Error searching 1337x: {e}")
        await message.edit_text("An error occurred during the search.")
        return []

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Hello! Use /search <query> to find torrents on 1337x.")

async def search(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text("Please provide a search term. Usage: /search <query>")
        return

    query = ' '.join(context.args)
    results = await search_1337x_with_progress(update, context, query)
    if results:
        context.user_data['results'] = results
        for i in range(0, min(5, len(results)), 1):
            response_text = format_results(results, i, i + 1)
            magnet_link = torrent_client.info(link=results[i]['link']).get('magnetLink', 'N/A')
            identifier = f"mirror_{i}"
            context.user_data[identifier] = magnet_link
            keyboard = [[InlineKeyboardButton("Mirror to Seedr", callback_data=identifier)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(response_text, parse_mode="HTML", reply_markup=reply_markup)
        keyboard = [[InlineKeyboardButton("View All Results", callback_data="show_telegraph")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Click below to view all search results.",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("No results found. Please try a different query.")

async def mirror_seedr_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    identifier = query.data
    magnet_link = context.user_data.get(identifier)
    if not magnet_link:
        await query.edit_message_text("Magnet link not found.")
        return
    seedr_link = mirror_to_seedr(magnet_link)
    if seedr_link:
        await query.edit_message_text(f"Mirrored to Seedr! Access it here: {seedr_link}")
    else:
        await query.edit_message_text("Failed to mirror to Seedr. Please try again later.")

async def show_telegraph(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    results = context.user_data.get('results', [])
    full_text = format_results(results, 0, len(results))
    telegraph_response = telegraph.create_page(
        title="Search Results",
        html_content=full_text.replace("\n", "<br>")
    )
    telegraph_link = f"https://telegra.ph/{telegraph_response['path']}"
    await query.edit_message_text(
        f"All search results are available [here]({telegraph_link}).",
        parse_mode="Markdown"
    )

async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    await update.message.reply_text("An unexpected error occurred. Please try again later.")

def main() -> None:
    if TELEGRAM_TOKEN is None:
        logger.error("TELEGRAM_TOKEN environment variable is not set.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CallbackQueryHandler(mirror_seedr_callback, pattern="^mirror_"))
    application.add_handler(CallbackQueryHandler(show_telegraph, pattern="show_telegraph"))
    application.add_error_handler(error_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
