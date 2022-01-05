# -*- coding: utf-8 -*-
import os

import datetime

import pytz
import requests
from Levenshtein import distance
from flask import Flask, request, Response
from flask_sqlalchemy import SQLAlchemy
from flask_sslify import SSLify


app = Flask(__name__)
sslify = SSLify(app)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = os.environ.get("SQLALCHEMY_TRACK_MODIFICATIONS")
db = SQLAlchemy(app)

from models import Employee, Log
from get_excel import get_excel

TZ = pytz.timezone("Asia/Bishkek")
token = os.environ.get("BOT_TOKEN")
URL = "https://api.telegram.org/bot{}/".format(token)
COMPANY_GROUP_ID = os.environ.get("COMPANY_GROUP_ID")
TEST_GROUP_ID = os.environ.get("TEST_GROUP_ID")
GROUP_IDS = [COMPANY_GROUP_ID, TEST_GROUP_ID]
OWNER_ID = os.environ.get("OWNER_ID")
OWNER_TG = os.environ.get("OWNER_TG")


# Message, that bot sends when new member will be added to group
NEW_MEMBER_INFO = """
    Добро пожаловать в чат для ворклога! 
    Вам нужно представиться, для этого отправьте в чат сообщение в формате:
    /new __Фамилия__ __Имя__
"""
# Message, that bot sends when new member will set his name
NEW_EMPLOYEE_INFO = """
    , вы записаны! Теперь вы можете отмечаться, для этого, как только вы пришли в офис, 
    отправьте в чат сообщение __пришел__ или __пришла__. 
    Если вы уходите из офиса, отправьте в чат сообщение __ушел__ или __ушла__
"""
WORK_SCHEDULE = {"start": datetime.time(9, 00), "end": datetime.time(18, 00)}
LATE_TIME = {"start": datetime.time(9, 5), "end": datetime.time(9, 30)}
LUNCH_TIME = {"start": datetime.time(12, 00), "end": datetime.time(13, 00)}


def add_employee(chat_id, user_id, message):
    e = Employee.query.filter_by(telegram_id=user_id).first()
    name = message.strip("/new").strip()
    if e:
        e.name = name
        db.session.add(e)
        db.session.commit()
    else:
        e = Employee(telegram_id=int(user_id), name=str(name))
        db.session.add(e)
        db.session.commit()
        m = name + NEW_EMPLOYEE_INFO
        send_message(chat_id, m)


def get_local_datetime(raw_dt):
    form_dt = datetime.datetime.fromtimestamp(raw_dt)
    time = pytz.utc.localize(form_dt, is_dst=None).astimezone(TZ)
    return time.replace(tzinfo=None)


def get_worktime(start, end, date):
    start1 = max(start.time(), WORK_SCHEDULE.get("start"))
    end1 = min(end.time(), WORK_SCHEDULE.get("end"))
    if end1 > start1:
        lunch_start = max(start1, LUNCH_TIME.get("start"))
        lunch_end = min(end1, LUNCH_TIME.get("end"))
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


def log_in(employee, date, time):
    late = True if (LATE_TIME.get("start") < time.time() < LATE_TIME.get("end")) else False
    log = Log(
        date=date,
        start=time,
        late=late,
        employee_id=employee.id
    )
    db.session.add(log)
    db.session.commit()


def log_out(employee, date, time):
    log = Log.query.filter_by(
        date=date,
        employee_id=employee.id
    ).first()
    if log:
        log.end = time
        log.worktime = get_worktime(log.start, log.end, date)
        db.session.add(log)
        db.session.commit()
    else:
        # Log not found
        pass


@app.route("/", methods=["GET"])
def get_webhook_info():
    url = URL + "getUpdates"
    response = requests.get(url)
    return response.json()


@app.route("/sendmessage")
def send_message(chat_id, message):
    url = URL + "sendMessage"
    data = {"chat_id": chat_id,
            "text": message}
    response = requests.post(url, json=data)
    return response.json()


def send_file(chat_id, file):
    url = URL + "sendDocument"
    data = {"chat_id": chat_id}
    files = {"document": file}
    response = requests.post(url, data=data, files=files)
    return response.json()


def handle_bot_command(message, user_id, chat_id):
    if "new" in message:
        add_employee(chat_id, user_id, message)
    elif "report" in message:
        file = get_excel()
        send_file(chat_id, file)
    else:
        send_message(chat_id, "A command is not recognized.")


def handle_message(message, user_id, chat_id, raw_time):
    employee = Employee.query.filter_by(telegram_id=user_id).first()
    if employee:
        time = get_local_datetime(raw_time)
        date = time.date()
        if distance(message.lower(), "пришл") <= 2:
            log_in(employee, date, time)
        elif distance(message.lower(), "ушл") <= 2:
            log_out(employee, date, time)
        else:
            pass
    else:
        send_message(chat_id, f"Пользователь не найден. {NEW_MEMBER_INFO}")


@app.route("/", methods=["POST"])
def get_updates():
    r = request.get_json()
    if r.get("message"):
        user_id = r["message"]["from"]["id"]
        chat_id = r["message"]["chat"]["id"]
        if str(chat_id) in GROUP_IDS:
            if r["message"].get("text"):
                message = r["message"]["text"].encode().decode("utf-8")
                if r["message"].get("entities"):
                    # if message contain bot commands
                    handle_bot_command(message, user_id, chat_id)
                    return Response(status=200)
                time = r["message"]["date"]
                handle_message(message, user_id, chat_id, time)
                return Response(status=200)
            elif r["message"].get("new_chat_members"):
                send_message(chat_id, NEW_MEMBER_INFO)
                return Response(status=200)
            else:
                # pass telegram system messages
                return Response(status=200)
        else:
            # pass messages from unknown chats
            send_message(chat_id, f"Hello, I am private chat bot. Contact my owner {OWNER_TG}")
            send_message(OWNER_ID, r)
            return Response(status=200)
    else:
        # pass telegram system messages
        return Response(status=200)


if __name__ == "__main__":
    app.run()
