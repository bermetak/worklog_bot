# -*- coding: utf-8 -*-

import os
import datetime, pytz, requests

from flask import Flask, request, Response
from flask_sqlalchemy import SQLAlchemy

from Levenshtein import distance

app = Flask(__name__)


# Database settings
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SQLALCHEMY_DATABASE_URI']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.environ['SQLALCHEMY_TRACK_MODIFICATIONS']
db = SQLAlchemy(app)


# Set local timezone in format http://pytz.sourceforge.net/
TZ = pytz.timezone(os.environ['TIMEZONE'])


# Telegram bot settings
token = os.environ['BOT_TOKEN']
GROUP_IDS = os.environ['GROUP_IDS']
URL = f'https://api.telegram.org/bot{token}/'


# Message, that bot sends when new member will be added to group
NEW_MEMBER_INFO = os.environ['NEW_MEMBER_INFO']
# Message, that bot sends when new member will set his name
NEW_EMPLOYEE_INFO = os.environ['NEW_EMPLOYEE_INFO']

# Set up work schedule, lateness time and lunch time
WORK_SCHEDULE = {'start': datetime.time(9, 00), 'end': datetime.time(18, 00)}
LATE_TIME = {'start': datetime.time(9, 5), 'end': datetime.time(9, 30)}
LUNCH_TIME = {'start': datetime.time(12, 00), 'end': datetime.time(13, 00)}


from models import Employee, Log
from get_excel import get_excel



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
        m = name + NEW_EMPLOYEE_INFO
        send_message(chat_id, m)
        return Response(status=200)


def get_utc_datetime(raw_dt):
    form_dt = datetime.datetime.fromtimestamp(raw_dt)
    time = pytz.utc.localize(form_dt, is_dst=None).astimezone(TZ)
    return time.replace(tzinfo=None)


def get_worktime(start, end, date):
    start1 = max(start.time(), WORK_SCHEDULE.get('start'))
    end1 = min(end.time(), WORK_SCHEDULE.get('end'))
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
            if LATE_TIME.get('start') < time.time() < LATE_TIME.get('end'):
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
                    send_message(chat_id, f'Пользователь не найден. {NEW_MEMBER_INFO}')
                    return Response(status=200)
        elif r['message'].get('new_chat_members'):
            send_message(chat_id, NEW_MEMBER_INFO)
            return Response(status=200)
        else:
            return Response(status=200)
    else:
        send_message(chat_id, "Hello, I'm private chat bot. Contact my owner @akynbekova")
        return Response(status=200)



if __name__ == '__main__':
    app.run()
