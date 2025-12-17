import globals

import time

import serial

from simulateur import Sim

from typing import Optional

import redis
redis_host='localhost'
redis_port=6379
redis_db=0

r = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)



def rc_control(throttle_command_buffer, turn_command_buffer, sim: Optional[Sim]):

    port_name = '/dev/ttyACM0'
    #port_name = '/dev/ttyUSB0'
    baud_rate = 115200

    #coeff_throttle = 0.25
    #coeff_stearing = 0.25

    coeff_throttle = 1.0
    coeff_stearing = 1.0

    # Use a breakpoint in the code line below to debug your script.
    #bus = serial.Serial(port=port_name, baudrate=baud_rate, parity=serial.PARITY_NONE,
                      #  stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=0.2)

    previous_time = time.time()

    throttle = 0
    stearing = 0
    slide = 0

    initial_time = time.time()

    while len(throttle_command_buffer) > 0 or len(turn_command_buffer) > 0:
        current_time = time.time()
        if len(throttle_command_buffer) > 0:
            if initial_time + throttle_command_buffer[0]['time'] > current_time:
                throttle =  throttle_command_buffer[0]['value'] * coeff_throttle
            else:
                throttle_command_buffer.pop(0)
        else:
            throttle = 0
        if len(turn_command_buffer) > 0:
            if initial_time + turn_command_buffer[0]['time'] > current_time:
                stearing =  turn_command_buffer[0]['value'] * coeff_stearing
            else:
                turn_command_buffer.pop(0)
        else:
            stearing = 0



        if sim:
            dt = sim.get_dt()
            _, obs = sim.move(rotate=-stearing/90, before_move=throttle/38, translate_move=slide/100, dt=dt)
            r.set('x_position', obs[0])
            r.set('y_position', obs[1])
            r.set('direction', obs[2])

        #order = str(throttle) + ' ' + str(stearing) + ' ' + str(slide)
        #bus.write(('\n' + order).encode())
        #print(f"command :  {str(order)}")
        #time.sleep(0.1)


