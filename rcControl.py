import globals

import time

import serial

import multiprocessing as mp

from simulateur import Sim

from typing import Optional


def rc_control(log_queue: mp.Queue, throttle_command_buffer, turn_command_buffer, sim: Optional[Sim], r, initial_time):

    port_name = '/dev/ttyACM0'
    #port_name = '/dev/ttyUSB0'
    baud_rate = 115200

    #coeff_throttle = 0.25
    #coeff_stearing = 0.25

    # Use a breakpoint in the code line below to debug your script.
    #bus = serial.Serial(port=port_name, baudrate=baud_rate, parity=serial.PARITY_NONE,
                      #  stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=0.2)

    previous_time = time.time()

    throttle = 0
    stearing = 0
    slide = 0

   # while len(throttle_command_buffer) > 0 or len(turn_command_buffer) > 0:
    current_time = time.time()
    if len(throttle_command_buffer) > 0:
        """
        if current_time <= initial_time + throttle_command_buffer[0]['time']:
            throttle =  throttle_command_buffer[0]['value']
        else:
            throttle_command_buffer.pop(0)"""
        throttle = get_buffer(log_queue, throttle_command_buffer, current_time, initial_time)
    else:
        throttle = 0
        
    if len(turn_command_buffer) > 0:
        """
        if current_time <= initial_time + turn_command_buffer[0]['time']:
            stearing =  turn_command_buffer[0]['value']
        else:
            turn_command_buffer.pop(0)"""
        stearing = get_buffer(log_queue, turn_command_buffer, current_time, initial_time)
    else:
        stearing = 0

    if sim is not None:
        running, obs = sim.move(rotate=-stearing, before_move=throttle, translate_move=slide)
        r.set('x_position', obs[0])
        r.set('y_position', obs[1])
        r.set('direction', obs[2])
        return running

    return True

    #order = str(throttle) + ' ' + str(stearing) + ' ' + str(slide)
    #bus.write(('\n' + order).encode())

def get_buffer(log_queue: mp.Queue, buffer, current_time, initial_time):
    if len(buffer) == 0: return 0
    #log_queue.put(f"[rc_contrôle_process/rcContol/get_buffer] current time: {current_time}, buffer time: {buffer[0]['time']}, initial time: {initial_time}\n\n")
    if current_time <= initial_time + buffer[0]['time']: return buffer[0]['value']
    buffer.pop(0)
    #return 0
    return get_buffer(log_queue, buffer, current_time, initial_time)
