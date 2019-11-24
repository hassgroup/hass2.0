from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_socketio import SocketIO, send, emit
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

import os

from RPi import GPIO

hass = Flask(__name__)

hass.config['SECRET_KEY'] = "@our #super $secret %encryption ^key!"
socket = SocketIO(hass)

basedir = os.path.abspath(os.path.dirname(__file__))
hass.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + basedir + '/database/database.db'
db = SQLAlchemy(hass)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(100), unique=True)
    last_login = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return '<User %r>' % self.username

    def create_account(username, password):
        print("Account created")


GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

RED_LED = 11
GREEN_LED = 12

GPIO.setup(RED_LED, GPIO.OUT, initial=GPIO.LOW)


def auth(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' not in session:
            flash('You need to login to access this resource. ', 'warning')
            return redirect(url_for('show_login', next=request.url))
        return f(*args, **kwargs)

    return wrap


def guest(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' not in session:
            return f(*args, **kwargs)
        return redirect(url_for('dashboard'))

    return wrap


@hass.route("/")
@guest
def show_login():
    return render_template("auth/login.html")


@hass.route("/signup")
@guest
def show_signup():
    return render_template("auth/signup.html")


@hass.route("/", methods=['POST'])
@guest
def post_login():
    username = request.form.get('username')
    password = request.form.get('password')

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password, password):
        flash('Please check your login details and try again.')
        return redirect(url_for('show_login'))

    session['logged_in'] = True
    session['username'] = user.username

    if request.args.get('next'):
        return redirect(request.args.get('next'))

    return redirect(url_for('dashboard'))


@hass.route("/signup", methods=["POST"])
@guest
def post_signup():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')

    user = User.query.filter_by(email=email).first()
    if user:
        return redirect(url_for('post_signup'))

    new_user = User(email=email, username=username, password=generate_password_hash(password, method='sha256'),
                    last_login=datetime.now())
    db.session.add(new_user)
    db.session.commit()

    return redirect(url_for('post_login'))


@hass.route("/logout", methods=["GET", "POST"])
@auth
def logout():
    session.pop('username', None)
    session.pop('logged_in', None)

    return redirect(url_for("dashboard"))


@hass.route("/dashboard")
@auth
def dashboard():
    return render_template("pages/dashboard.html")


@hass.route("/stream")
def surveillance():
    return render_template("pages/camera.html")


@hass.route("/lights")
def lights():
    return render_template("pages/lights.html")


@hass.route("/test")
@auth
def test():
    return render_template("pages/test.html")


if __name__ == "__main__":
    socket.run(hass, host='0.0.0.0', port=9000, debug=True)
