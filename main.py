import re
from datetime import datetime, timedelta

import threading

import telebot
from tornado.websocket import websocket_connect
from tornado.ioloop import IOLoop
from tornado import gen
from geopy import distance
import geocoder
import logging
import json
import sys
#from bot import TgBot

echo_uri = 'wss://www.seismicportal.eu/standing_order/websocket'
# echo_uri = 'wss://localhost'
PING_INTERVAL = 15
current_location = (42.87, 74.59) #geocoder.ip('me')
tmp_info = {'unid': ''}
print(current_location)
#bot = TgBot()

TOKEN = ""

bot = telebot.TeleBot(TOKEN, parse_mode=None)
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
]

with open('user_id.txt', 'r') as txt:
    users = txt.read().split('\n')

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Salam aleykum, i am earthquake notifier bot.")
    if str(message.chat.id) not in users:
        users.append(str(message.chat.id))
        with open('user_id.txt', 'a') as txt:
            txt.write('\n' + str(message.chat.id))

@bot.message_handler(commands=['worked'])
def bot_worked_message():
    for i in users:
        if i.isdigit():
            chat_id = i
            bot.send_message(chat_id=chat_id, text='Bot worked')

def send_shake_message(message, flag):
    for i in users:
        if i.isdigit():
            chat_id = i
            bot.send_message(chat_id, message, disable_notification=flag, disable_web_page_preview=True,
                             parse_mode='Markdown')

def run_telegram_bot():
    bot.polling()




# You can modify this function to run custom process on the message
def myprocessing(message):
    try:
        data = json.loads(message)
        shake_info = data['data']['properties']
        shake_info['action'] = data['action']
        shake_location = (shake_info['lat'], shake_info['lon'])
        my_distance = int(distance.distance(shake_location, current_location).km)
        shake_info['time'] = re.sub(r'T', ' ', re.sub(r'\..*$', '', shake_info['time']))
        shake_info['cur_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        shake_info['time'] = (datetime.strptime(shake_info['time'], "%Y-%m-%d %H:%M:%S") + timedelta(hours=6)).strftime(
            "%Y-%m-%d %H:%M:%S")
        shake_info[
            'google_link'] = f'https://www.google.com/maps?q={",".join(list(map(str, shake_location)))}&markers={",".join(list(map(str, shake_location)))}'

        if shake_info['unid'] != tmp_info['unid']:
            tmp_info.clear()

            # write in file
            with open('eq_list.json', 'a', encoding='utf-8') as json_file:
                json.dump(shake_info, json_file, ensure_ascii=False, indent=4)
                json_file.write(',')

            # log in console new earthshake
            if 'create' in shake_info['action']:
                msg = '`Mag: {mag}`\nRegion: [{flynn_region}]({google_link}) \nShake time: ***{time}*** \nCurr time : ***{cur_time}*** '
                disable_notification = False if shake_info['mag'] > 5 else True

                # Alarm if mag > 4
                if shake_info['mag'] > 4:
                    send_shake_message(msg.format(**shake_info), disable_notification)
                # Alarm if my_distance < 400
                if my_distance <= 400:
                    for i in range(7):
                        send_shake_message('‼️‼️‼️\n' + msg.format(**shake_info) + ' DISTANCE: ' + str(my_distance), False)

            tmp_info.update(shake_info)



    except Exception:
        logging.exception("Unable to parse json message")


@gen.coroutine
def listen(ws):
    while True:
        msg = yield ws.read_message()
        if msg is None:
            logging.info("close")
            ws = None
            break
        myprocessing(msg)


@gen.coroutine
def launch_client():
    try:
        logging.info("Open WebSocket connection to %s", echo_uri)
        ws = yield websocket_connect(echo_uri, ping_interval=PING_INTERVAL)
    except Exception:
        logging.exception("connection error")
    else:
        logging.info("Waiting for messages...")
        listen(ws)

import signal

exit_event = threading.Event()

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    ioloop = IOLoop.instance()
    signal.signal(signal.SIGTERM, ioloop.stop)
    telegram_bot_thread = threading.Thread(target=run_telegram_bot)
    launch_client()
    try:
        exit_event.clear()
        telegram_bot_thread.start()
        ioloop.start()
    except KeyboardInterrupt:
        ioloop.stop()
        logging.info("Close WebSocket")
        exit_event.set()
        telegram_bot_thread.join()
