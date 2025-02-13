import RPi.GPIO as GPIO
import time

#Static green, red or yellow

#Everything off

#normal loop

#Set up

GPIO.setmode(GPIO.BCM)


#configure pins

green = 0
yellow = 2
red = 3

#Configure pins as outputs
GPIO.setup(green, GPIO.OUT)
GPIO.setup(yellow, GPIO.OUT)
GPIO.setup(red, GPIO.OUT)

GPIO.output(green, GPIO.LOW)
GPIO.output(yellow, GPIO.LOW)
GPIO.output(red, GPIO.LOW)

#normal loop

def normal_loop():
    while True:
        GPIO.output(green, GPIO.HIGH)
        time.sleep(10)
        GPIO.output(green, GPIO.LOW)            
        time.sleep(.5)
        
        GPIO.output(yellow, GPIO.HIGH)
        time.sleep(10)
        GPIO.output(yellow, GPIO.LOW)
        time.sleep(.5)
            
        GPIO.output(red, GPIO.HIGH)
        time.sleep(10)
        GPIO.output(red, GPIO.LOW)
        time.sleep(.5)
#Static green, red or yellow

#static green
def static_green():
    GPIO.output(yellow, GPIO.LOW)
    GPIO.output(red, GPIO.LOW)

    try:
        GPIO.output(green, GPIO.HIGH)
    except KeyboardInterrupt:
        print("Done with green")
#static red
def static_red():
    GPIO.output(yellow, GPIO.LOW)
    GPIO.output(green, GPIO.LOW)

    try:
        GPIO.output(red, GPIO.HIGH)
    except KeyboardInterrupt:
        print("Done with red")
#static yellow
def static_yellow():
    GPIO.output(green, GPIO.LOW)
    GPIO.output(red, GPIO.LOW)

    try:
        GPIO.output(yellow, GPIO.HIGH)
    except KeyboardInterrupt:
        print("Done with green")

#everything off
def every_thing_off():
    GPIO.output(green, GPIO.LOW)
    GPIO.output(red, GPIO.LOW)
    GPIO.output(yellow, GPIO.LOW)

def main():
    try :
        while True:
            command = input("List of Commands: /n 1)static green /n 2)static yellow /n 3) static red /n 4) normal loop /n 5) everything off /n 6) exit")

            if command == "static green":
                try:
                    static_green()
                except KeyboardInterrupt:
                    every_thing_off()
            elif command == "static yellow":
                try:
                    static_yellow()
                except KeyboardInterrupt:
                    every_thing_off()
            elif command == "static red":
                try:
                    static_red()
                except KeyboardInterrupt:
                    every_thing_off()
            elif command == "normal loop":
                try:
                    normal_loop()
                except KeyboardInterrupt:
                    every_thing_off()
            elif command == "everything off":
                try:
                    every_thing_off()
                except KeyboardInterrupt:
                    every_thing_off()
            elif command == "exit":
                every_thing_off()
                break

    finally:
        GPIO.cleanup()

