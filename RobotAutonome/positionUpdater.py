import globals
import time
from math import cos, sin, pi

def update_position():
    speed_coeff = 1
    turn_coeff = pi / 180
    previous_time = time.time()
    while True:
        current_time = time.time()
        if (len(globals.throttle_command_buffer)>0):
            if globals.throttle_command_buffer[0]['time']>current_time:
                distance = (current_time - previous_time) * globals.throttle_command_buffer[0]['value'] * speed_coeff
                globals.x_position = int(globals.x_position + distance * cos(globals.direction))
                globals.y_position = int(globals.y_position + distance * sin(globals.direction))
            else:
                globals.throttle_command_buffer.pop(0)
        if (len(globals.turn_command_buffer)>0):
            if globals.turn_command_buffer[0]['time']>current_time:
                globals.direction += (current_time - previous_time) * globals.turn_command_buffer[0]['value'] * turn_coeff
            else:
                globals.turn_command_buffer.pop(0)
        previous_time = current_time
        time.sleep(0.05)

