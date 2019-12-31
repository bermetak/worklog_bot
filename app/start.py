# -*- coding: utf-8 -*-


import datetime
import pytz
import requests
from Levenshtein import distance

from flask import Flask, request, Response
from flask_sslify import SSLify
import os

from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
sslify = SSLify(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////path_to_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)

from models import Employee, Log
from get_excel import get_excel

TZ = pytz.timezone('Asia/Bishkek')
token = os.environ['BOT_TOKEN']
URL = f'https://api.telegram.org/bot{token}/'
GROUP_IDS = os.environ['GROUP_IDS']


NEW_MEMBER = '''Добро пожаловать в чат для ворклога! 
            Вам нужно представиться, для этого отправьте в чат сообщение в формате:
            /new Фамилия Имя'''
SCHEDULE = {'start': datetime.time(9, 00), 'end': datetime.time(18, 00)}
LATE_TIME = {'not_late': datetime.time(9, 5), 'too_late': datetime.time(9, 30)}
LUNCH_TIME = {'start': datetime.time(12, 00), 'end': datetime.time(13, 00)}


def add_employee(chat_id, user_id, message):
    e = Employee.query.filter_by(telegram_id=user_id).first()
    name = message[4:].strip()
    if e is not None:
        e.name = name
        db.session.add(e)
        db.session.commit()
        return Response(status=200)
    else:
        e = Employee(telegram_id=int(user_id), name=str(name))
        db.session.add(e)
        db.session.commit()
        m = f'''{name}, вы записаны! 
               Теперь вы можете отмечаться, для этого, как только вы пришли в офис и 
               ваш аппарат находится в рабочей сети Ooba, отправьте в чат сообщение
               "пришел" или "пришла". 
               Если вы уходите из офиса, отправьте в чат сообщение "ушел" или "ушла"'''
        send_message(chat_id, m)
        return Response(status=200)


def get_utc_datetime(raw_dt):
    form_dt = datetime.datetime.fromtimestamp(raw_dt)
    time = pytz.utc.localize(form_dt, is_dst=None).astimezone(TZ)
    return time.replace(tzinfo=None)


def get_worktime(start, end, date):
    start1 = max(start.time(), SCHEDULE.get('start'))
    end1 = min(end.time(), SCHEDULE.get('end'))
    if end1 > start1:
        lunch_start = max(start1, LUNCH_TIME.get('start'))
        lunch_end = min(end1, LUNCH_TIME.get('end'))
        lunch_time = datetime.datetime.combine(date, lunch_end) - datetime.datetime.combine(date, lunch_start)
        worktime = datetime.datetime.combine(date, end1) - datetime.datetime.combine(date, start1)
        if lunch_time.total_seconds() > 0:
            worktime -= lunch_time
        tot_seconds = worktime.total_seconds()
        if tot_seconds > 0:
            hours = tot_seconds // 3600
            minutes = tot_seconds % 3600 // 60
            if minutes > 30:
                hours += 1
            return hours
        else:
            return 0
    else:
        return 0


def work_log(employee, message, raw_dt):
    time = get_utc_datetime(raw_dt)
    date = time.date()

    log = Log.query.filter_by(date=date, employee_id=employee.id).first()
    if distance(message.lower(), 'пришл') <= 2:
        if log:
            # Log exists
            pass
        else:
            if LATE_TIME.get('not_late') < time.time() < LATE_TIME.get('too_late'):
                late = True
            else:
                late = False
            log = Log(date=date, start=time, late=late, employee_id=employee.id)
            db.session.add(log)
            db.session.commit()
            return Response(status=200)

    elif distance(message.lower(), 'ушл') <= 2:
        if log:
            if log.end:
                # Log exists
                pass
            else:
                log.end = time
                log.worktime = get_worktime(log.start, log.end, date)
                db.session.add(log)
                db.session.commit()
                return Response(status=200)
        else:
            # Log not found
            pass
    else:
        # message not recognized
        pass


@app.route('/', methods=['GET'])
def get_updates():
    url = URL + 'getUpdates'
    response = requests.get(url)
    return response.json()


def send_message(chat_id, message):
    url = URL + 'sendMessage'
    data = {'chat_id': chat_id,
            'text': message}
    response = requests.post(url, json=data)
    return response.json()


def send_file(chat_id, file):
    url = URL + 'sendDocument'
    data = {'chat_id': chat_id}
    files = {'document': file}
    response = requests.post(url, data=data, files=files)
    return response.json()


@app.route(f'/{token}', methods=['POST'])
def get_message():
    r = request.get_json()
    user_id = r['message']['from']['id']
    chat_id = r['message']['chat']['id']
    if str(chat_id) in GROUP_IDS:
        if r['message'].get('text'):
            message = r['message']['text'].encode().decode('utf-8')

            if 'new' in message:
                add_employee(chat_id, user_id, message)
                return Response(status=200)
            elif 'report' in message:
                file = get_excel()
                send_file(chat_id, file)
                return Response(status=200)
            else:
                employee = Employee.query.filter_by(telegram_id=user_id).first()
                if employee:
                    time = r['message']['date']
                    work_log(employee, message, time)
                    return Response(status=200)
                else:
                    send_message(chat_id, f'Пользователь не найден. {NEW_MEMBER}')
                    return Response(status=200)
        elif r['message'].get('new_chat_members'):
            send_message(chat_id, NEW_MEMBER)
            return Response(status=200)
        else:
            return Response(status=200)
    else:
        send_message(chat_id, "Hello, I'm private chat bot. Contact my owner @akynbekova")
        return Response(status=200)



if __name__ == '__main__':
    app.run()
