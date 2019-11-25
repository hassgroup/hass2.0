import RPi.GPIO as GPIO
import time

servoPIN = 3
GPIO.setmode(GPIO.BOARD)
GPIO.setup(servoPIN, GPIO.OUT)

p = GPIO.PWM(servoPIN, 50) # GPIO 17 for PWM with 50Hz
p.start(0) # Initialization

def set_angle(angle):
  duty = angle / 18 + 2
  GPIO.output(3, True)
  p.ChangeDutyCycle(duty)
  # time.sleep(1)
  # GPIO.output(3, False)
  # p.ChangeDutyCycle(0)

try:
    while True:
        for i in range(0, 90, 5):
          set_angle(i)
          time.sleep(0.1)
        # p.ChangeDutyCycle(5)
        # time.sleep(0.5)
        # p.ChangeDutyCycle(7.5)
        # time.sleep(0.5)
        # p.ChangeDutyCycle(10)
        # time.sleep(0.5)
        # p.ChangeDutyCycle(12.5)
        # time.sleep(0.5)
        # p.ChangeDutyCycle(10)
        # time.sleep(0.5)
        # p.ChangeDutyCycle(7.5)
        # time.sleep(0.5)
        # p.ChangeDutyCycle(5)
        # time.sleep(0.5)
        # p.ChangeDutyCycle(2.5)
        # time.sleep(0.5)
except KeyboardInterrupt:
  p.stop()
  GPIO.cleanup()
