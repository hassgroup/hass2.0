from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_socketio import SocketIO, send, emit
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import Adafruit_DHT as DHT
import threading

import os
import json
import time

import RPi.GPIO as GPIO


hass = Flask(__name__)

hass.config['SECRET_KEY'] = "@our #super $secret %encryption ^key!"
socket = SocketIO(hass)

basedir = os.path.abspath(os.path.dirname(__file__))
hass.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + basedir + '/database/database.db'
db = SQLAlchemy(hass)

# LEDS location on GPIO Pin

p_led = 18
r_led = 16
s_led = 15
DHT_GPIO = 4

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

GPIO.setup(p_led, GPIO.OUT)
GPIO.setup(r_led, GPIO.OUT)
GPIO.setup(s_led, GPIO.OUT)
# GPIO.setup(DHT_GPIO, GPIO.IN)

dht = DHT.DHT11
TEMP_TIME_INTERVAL = 15

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(100), unique=True)
    last_login = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return '<User %r>' % self.username



class Temperature(db.Model):
    __tablename__ = 'temperatures'

    id = db.Column(db.Integer, primary_key=True)
    temp = db.Column(db.String(80), nullable=False)
    humid = db.Column(db.String(120), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<Temp %r, %r>' % (self.temp, self.humid)


def store_temp(slp):
    while True:
        humid, temp = DHT.read_retry(dht, DHT_GPIO, 5)
        if humid is not None and temp is not None:
            temp = Temperature(temp=temp, humid=humid)
            db.session.add(temp)
            db.session.commit()
            print("Storing background temp: %s/humid: %s" % (temp.temp, temp.humid))
            time.sleep(slp)
        else:
            print("Error reading temp. Retrying...")

temp_thread = threading.Thread(name="temp/humid thread", target=store_temp, args=(TEMP_TIME_INTERVAL,))
temp_thread.setDaemon(True)
temp_thread.start()


def auth(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Access to this resource is protected. Please login. ', 'warning')
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

def update_devices(key, value):
    content = read_devices_status()
    print(content)
    content[key] = value
    with open("devices.json", "w") as f:
        json.dump(content, f)

def update_led(name, state):
    pin = eval(name)
    GPIO.output(pin, state)
    update_devices(name, state)
    # socket.emit('light_updated', (data = {nam: name, state = state}))
    # @socketio.on('light_updated')
        # def handle_light_update():
    # print("name: ", name, " state: ", state)
    socket.emit('light_updated', {'name': name, 'state': state}, broadcast=True)

@hass.route("/lights")
def lights():
    return render_template("pages/lights.html")


@hass.route("/temperature")
def temperature():
    return render_template("pages/temperature.html")


@hass.route("/toggle_lights", methods=["POST"])
def toggle_lights():

    name = request.args.get('name')
    state = request.args.get('state') == 'true'

    update_led(name, state)
    return jsonify({'success': True})


@socket.on("light-status-changed")
def lightStatus(obj):
    update_led(obj['name'], obj['state'])

@hass.route("/devices")
def get_devices():
    data = read_devices_status()
    return jsonify(data)


def read_devices_status():
    data = {}
    with open("devices.json") as f:
        data = json.load(f)
    return data

def get_temp_humid():
    humid, temp = DHT.read_retry(dht, DHT_GPIO, 5)
    if temp is not None:
        return temp, humid
    return None, None


@hass.route("/temp")
def temp():
    humid, temp = get_temp_humid()
    return jsonify({'temp': temp, 'humid': humid})

@socket.on("temp-values")
def get_temp_values(count=20):
    query = Temperature.query.limit(count).all()
    # print(query)
    for rep in query:
        print(rep)
    # return jsonify(query)     


if __name__ == "__main__":
    socket.run(hass, host='0.0.0.0', port=9000, debug=True)
