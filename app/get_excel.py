import datetime
from collections import OrderedDict
from pyexcel_xls import save_data

from models import Employee, Log
from start import db

date = datetime.datetime.now()


def get_month_logs():
    year, month = date.year, date.month
    return Log.query.filter(Log.date >= datetime.date(year, month, 1),
                            Log.date <= datetime.date(year, month, 31)).all()


def get_workdays(logs):
    work_days = list()
    for log in logs:
        work_days.append(log.date.day)
    work_days = list(set(work_days))
    work_days.sort()
    return work_days


def get_table_list(work_days):
    t = work_days.copy()
    t.insert(0, "ФИО")
    t.append("Всего")
    table = list()
    table.append(t)
    return table


def get_excel():
    logs = get_month_logs()
    work_days = get_workdays(logs)

    table1 = get_table_list(work_days)
    table2 = list(table1)

    for employee in Employee.query.all():
        employee_logs, employee_lateness = dict(), dict()
        for log in logs:
            if log.employee_id == employee.id:
                employee_logs[log.date.day] = log.worktime
                employee_lateness[log.date.day] = log.late

        worklogs = [employee.name]
        lateness = [employee.name]
        for day in work_days:
            if day in employee_logs.keys():
                worklogs.append(0) if employee_logs[day] is None else worklogs.append(employee_logs[day])
                lateness.append(1) if employee_lateness[day] else lateness.append(0)
            else:
                worklogs.append(0)
                lateness.append(0)

        worklogs.append(sum(worklogs[1:]))
        lateness.append(sum(lateness[1:]))
        table1.append(worklogs)
        table2.append(lateness)

    month_name = date.strftime("%B")

    data = OrderedDict()
    data.update({month_name: table1})
    data.update({"Опоздания": table2})

    save_data(f"{month_name}.xls", data)
    return open(f"{month_name}.xls", "rb")
