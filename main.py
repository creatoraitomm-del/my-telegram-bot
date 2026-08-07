import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# 1. Заглушка для Render
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_health_check_server, daemon=True).start()

# 2. Настройки бота
TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = 479939884

bot = telebot.TeleBot(TOKEN)

# Хранилище динамических слотов (по умолчанию)
available_slots = {
    "Понедельник": ["12:00", "15:00", "18:00"],
    "Среда": ["10:00", "14:00", "16:30"],
    "Пятница": ["11:00", "13:00", "17:00"]
}

# Хранилище состояния админа (для режима ввода новых слотов)
admin_state = {}

# Хранилище выбора пользователей и общих броней
user_booking = {}
all_bookings = []

# --- КЛАВИАТУРЫ ---

# 1. Меню для клиентов
def client_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_book = types.KeyboardButton("📅 Выбрать время и записаться")
    btn_info = types.KeyboardButton("ℹ️ Контакты и инфо")
    btn_ask = types.KeyboardButton("💬 Задать вопрос")
    markup.add(btn_book, btn_info, btn_ask)
    return markup

# 2. Меню ДЛЯ АДМИНИСТРАТОРА
def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_list = types.KeyboardButton("📋 Все записи")
    btn_slots = types.KeyboardButton("⚙️ Изменить слоты")
    btn_stats = types.KeyboardButton("📊 Статистика")
    btn_switch = types.KeyboardButton("👁 Режим клиента")
    markup.add(btn_list, btn_slots, btn_stats, btn_switch)
    return markup

# Динамическая клавиатура выбора дней для клиента
def get_days_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for day in available_slots.keys():
        markup.add(types.InlineKeyboardButton(f"🗓 {day}", callback_data=f"day_{day}"))
    return markup

# --- КОМАНДА /START ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    admin_state[user_id] = None  # Сброс состояния
    
    if user_id == ADMIN_ID:
        bot.send_message(
            message.chat.id, 
            "👑 **Панель администратора**\n\nВыберите нужное действие в меню ниже:", 
            reply_markup=admin_keyboard(),
            parse_mode='Markdown'
        )
    else:
        welcome_text = (
            f"Здравствуйте, {message.from_user.first_name}! 👋\n\n"
            f"Добро пожаловать! Я бот для онлайн-записи.\n"
            f"Выберите нужное действие в меню ниже 👇"
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=client_keyboard())

# --- УПРАВЛЕНИЕ СЛОТАМИ (ДЛЯ АДМИНИСТРАТОРА) ---

@bot.message_handler(func=lambda message: message.text == "⚙️ Изменить слоты" and message.chat.id == ADMIN_ID)
def edit_slots_start(message):
    # Показываем текущие слоты
    slots_info = "⚙️ **Текущие доступные слоты:**\n\n"
    for day, times in available_slots.items():
        slots_info += f"🔹 **{day}:** {', '.join(times)}\n"
    
    slots_info += (
        "\n✍️ **Чтобы изменить слоты, отправьте сообщение в таком формате:**\n"
        "`Понедельник: 10:00, 12:00 | Вторник: 15:00, 18:00 | Четверг: 11:00`\n\n"
        "*(Разделяйте дни символом '|', а время — запятыми)*"
    )
    admin_state[ADMIN_ID] = "WAITING_FOR_SLOTS"
    bot.send_message(ADMIN_ID, slots_info, parse_mode='Markdown')

# Просмотр всех записей
@bot.message_handler(func=lambda message: message.text == "📋 Все записи" and message.chat.id == ADMIN_ID)
def show_all_bookings(message):
    admin_state[ADMIN_ID] = None
    if not all_bookings:
        bot.send_message(ADMIN_ID, "📭 Активных записей пока нет.")
        return
    
    text = "📋 **Список текущих записей:**\n\n"
    for idx, item in enumerate(all_bookings, 1):
        text += f"{idx}. **{item['day']} ({item['time']})** — {item['name']} ({item['phone']})\n"
    
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

