import datetime

from start import db


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    added = db.Column(db.DateTime, default=datetime.datetime.now())
    logs = db.relationship('Log', backref='employee')

    def __init__(self, telegram_id, name):
        self.telegram_id = telegram_id
        self.name = name

    def __repr__(self):
        return '<Employee name is {}>'.format(self.name)


class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    start = db.Column(db.DateTime)
    end = db.Column(db.DateTime)
    out = db.Column(db.DateTime)
    late = db.Column(db.Boolean, default=False)
    worktime = db.Column(db.Integer)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)

    def __repr__(self):
        return '<Log id = {}>'.format(self.id)
