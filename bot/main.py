#!/usr/bin/env python3
import re
from suport_fl import mess, button, suport
from weather.get_meteo import create_text
from Currency.currency import Currency, create_cur_text
from dotenv import load_dotenv
import os
from cute_animals.animals import Animals
import logging
from weather.weather_main import WeatherClient
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

logging.basicConfig(level=logging.DEBUG)
load_dotenv()

TOKEN = os.getenv('TOKEN')
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot=bot, storage=storage)

weather = WeatherClient(bot)
currency = Currency(bot)
kitty = Animals()


# Форма для прогноза погоды
class FormWeather(StatesGroup):
    city = State()
    date = State()


# Форма для конвектора валют
class FormCurrency(StatesGroup):
    cur = State()
    sum = State()


# Выводим кнопки с выбором функций бота
@dp.message_handler(commands='start')
async def start_help(message: types.Message):
    print(f'{message.from_user.first_name} - command: {message.text}')
    mes = mess.header_mess(message)
    print(message)
    change_btn = button.change_function_btn()
    await message.answer(mes, parse_mode='html', reply_markup=change_btn)


# Сюда приходит callback с выбранной функцией
@dp.callback_query_handler(lambda x: x.data in ['Погода', 'Валюты', 'Милота!', 'Опросы'])
async def process_callback_one_spot(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, f"Вы выбрали {callback_query.data}")
    # В зависимости от выбранной функции запускаем диалог
    if callback_query.data == 'Погода':
        await FormWeather.city.set()
        await bot.send_message(callback_query.from_user.id, 'Введите название города')
    elif callback_query.data == 'Валюты':
        await FormCurrency.cur.set()
        await bot.send_message(callback_query.from_user.id, 'Введите название валют через пробел\nнапример RUB USD')
    elif callback_query.data == 'Милота!':
        await send_random_animal_image(callback_query.from_user.id)


# Эта функция позволяет выйти из диалога командой /cancel
@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='отмена', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.finish()
    await message.reply('Отмана')


# ПРОГНОЗ проверяем и записываем город
@dp.message_handler(state=FormWeather.city)
async def process_name(message: types.Message, state: FSMContext):
    if not await weather.get_weather(message.text):
        return await message.reply("Город не найден. Попробуйте еще раз или /cancel")

    async with state.proxy() as data:
        data['city'] = message.text

    await FormWeather.next()
    markup = button.day_btn()
    await message.reply("На какую дату сформировать прогноз?\nУкажите дату кнопкой на клавиатуре", reply_markup=markup)


# ПРОГНОЗ проверяем дату
@dp.message_handler(lambda message: not re.search(r"[А-Я][а-я]\s\d{2}\s[а-я]+\b|Сейчас", message.text),
                    state=FormWeather.date)
async def process_gender_invalid(message: types.Message):
    return await message.reply("Дата не верна. Укажите дату кнопкой на клавиатуре или /cancel")


# ПРОГНОЗ записываем дату, отправляем прогноз
@dp.message_handler(state=FormWeather.date)
async def process_gender(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['date'] = message.text
        meteo = await weather.get_weather(data['city'])
        date_f = [suport.re_amdate(message.text)]
        text = create_text(date_f, meteo)
        markup = types.ReplyKeyboardRemove()
        await bot.send_message(message.chat.id, 'Ваш прогноз готов!', reply_markup=markup, parse_mode='html')
        markup = button.change_function_btn()
        await bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='html')
    # Заканчиваем диалог
    await state.finish()


@dp.message_handler(state=FormCurrency.cur)
async def process_name(message: types.Message, state: FSMContext):
    cur_from, cur_to = message.text.split()
    await message.reply('Делаем запрос на сервер...')
    answer = await currency.get_cur(cur_to, cur_from, 100)
    print(answer)
    if 'error' in answer:
        return await message.reply("Обозначения валют введены не верно. Попробуйте еще раз или /cancel")

    async with state.proxy() as data:
        data['cur'] = {'to': cur_to, 'from': cur_from, 'rate': answer["info"]["rate"]}

    await FormCurrency.next()
    await message.reply("Введите сумму")


@dp.message_handler(state=FormCurrency.sum)
async def process_gender(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        amount = data['sum'] = message.text
        text = create_cur_text(data['cur'], amount)
        markup = button.change_function_btn()
        await bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='html')
    # Заканчиваем диалог
    await state.finish()


async def send_random_animal_image(chat_id: int):
    image_url = await kitty.get_random_animals()
    markup = button.change_function_btn()
    await bot.send_photo(chat_id, image_url, reply_markup=markup)


def ran_server():
    executor.start_polling(dp)


if __name__ == '__main__':
    ran_server()
