import asyncio
import logging
import re
import sys
from datetime import datetime
from os import getenv

import aiogram.utils.markdown as md
import pytz
import requests
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from dotenv import load_dotenv
from timezonefinder import TimezoneFinder


async def start_command(message: types.Message):
    await message.answer(
        "🤗 Добро пожаловать! 🤗"
        "\n\nНапиши название города, чтобы узнать местное время и разницу во времени с Москвой"
        "\nНАПРИМЕР: Уфа"
        "\nОТВЕТ: 02:42 Уфа ＋2"
        "\n\nЧтобы узнать follow up"
        "\nПроцитируй, ответь или смахни сообщение на телефоне и укажи время в формате 12:30"
        "\nНАПРИМЕР: 13:00"
        "\nОТВЕТ: ⏰ follow-up в 12:00 по Москве ⏰"
        "\n\nЧтобы трансформировать текс, введи предложение после /t"
        "\nНАПРИМЕР: /t этО ПриМер Не правиЛЬНОй стРОки, Где После заПятой, Маленькие БУКвы. а после точки бОЛЬШИЕ!"
        "\nОТВЕТ: Это пример не правильной строки, где после запятой, маленькие буквы. А после точки большие!")


def _city_time_timezone(city_name):
    try:
        nominatim_url = f"https://nominatim.openstreetmap.org/search?format=json&q={city_name}&limit=1&accept-language=ru"
        response = requests.get(nominatim_url)
        data = response.json()

        if data and len(data) > 0:
            latitude = float(data[0]["lat"])
            longitude = float(data[0]["lon"])
            tf = TimezoneFinder()
            timezone_str = tf.timezone_at(lng=longitude, lat=latitude)

            if timezone_str:
                timezone = pytz.timezone(timezone_str)
                current_time = pytz.utc.localize(datetime.utcnow()).astimezone(timezone)
                return timezone, current_time
        return None, None

    except Exception as e:
        print(str(e))
        return None, None


async def get_city_time_timezone(message: types.Message):
    timezone_msk, current_time_msk = _city_time_timezone('Москва')
    city_name = message.text.strip()
    timezone, current_time = _city_time_timezone(city_name)

    if timezone is not None:
        utc_offset_msk = current_time_msk.utcoffset()
        hours_msk = int(utc_offset_msk.total_seconds() // 3600)
        utc_offset = current_time.utcoffset()
        hours = int(utc_offset.total_seconds() // 3600)
        utc_difference = hours_msk - hours

        sign = "＋" if utc_offset.total_seconds() >= utc_offset_msk.total_seconds() else "－"
        utc_format = f"{current_time.strftime('%H:%M')} {city_name} {sign}{abs(utc_difference)}"

        await message.answer(
            md.text(
                utc_format,
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await message.answer("Город не найден. Пожалуйста, укажите действительное название города.")


async def get_followup(message: types.Message):
    try:
        quoted_message = message.reply_to_message
        user_time = datetime.strptime(message.text.strip(), '%H:%M').time()
        user_time_sec = user_time.hour * 3600 + user_time.minute * 60
        try:
            city_utc_str = quoted_message.text.split()[-1]
            numeric_value = int(city_utc_str[1:])

            followup_sec = (user_time_sec + (-numeric_value * 3600) + 3600) // 3600
            followup_h = (followup_sec + 24) % 24

            await message.answer(
                md.text(
                    f'⏰ follow-up в {md.bold(followup_h + 1) if user_time.minute > 30 else md.bold(followup_h)}'
                    f':{md.bold(30) if 0 < user_time.minute <= 30 else md.bold(f"{00:02d}")} по Москве ⏰',
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except ValueError:
            await message.answer("Это не ответ на сообщение. Пожалуйста, ответьте на сообщение с указанием города.")
    except ValueError:
        await message.answer("Неверный формат времени. Введите время в формате HH:MM.")


async def get_city_time_timezone_and_followup(message: types.Message):
    if message.reply_to_message:
        await get_followup(message)
    else:
        await get_city_time_timezone(message)


def _transform_text(text):
    sentences = re.split(r'([.!?])\s+', text)
    transformed_text = ""

    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        transformed_sentence = sentence[0].upper() + sentence[1:].lower()
        transformed_text += transformed_sentence

        if i + 1 < len(sentences):
            transformed_text += sentences[i + 1] + " "

    return transformed_text


async def transform_text_command(message: types.Message):
    input_text = message.text[len('/t '):]
    transformed_text = _transform_text(input_text)
    await message.answer(transformed_text)


async def start():
    load_dotenv()
    bot_token = getenv('BOT_TOKEN')
    bot = Bot(token=bot_token)
    dp = Dispatcher()

    dp.message.register(start_command, Command(commands=['start', 'run']))
    dp.message.register(transform_text_command, Command(commands=['t']))
    dp.message.register(get_city_time_timezone_and_followup, F.text)
    # dp.message.register(get_city_time_timezone, F.text.lower())
    # dp.message.register(get_followup, F.text)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(start())