# Статистика
@bot.message_handler(func=lambda message: message.text == "📊 Статистика" and message.chat.id == ADMIN_ID)
def show_stats(message):
    admin_state[ADMIN_ID] = None
    total = len(all_bookings)
    bot.send_message(ADMIN_ID, f"📈 **Статистика бота:**\n\nВсего полученных броней: **{total}**", parse_mode='Markdown')

# Режим клиента
@bot.message_handler(func=lambda message: message.text == "👁 Режим клиента" and message.chat.id == ADMIN_ID)
def switch_to_client(message):
    admin_state[ADMIN_ID] = None
    bot.send_message(
        ADMIN_ID, 
        "Вы переключились в вид для обычного клиента. Чтобы вернуться в Админ-панель, введите команду `/start`.", 
        reply_markup=client_keyboard(),
        parse_mode='Markdown'
    )

# --- КЛИЕНТСКИЙ СЦЕНАРИЙ ZAПИСИ ---

@bot.message_handler(func=lambda message: message.text in ["📅 Выбрать время и записаться", "📝 Записаться"])
def choose_day(message):
    if not available_slots:
        bot.send_message(message.chat.id, "К сожалению, сейчас нет доступных слотов для записи.")
        return
    bot.send_message(
        message.chat.id, 
        "Выберите удобный день для записи:", 
        reply_markup=get_days_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_days")
def back_to_days(call):
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="Выберите удобный день для записи:",
        reply_markup=get_days_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("day_"))
def choose_time(call):
    selected_day = call.data.split("_")[1]
    user_booking[call.message.chat.id] = {"day": selected_day}
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    times = available_slots.get(selected_day, [])
    
    time_buttons = [types.InlineKeyboardButton(f"⏰ {t}", callback_data=f"time_{t}") for t in times]
    markup.add(*time_buttons)
    
    btn_back = types.InlineKeyboardButton("⬅️ Назад к выбору дня", callback_data="back_to_days")
    markup.add(btn_back)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"Вы выбрали: **{selected_day}**.\n\nВыберите удобное время или вернитесь назад:",
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("time_"))
def confirm_slot(call):
    selected_time = call.data.split("_")[1]
    chat_id = call.message.chat.id
    
    if chat_id in user_booking:
        user_booking[chat_id]["time"] = selected_time
    else:
        user_booking[chat_id] = {"day": "Ближайший день", "time": selected_time}
    
    day = user_booking[chat_id].get("day", "")
    
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"✅ Вы выбрали: **{day}, {selected_time}**\n\nОстался последний шаг!",
        parse_mode='Markdown'
    )
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_phone = types.KeyboardButton(text="📱 Забронировать (отправить номер)", request_contact=True)
    markup.add(btn_phone)
    
    bot.send_message(
        chat_id, 
        "Нажмите кнопку ниже, чтобы закрепить бронь за вашим номером телефона 👇", 
        reply_markup=markup
    )

