import globals
import time


delay = 0

def generate_mission():

    globals.x_target = 1500
    globals.y_target = 1500

    time.sleep(20)

    globals.x_target = 2000
    globals.y_target = 1500

    time.sleep(20)

    globals.x_target = 1000
    globals.y_target = 2000

    time.sleep(20)

    globals.x_target = 2500
    globals.y_target = 750

