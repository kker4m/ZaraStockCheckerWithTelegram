from scraperHelpers import *
from telegram_bot import TelegramBot
import json
import logging
import threading
import asyncio
import time
import sys
import random

def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading config.json: {e}")
        raise

async def send_telegram_notification(bot, user_id, message):
    try:
        success = await bot.send_notification(int(user_id), message)
        if not success:
            logging.error(f"Failed to send notification to {user_id}")
    except Exception as e:
        logging.error(f"Error sending notification to {user_id}: {e}")

def send_telegram_notifications(bot, message):
    async def send_all():
        tasks = []
        for user_id in bot.allowed_users:
            tasks.append(send_telegram_notification(bot, user_id, message))
        await asyncio.gather(*tasks, return_exceptions=True)

    try:
        # Mevcut event loop'u kullan veya yeni bir tane oluştur
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(send_all())
    except Exception as e:
        logging.error(f"Error in send_telegram_notifications: {e}")
    finally:
        try:
            if not loop.is_closed():
                loop.close()
        except:
            pass

def run_stock_checker(items, stock_check_event, config, bot):
    while stock_check_event.is_set():
        try:
            config = load_config()
            result = stock_checker(config['items'], stock_check_event, config)
            if result:  # Eğer stok bulunduysa
                print(f"\n🔔 Stok bulundu! Telegram bildirimi gönderiliyor...")
                send_telegram_notifications(bot, result)
                print(f"✅ Telegram bildirimi gönderildi.\n")
                
                # Bildirim gönderdikten sonra bekle
                sleep_time = random.randint(
                    config.get('sleep_min_seconds', 30),
                    config.get('sleep_max_seconds', 60)
                )
                time.sleep(sleep_time)
                
        except Exception as e:
            logging.error(f"Error in stock checker: {e}")
            if stock_check_event.is_set():  # Only sleep if we're still running
                time.sleep(60)  # Hata durumunda 1 dakika bekle

async def main():
    # Logging ayarları
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Stock checker event
    stock_check_event = threading.Event()
    stock_check_event.set()
    bot = None

    try:
        # Config yükle
        config = load_config()
        logging.info("Config loaded successfully")
        
        # Telegram bot başlatma
        bot = TelegramBot()
        
        # Stock checker ayarları
        items = config['items']

        # Stock checker thread'i başlat
        stock_checker_thread = threading.Thread(
            target=run_stock_checker,
            args=(items, stock_check_event, config, bot),
            daemon=True
        )
        stock_checker_thread.start()

        # Start the bot and wait forever
        logging.info("Starting Telegram bot...")
        try:
            await bot.run_async()
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt in bot...")
        finally:
            if bot.app:
                await bot.app.stop()

    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logging.error(f"An error occurred in main: {e}")
    finally:
        # Cleanup
        if stock_check_event.is_set():
            stock_check_event.clear()
        if bot and bot.app:
            try:
                await bot.app.stop()
            except:
                pass
        logging.info("Application shutdown complete")

if __name__ == "__main__":
    # Windows için event loop policy ayarla
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run the main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutting down gracefully...")