from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
import json
import logging
import asyncio

# Conversation states
STORE_SELECTION = 0
URL_INPUT = 1
SIZE_INPUT = 2

class TelegramBot:
    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        self.config = self.load_config()
        self.bot_token = self.config['telegram']['bot_token']
        # allowed_users'ı string listesi olarak tutuyoruz
        self.allowed_users = [str(user) for user in self.config['telegram']['allowed_users']]
        self.supported_stores = {
            'zara': 'ZARA',
            'rossmann': 'Rossmann',
            'pullandbear': 'Pull&Bear',
            'bershka': 'Bershka'
        }
        # Geçici veri saklamak için
        self.temp_product_data = {}
        self.app = None

    def load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        await update.message.reply_text(
            f"Merhaba! Sizin Telegram ID'niz: {user_id}\n"
            f"Kullanıcı adınız: @{username}\n\n"
            "Bu ID'yi config.json dosyasındaki allowed_users listesine eklemelisiniz.\n\n"
            "Komutlar:\n"
            "/add - Yeni ürün ekle\n"
            "/list - Takip edilen ürünleri listele\n"
            "/remove - Ürün kaldır\n"
            "/help - Yardım menüsü"
        )

    async def check_authorized(self, update: Update) -> bool:
        user_id = update.effective_user.id
        if str(user_id) not in self.allowed_users:
            await update.message.reply_text("Bu botu kullanma yetkiniz yok.")
            return False
        return True

    async def add_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ürün ekleme işlemini başlat"""
        if not await self.check_authorized(update):
            return ConversationHandler.END
            
        try:
            # Önceki conversation'ı temizle
            user_id = update.effective_user.id
            if user_id in self.temp_product_data:
                del self.temp_product_data[user_id]

            keyboard = []
            # Her mağaza için bir buton oluştur
            for store_id, store_name in self.supported_stores.items():
                keyboard.append([InlineKeyboardButton(store_name, callback_data=f"store_{store_id}")])

            keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="store_cancel")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Lütfen mağaza seçin:\n\n"
                "Not: İşlemi iptal etmek için /cancel komutunu kullanabilirsiniz.", 
                reply_markup=reply_markup
            )
            return STORE_SELECTION
        except Exception as e:
            logging.error(f"Error in add_start: {e}")
            await update.message.reply_text("Bir hata oluştu. Lütfen tekrar deneyin.")
            return ConversationHandler.END

    async def store_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mağaza seçildikten sonra URL iste"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "store_cancel":
            await query.edit_message_text("İşlem iptal edildi.")
            return ConversationHandler.END
        
        store = query.data.replace("store_", "")
        user_id = update.effective_user.id
        self.temp_product_data[user_id] = {"store": store}
        
        await query.edit_message_text(
            f"{self.supported_stores[store]} seçildi.\n\n"
            "Lütfen ürün URL'sini gönderin:\n\n"
            "Not: İşlemi iptal etmek için /cancel komutunu kullanabilirsiniz."
        )
        return URL_INPUT

    async def url_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """URL alındıktan sonra beden seçimi iste"""
        url = update.message.text
        user_id = update.effective_user.id
        self.temp_product_data[user_id]["url"] = url
        self.temp_product_data[user_id]["sizes"] = []  # Çoklu beden seçimi için liste

        # Rossmann için beden gerekmiyorsa
        if self.temp_product_data[user_id]["store"] == "rossmann":
            await self.save_product(update, context)
            return ConversationHandler.END

        # Beden seçim menüsünü hazırla
        keyboard = [
            [InlineKeyboardButton("XS", callback_data="size_XS"),
             InlineKeyboardButton("S", callback_data="size_S"),
             InlineKeyboardButton("M", callback_data="size_M")],
            [InlineKeyboardButton("L", callback_data="size_L"),
             InlineKeyboardButton("XL", callback_data="size_XL")],
            [InlineKeyboardButton("36", callback_data="size_36"),
             InlineKeyboardButton("37", callback_data="size_37")]
        ]

        # Sadece Zara ve Bershka için çanta seçeneği ekle
        store = self.temp_product_data[user_id]["store"]
        if store in ["zara", "bershka"]:
            keyboard.append([InlineKeyboardButton("👜 ÇANTA", callback_data="size_BAG")])

        keyboard.append([InlineKeyboardButton("✅ Seçimi Tamamla", callback_data="size_done")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Mesajı hazırla
        message = "Lütfen takip etmek istediğiniz bedenleri seçin.\n"
        if store in ["zara", "bershka"]:
            message += "Çanta/Aksesuar için 'ÇANTA' seçeneğini kullanın.\n"
        message += "Birden fazla beden seçebilirsiniz.\n"
        message += "Seçiminiz bittiğinde 'Seçimi Tamamla' butonuna tıklayın:"

        await update.message.reply_text(message, reply_markup=reply_markup)
        return SIZE_INPUT

    async def size_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Beden seçimlerini yönet"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if "sizes" not in self.temp_product_data[user_id]:
            self.temp_product_data[user_id]["sizes"] = []

        if query.data == "size_done":
            if not self.temp_product_data[user_id]["sizes"]:
                await query.edit_message_text("Lütfen en az bir beden seçin!")
                return SIZE_INPUT
            
            self.temp_product_data[user_id]["size"] = self.temp_product_data[user_id]["sizes"]
            await self.save_product(update, context)
            return ConversationHandler.END

        size = query.data.replace("size_", "")
        sizes = self.temp_product_data[user_id]["sizes"]
        store = self.temp_product_data[user_id]["store"]
        
        if size in sizes:
            sizes.remove(size)
        else:
            sizes.append(size)

        # Güncellenmiş beden seçim menüsü
        keyboard = [
            [InlineKeyboardButton(
                f"{'✅ ' if 'XS' in sizes else ''}XS", callback_data="size_XS"),
             InlineKeyboardButton(
                f"{'✅ ' if 'S' in sizes else ''}S", callback_data="size_S"),
             InlineKeyboardButton(
                f"{'✅ ' if 'M' in sizes else ''}M", callback_data="size_M")],
            [InlineKeyboardButton(
                f"{'✅ ' if 'L' in sizes else ''}L", callback_data="size_L"),
             InlineKeyboardButton(
                f"{'✅ ' if 'XL' in sizes else ''}XL", callback_data="size_XL")],
            [InlineKeyboardButton(
                f"{'✅ ' if '36' in sizes else ''}36", callback_data="size_36"),
             InlineKeyboardButton(
                f"{'✅ ' if '37' in sizes else ''}37", callback_data="size_37")]
        ]

        # Sadece Zara ve Bershka için çanta seçeneği ekle
        if store in ["zara", "bershka"]:
            keyboard.append([InlineKeyboardButton(
                f"{'✅ ' if 'BAG' in sizes else ''}👜 ÇANTA", callback_data="size_BAG")])

        keyboard.append([InlineKeyboardButton("✅ Seçimi Tamamla", callback_data="size_done")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Seçilen bedenler: {', '.join(['Çanta' if s == 'BAG' else s for s in sizes]) if sizes else 'Henüz seçim yapılmadı'}\n"
            "Seçiminiz bittiğinde 'Seçimi Tamamla' butonuna tıklayın:",
            reply_markup=reply_markup
        )
        return SIZE_INPUT

    async def save_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ürünü config'e kaydet"""
        user_id = update.effective_user.id
        product_data = self.temp_product_data[user_id]
        
        new_product = {
            "store": product_data["store"],
            "url": product_data["url"]
        }

        # Rossmann dışındaki mağazalar için sizes_to_check ekle
        if product_data["store"] != "rossmann" and "size" in product_data:
            new_product["sizes_to_check"] = product_data["size"]  # Artık bir liste

        if "items" not in self.config:
            self.config["items"] = []
        
        # Eğer aynı URL varsa güncelle, yoksa yeni ekle
        url_exists = False
        for item in self.config["items"]:
            if item["url"] == product_data["url"]:
                url_exists = True
                if "size" in product_data and "sizes_to_check" in item:
                    # Yeni bedenleri ekle (tekrar etmeyecek şekilde)
                    item["sizes_to_check"] = list(set(item["sizes_to_check"] + product_data["size"]))
                break
        
        if not url_exists:
            self.config["items"].append(new_product)
        
        self.save_config()

        # Mesajı gönder
        store_name = self.supported_stores[product_data["store"]]
        if "size" in product_data:
            message = f"Ürün eklendi:\nMağaza: {store_name}\nBedenler: {', '.join(product_data['size'])}"
        else:
            message = f"Ürün eklendi:\nMağaza: {store_name}"

        if isinstance(update, Update):
            if update.callback_query:
                await update.callback_query.edit_message_text(message)
            else:
                await update.message.reply_text(message)

        # Geçici veriyi temizle
        del self.temp_product_data[user_id]

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """İşlemi iptal et"""
        user_id = update.effective_user.id
        if user_id in self.temp_product_data:
            del self.temp_product_data[user_id]
        await update.message.reply_text("İşlem iptal edildi.")
        return ConversationHandler.END

    async def list_products(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_authorized(update):
            return
        if not self.config.get('items', []):
            await update.message.reply_text("Takip edilen ürün bulunmuyor.")
            return

        message = "Takip edilen ürünler:\n\n"
        for i, product in enumerate(self.config['items'], 1):
            store_name = self.supported_stores[product['store']]
            message += f"{i}. {store_name}\n{product['url']}"
            if 'sizes_to_check' in product:
                message += f"\nTakip edilen bedenler: {', '.join(product['sizes_to_check'])}"
            message += "\n\n"
        
        await update.message.reply_text(message)

    async def remove_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ürün silme menüsünü göster"""
        if not await self.check_authorized(update):
            return
        if not self.config.get('items', []):
            await update.message.reply_text("Silinecek ürün bulunmuyor.")
            return

        keyboard = []
        for i, product in enumerate(self.config['items'], 1):
            store_name = self.supported_stores[product['store']]
            display_text = f"{i}. {store_name}"
            if 'sizes_to_check' in product:
                display_text += f" ({', '.join(product['sizes_to_check'])})"
            keyboard.append([InlineKeyboardButton(display_text, callback_data=f"remove_{i-1}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Silmek istediğiniz ürünü seçin:", reply_markup=reply_markup)

    async def remove_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Seçilen ürünü sil"""
        query = update.callback_query
        await query.answer()
        
        index = int(query.data.replace("remove_", ""))
        if 0 <= index < len(self.config['items']):
            removed = self.config['items'].pop(index)
            self.save_config()
            store_name = self.supported_stores[removed['store']]
            sizes_text = f" ({', '.join(removed['sizes_to_check'])})" if 'sizes_to_check' in removed else ""
            await query.edit_message_text(f"Ürün kaldırıldı: {store_name}{sizes_text}")
        else:
            await query.edit_message_text("Geçersiz seçim.")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_authorized(update):
            return
        help_text = """
        Kullanılabilir komutlar:
        
        /start - Botu başlat
        /add - Yeni ürün ekle
        /list - Takip edilen ürünleri listele
        /remove - Ürün kaldır
        /help - Bu mesajı göster
        /cancel - Devam eden işlemi iptal et
        """
        await update.message.reply_text(help_text)

    async def run_async(self):
        try:
            # Build application
            self.app = Application.builder().token(self.bot_token).build()
            
            # Conversation handler for adding products
            conv_handler = ConversationHandler(
                entry_points=[CommandHandler("add", self.add_start)],
                states={
                    STORE_SELECTION: [
                        CallbackQueryHandler(self.store_callback, pattern=r"^store_"),
                        CommandHandler("cancel", self.cancel)
                    ],
                    URL_INPUT: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.url_input),
                        CommandHandler("cancel", self.cancel)
                    ],
                    SIZE_INPUT: [
                        CallbackQueryHandler(self.size_callback, pattern=r"^size_"),
                        CommandHandler("cancel", self.cancel)
                    ]
                },
                fallbacks=[
                    CommandHandler("cancel", self.cancel),
                    MessageHandler(filters.COMMAND, self.invalid_command_during_conversation)
                ],
                name="my_conversation",
                persistent=False,
                allow_reentry=True
            )

            # Add handlers
            self.app.add_handler(conv_handler)
            
            # Command handlers
            command_handlers = [
                CommandHandler("start", self.start),
                CommandHandler("list", self.list_products),
                CommandHandler("remove", self.remove_product),
                CommandHandler("help", self.help),
                CallbackQueryHandler(self.remove_callback, pattern=r"^remove_")
            ]
            
            for handler in command_handlers:
                self.app.add_handler(handler)

            # Add error handler
            self.app.add_error_handler(self.error_handler)

            # Start the bot
            logging.info("Starting bot...")
            await self.app.initialize()
            await self.app.start()
            logging.info("Bot started successfully")

            # Start polling with error handling
            await self.app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query", "chat_member"]
            )

            # Keep the application running
            while True:
                await asyncio.sleep(1)

        except Exception as e:
            logging.error(f"Error in run_async: {e}")
            raise

    async def invalid_command_during_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Conversation sırasında geçersiz komut girildiğinde"""
        await update.message.reply_text(
            "Aktif bir işlem devam ediyor. Lütfen önce mevcut işlemi tamamlayın veya /cancel ile iptal edin."
        )
        return None  # Mevcut durumu koru

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors in the bot."""
        logging.error(f"Exception while handling an update: {context.error}")
        try:
            if update and isinstance(update, Update) and update.effective_message:
                await update.effective_message.reply_text(
                    "Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin."
                )
        except Exception as e:
            logging.error(f"Error in error handler: {e}")

    async def send_notification(self, user_id: int, message: str):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                if self.app and self.app.bot:
                    await self.app.bot.send_message(
                        chat_id=user_id, 
                        text=f"🔔 Stok Bildirimi 🔔\n\n{message}",
                        disable_web_page_preview=False  # URL önizlemesini göster
                    )
                    logging.info(f"Notification sent to user {user_id}")
                    return True
                else:
                    # Yeni bir uygulama ve bot oluştur
                    app = Application.builder().token(self.bot_token).build()
                    await app.initialize()
                    await app.start()
                    try:
                        await app.bot.send_message(
                            chat_id=user_id, 
                            text=f"🔔 Stok Bildirimi 🔔\n\n{message}",
                            disable_web_page_preview=False
                        )
                        logging.info(f"Notification sent to user {user_id} via temporary bot")
                        return True
                    finally:
                        await app.stop()
                        
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    logging.error(f"Failed to send notification to {user_id} after {max_retries} attempts: {e}")
                    import traceback
                    logging.error(f"Full error traceback: {traceback.format_exc()}")
                    return False
                else:
                    logging.warning(f"Retry {retry_count}/{max_retries} for sending notification to {user_id}")
                    await asyncio.sleep(1)  # Retry after 1 second