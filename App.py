# Replace libraries by fake ones
import sys
import fake_rpi

sys.modules['RPi'] = fake_rpi.RPi     # Fake RPi
sys.modules['RPi.GPIO'] = fake_rpi.RPi.GPIO # Fake GPIO
sys.modules['smbus'] = fake_rpi.smbus # Fake smbus (I2C)

from flask import Flask, render_template, request
import RPi.GPIO as GPIO
import threading
import time

# SETUP THE GPIO
GPIO.setmode(GPIO.BOARD)
lights = {"RED":15,"YELLOW":13,"GREEN":15}

for pin in lights.values():
  GPIO.setup(pin, GPIO.OUT)
  GPIO.output(pin, GPIO.LOW)

app = Flask(__name__)
current_mode = "STOP"
running = False

# Function to perform a standard traffic light sequence
def traffic_light_sequence():
  global running
  while running:
    GPIO.output(lights["RED"], GPIO.HIGH)
    time.sleep(5)
    GPIO.output(lights["RED"], GPIO.LOW)
    GPIO.output(lights["GREEN"], GPIO.HIGH)
    time.sleep(5)
    GPIO.output(lights["YELLOW"], GPIO.HIGH)
    GPIO.output(lights["GREEN"], GPIO.LOW)
    time.sleep(5)
    GPIO.output(lights["YELLOW"], GPIO.LOW)

@app.route('/')
def index():
  return render_template('index.html', current_mode=current_mode)

@app.route('/control', methods=['POST'])
def control():
  global current_mode, running

  mode = request.form['mode']
  current_mode = mode

  # Set all lights to off
  for pin in lights.values():
    GPIO.output(pin, GPIO.LOW)

  if mode == "STOP":
    running = False
  elif mode == "SEQUENCE":
    running = True
    threading.Thread(target=traffic_light_sequence, daemon=True).start()
  else: # In following mode you can hold or flash any specific light
    pass
  
  return render_template('index.html', current_mode=current_mode)
