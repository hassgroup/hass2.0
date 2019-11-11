from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, send, emit
from flask_sqlalchemy import SQLAlchemy
import os

from RPi import GPIO

hass = Flask(__name__)

hass.config['SECRET_KEY'] = "@our #super $secret %encryption ^key!"
socket = SocketIO(hass)

basedir = os.path.abspath(os.path.dirname(__file__))
print(basedir)
hass.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + basedir + '/database/database.db'
db = SQLAlchemy(hass)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return '<User %r>' % self.username


GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

RED_LED = 11
GREEN_LED = 12

GPIO.setup(RED_LED, GPIO.OUT, initial=GPIO.LOW)


@hass.route("/")
def show_login():
    return render_template("auth/login.html")


@hass.route("/", methods=['POST'])
def post_login():
    username = request.form.get('username')
    password = request.form.get('password')

    print("username: ", username, "\nPassword: ", password)

    return redirect(url_for('show_login'))


if __name__ == "__main__":
    socket.run(hass, host='0.0.0.0', port=9000, debug=True)
