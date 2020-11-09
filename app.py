import json
from datetime import datetime

import requests
import xmltodict
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


NAMES = [
        {'name': 'Фунт стерлингов Соединенного королевства'},
        {'name': 'Белорусский рубль'},
        {'name': 'Доллар США'},
        {'name': 'Евро'},
        {'name': 'Индийская рупия'},
        {'name': 'Казахстанский тенге'},
        {'name': 'Канадский доллар'},
        {'name': 'Китайский юань'},
        {'name': 'Украинская гривна'},
        {'name': 'Швейцарский франк'},
        {'name': 'Японская иена'}
    ]

NAME_TO_CODE = {
    'Фунт стерлингов Соединенного королевства': 'R01035',
    'Белорусский рубль': 'R01090',
    'Доллар США': 'R01235',
    'Евро': 'R01239',
    'Индийская рупия': 'R01270',
    'Казахстанский тенге': 'R01335',
    'Канадский доллар': 'R01350',
    'Китайский юань': 'R01375',
    'Украинская гривна': 'R01720',
    'Швейцарский франк': 'R01775',
    'Японская иена': 'R01820'
}

CODE_TO_NAME = {
    'R01035': 'Фунт стерлингов Соединенного королевства',
    'R01090': 'Белорусский рубль',
    'R01235': 'Доллар США',
    'R01239': 'Евро',
    'R01270': 'Индийская рупия',
    'R01335': 'Казахстанский тенге',
    'R01350': 'Канадский доллар',
    'R01375': 'Китайский юань',
    'R01720': 'Украинская гривна',
    'R01775': 'Швейцарский франк',
    'R01820': 'Японская иена'
}


class ChangesRequest(db.Model):
    __tablename__ = 'сhanges_request'
    id = db.Column(db.Integer, primary_key=True)
    currency = db.Column(db.String(10), nullable=False)
    course_changes = db.relationship("CourseChanges")
    date = db.Column(db.Date, default=datetime.utcnow)

    def __repr__(self):
        return '<ChangesRequest %r' % self.id


class CourseChanges(db.Model):
    __tablename__ = 'сourse_сhanges'
    id = db.Column(db.Integer, primary_key=True)
    changes_request_id = db.Column(
        db.Integer,
        db.ForeignKey('сhanges_request.id')
    )
    currency = db.Column(db.String(10), nullable=False)
    record_date = db.Column(db.Date, nullable=False)
    nominal = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return '<CourseChanges %r' % self.id


@app.route('/')
def index():
    return render_template('index.html')


def get_message(message):
    return render_template(
        'get-course-changes.html',
        data=NAMES, message=message
    )


def validate_data(date_1, date_2):
    if not date_1 or not date_2:
        return get_message('Заполните даты')
    date_req1 = datetime.strptime(date_1, '%Y-%m-%d')
    date_req2 = datetime.strptime(date_2, '%Y-%m-%d')
    if date_req2 < date_req1:
        return get_message(
            'Дата окончания не может быть раньше чем дата начала'
        )
    if date_req2 > datetime.today():
        return get_message(
            'Дата окончания не может быть позже сегодняшней даты'
        )
    return date_req1, date_req2


def get_request(date_req1, date_req2, currency_code):
    try:
        changes_xml = requests.get(
            f'http://www.cbr.ru/scripts/XML_dynamic.asp?date_req1={date_req1}'
            f'&date_req2={date_req2}&VAL_NM_RQ={currency_code}')
    except Exception as e:
        return get_message(f'Сервер Центробанка не доступен. Ошибка {e}')
    data = xmltodict.parse(changes_xml.text)
    data = json.loads(json.dumps(data)).get('ValCurs').get('Record')
    return data


def create_changes_request(currency):
    changes_request = ChangesRequest(currency=currency)
    try:
        db.session.add(changes_request)
        db.session.commit()
    except Exception as e:
        return get_message(f'При создании отчета произошла ошибка - {e}')
    return changes_request


def create_course_changes(data, changes_request_id):
    changes_list = []
    for el in data:
        currency = el.get('@Id')
        record_date = datetime.strptime(el.get('@Date'), '%d.%m.%Y')
        nominal = el.get('Nominal')
        value = float(el.get('Value').replace(',', '.'))
        changes_list.append(
            CourseChanges(
                currency=currency,
                record_date=record_date,
                nominal=nominal,
                value=value,
                changes_request_id=changes_request_id
            )
        )
    try:
        db.session.add_all(changes_list)
        db.session.commit()
    except Exception as e:
        return get_message(f'При создании отчета произошла ошибка - {e}')
    return redirect(f'/course-changes/{changes_request_id}')


@app.route('/get-course-changes', methods=['POST', 'GET'])
def get_course_changes():
    if request.method == 'POST':
        currency = request.form.get('currency')
        date_req1, date_req2 = validate_data(
            request.form.get('date_1'),
            request.form.get('date_2')
        )
        date_req1 = datetime.strftime(date_req1, '%d/%m/%Y')
        date_req2 = datetime.strftime(date_req2, '%d/%m/%Y')
        currency_code = NAME_TO_CODE.get(currency)
        data = get_request(date_req1, date_req2, currency_code)
        changes_request = create_changes_request(currency)
        return create_course_changes(data, changes_request.id)
    return render_template('get-course-changes.html', data=NAMES)


@app.route('/course-changes/<int:changes_request_id>')
def course_changes(changes_request_id):
    changes = CourseChanges.query.filter(
        CourseChanges.changes_request_id == changes_request_id
    )
    currency = CODE_TO_NAME.get(changes[0].currency)
    changes_request = changes[0].changes_request_id
    return render_template(
        'course-changes.html',
        data=changes,
        currency=currency,
        changes_request=changes_request
    )


@app.route('/history')
def get_history():
    changes = ChangesRequest.query.all()
    return render_template('history.html', data=changes)


if __name__ == "__main__":
    app.run(debug=True)