# --- ПРИЕМ КОНТАКТА ---
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    user = message.from_user
    chat_id = message.chat.id
    
    booking_info = user_booking.get(chat_id, {"day": "Не указан", "time": "Не указано"})
    day = booking_info.get("day", "Не указан")
    time_slot = booking_info.get("time", "Не указано")
    client_name = f"{contact.first_name} {contact.last_name or ''}".strip()
    phone = f"+{contact.phone_number}"
    
    all_bookings.append({
        "day": day,
        "time": time_slot,
        "name": client_name,
        "phone": phone
    })
    
    lead_info = (
        f"🎯 **ПОДТВЕРЖДЕННАЯ БРОНЬ В БОТЕ!**\n\n"
        f"📅 **Дата/День:** {day}\n"
        f"⏰ **Время:** {time_slot}\n\n"
        f"👤 **Клиент:** {client_name}\n"
        f"📞 **Телефон:** {phone}\n"
        f"🔗 **Юзернейм:** @{user.username if user.username else 'не указан'}\n"
        f"🆔 **ID:** `{user.id}`"
    )
    
    try:
        bot.send_message(ADMIN_ID, lead_info, parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка отправки администратору: {e}")

    bot.send_message(
        chat_id, 
        f"🎉 **Запись успешно подтверждена!**\n\n"
        f"Ждем вас в **{day} в {time_slot}**.\n"
        f"Мы забронировали это время за вами!", 
        reply_markup=client_keyboard(),
        parse_mode='Markdown'
    )

# Обычные клиентские блоки
@bot.message_handler(func=lambda message: message.text == "ℹ️ Контакты и инфо")
def show_info(message):
    info_text = (
        "📍 **Наша контактная информация:**\n\n"
        "🏢 **Адрес:** г. Москва, ул. Примерная, д. 10, офис 404\n"
        "⏰ **Режим работы:** Пн-Пт с 09:00 до 20:00\n"
        "📞 **Телефон:** +7 (999) 000-00-00\n"
        "🌐 **Наш сайт:** https://example.com"
    )
    bot.send_message(message.chat.id, info_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "💬 Задать вопрос")
def ask_question(message):
    ask_text = (
        "❓ **У вас есть вопрос?**\n\n"
        "Просто напишите ваш вопрос прямо в этот чат, и мы перешлем его администратору!"
    )
    bot.send_message(message.chat.id, ask_text, parse_mode='Markdown')

# Обработка текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user = message.from_user
    
    # Администратор
    if message.chat.id == ADMIN_ID:
        # Если админ в режиме обновления слотов
        if admin_state.get(ADMIN_ID) == "WAITING_FOR_SLOTS":
            try:
                new_slots = {}
                raw_days = message.text.split("|")
                for item in raw_days:
                    if ":" in item:
                        day, times_str = item.split(":", 1)
                        times = [t.strip() for t in times_str.split(",") if t.strip()]
                        new_slots[day.strip()] = times
                
                if new_slots:
                    global available_slots
                    available_slots = new_slots
                    admin_state[ADMIN_ID] = None
                    bot.send_message(ADMIN_ID, "✅ **Доступное время успешно обновлено!**", reply_markup=admin_keyboard(), parse_mode='Markdown')
                else:
                    bot.send_message(ADMIN_ID, "❌ Не удалось распознать формат. Попробуйте еще раз.")
                return
            except Exception as e:
                bot.send_message(ADMIN_ID, f"❌ Ошибка формата: {e}. Попробуйте еще раз.")
                return

        # Если админ отвечает на вопрос пользователя
        if message.reply_to_message:
            try:
                msg_text = message.reply_to_message.text
                if "ID:" in msg_text:
                    target_id_str = msg_text.split("ID:")[1].split(")")[0].strip()
                    target_user_id = int(target_id_str)
                    
                    bot.send_message(target_user_id, f"💬 **Ответ от администратора:**\n\n{message.text}", parse_mode='Markdown')
                    bot.send_message(ADMIN_ID, "✅ Ответ успешно переслан клиенту!")
                    return
            except Exception as e:
                bot.send_message(ADMIN_ID, f"❌ Ошибка отправки ответа: {e}")
                return
        else:
            bot.send_message(ADMIN_ID, "💡 Воспользуйтесь кнопками ниже или нажмите «Ответить» (Reply) на сообщение с вопросом клиента.")
            return

    # Клиент
    bot.send_message(
        ADMIN_ID, 
        f"📩 **Вопрос от пользователя (ID: {user.id}):**\n"
        f"👤 **Имя:** {user.first_name} (@{user.username if user.username else 'нет'})\n\n"
        f"💬 **Текст:** {message.text}"
    )
    bot.send_message(message.chat.id, "Ваше сообщение передано администратору! Мы ответим вам в ближайшее время.")

bot.polling(none_stop=True)
