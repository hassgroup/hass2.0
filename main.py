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
from time import sleep

import RPi.GPIO as GPIO
from pytz import timezone

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
SERVO_PIN = 3

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

GPIO.setup(p_led, GPIO.OUT)
GPIO.setup(r_led, GPIO.OUT)
GPIO.setup(s_led, GPIO.OUT)
GPIO.setup(SERVO_PIN, GPIO.OUT)

pwm=GPIO.PWM(SERVO_PIN, 50)
pwm.start(0)

# GPIO.setup(DHT_GPIO, GPIO.IN)

dht = DHT.DHT11
TEMP_TIME_INTERVAL = 15 # Time after saving temps to database
MAX_TEMP_THRESHOLD = 30.0 # Max temp before fan ons
GET_CONFIG_TIMEOUT = 15 # Timeout after loading database config
temperature_value = []
CONFIG = None # Variable to hold configuration

# import json

# class Object:
#     def toJSON(self):
#         return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(100), unique=True)
    last_login = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return '<User %r>' % self.username

class Config(db.Model):
    __tablename__ = 'config'

    id = db.Column(db.Integer, primary_key=True)
    active = db.Column(db.Boolean, default=True)
    max_temp = db.Column(db.Float, nullable=True)
    temp_auto = db.Column(db.Boolean, default=True)

    @property
    def serialize(self):
        return {
            'id': self.id, 
            'active': self.active, 
            'max_temp': self.max_temp,
            'temp_auto': self.temp_auto,
        }

class Temperature(db.Model):
    __tablename__ = 'temperatures'

    id = db.Column(db.Integer, primary_key=True)
    temp = db.Column(db.String(80), nullable=False)
    humid = db.Column(db.String(120), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return '<Temp %r, %r>' % (self.temp, self.humid)
    
    @property
    def serialize(self):
        return {
            'id': self.id, 
            'temperature': self.temp, 
            'humidity': self.humid, 
            'timestamp': self.timestamp.strftime("%b %d %Y %H:%M:%S"),
            'time': self.timestamp.strftime("%H:%M:%S"),
            'date': self.timestamp.strftime("%b %d %Y"),
        }
def get_config():
    conf = Config.query.filter_by(active=True).first()
    return conf.serialize

def set_config_thread(timeout=15):
    global CONFIG
    times = 1
    while True:
        CONFIG = get_config()
        times += 1
        print("Getting config %s times..." % times)
        print(CONFIG)
        sleep(timeout)


def temp_auto(threshold):
    global CONFIG
    humid, temp = get_temp_humid()
    if temp is not None:
        if CONFIG['temp_auto'] and temp > CONFIG['max_temp']:
            if not GPIO.input(FAN_PIN):
                GPIO.output(FAN_PIN, True)
            print("Condition validated for fan")
        else:
            GPIO.output(FAN_PIN, False)
            print("")
    else:
        print("AutoTemp: Sensor not connected or working")


def store_temp(slp):
    while True:
        humid, temp = DHT.read_retry(dht, DHT_GPIO, 5)
        if humid is not None and temp is not None:
            tz = timezone("Africa/Douala")
            dt = datetime.now()
            local_dt = tz.localize(dt)
            local_dt.replace(hour=local_dt.hour + int(local_dt.utcoffset().total_seconds() / 3600))
            # return local_dt.strftime(format)
            temp = Temperature(temp=temp, humid=humid, timestamp=local_dt)
            db.session.add(temp)
            db.session.commit()
            print("Storing background temp: %s/humid: %s" % (temp.temp, temp.humid))
            time.sleep(slp)
        else:
            print("Error reading temp. Retrying...")


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

@hass.route("/air-condition")
def air_condition():
    return render_template("pages/air-condition.html")

@hass.route("/gate")
def gate():
    return render_template("pages/gate.html")

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

def open_gate(angle):
    duty = angle / 18 + 2
    GPIO.output(SERVO_PIN, True)
    pwm.ChangeDutyCycle(duty)
    sleep(1)
    GPIO.output(SERVO_PIN, False)
    pwm.ChangeDutyCycle(0)
    pwm.stop()

# open_gate(90)

@hass.route("/temp")
def temp():
    humid, temp = get_temp_humid()
    return jsonify({'temp': temp, 'humid': humid})

@socket.on("temp-values")
def get_temp_values(count=20):
    query = Temperature.query.order_by(Temperature.id.desc()).limit(count)
    return [temp.serialize for temp in query.all()]


if __name__ == "__main__":

    temp_thread = threading.Thread(name="store_temp thread", target=store_temp, args=(TEMP_TIME_INTERVAL,))
    temp_thread.setDaemon(True)
    temp_thread.start()

    conf_thread = threading.Thread(name="load_config thread", target=set_config_thread)
    conf_thread.setDaemon(True)
    conf_thread.start()
    socket.run(hass, host='0.0.0.0', port=9000, debug=True)
