import os
import logging
import asyncio
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
telegraph = Telegraph()
telegraph.create_account(short_name="1337x_bot")

def format_results(results, start=0, end=5):
    response_text = ""
    for idx, item in enumerate(results[start:end], start=start + 1):
        torrent_info = torrent_client.info(link=item['link'])
        magnet_link = torrent_info.get('magnetLink', 'N/A')
        response_text += (
            f"🎬 <b>{idx}. {item['name']}</b>\n"
            f"⚙️ Seeders: {item['seeders']} | Leechers: {item['leechers']}\n"
            f"🔗 <code>{magnet_link}</code>\n\n"
        )
    return response_text

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
            await update.message.reply_text(response_text, parse_mode="HTML")
        keyboard = [[InlineKeyboardButton("View All Results", callback_data="show_telegraph")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Click below to view all search results.",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("No results found. Please try a different query.")

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
    application.add_handler(CallbackQueryHandler(show_telegraph, pattern="show_telegraph"))
    application.add_error_handler(error_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
