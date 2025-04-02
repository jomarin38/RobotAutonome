import globals

import time

import serial

def rc_control():

    port_name = '/dev/ttyACM0'
    baud_rate = 115200

    #coeff_throttle = 0.25
    #coeff_stearing = 0.25

    coeff_throttle = 1.0
    coeff_stearing = 1.0

    # Use a breakpoint in the code line below to debug your script.
    bus = serial.Serial(port=port_name, baudrate=baud_rate, parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=0.2)

    previous_time = time.time()

    throttle = 0
    stearing = 0

    while True:
        current_time = time.time()
        if (len(globals.throttle_command_buffer)>0):
            if globals.throttle_command_buffer[0]['time']>current_time:
                throttle =  globals.throttle_command_buffer[0]['value'] * coeff_throttle
            else:
                globals.throttle_command_buffer.pop(0)
        else:
            throttle = 0
        if (len(globals.turn_command_buffer)>0):
            if globals.turn_command_buffer[0]['time']>current_time:
                stearing =  globals.turn_command_buffer[0]['value'] * coeff_stearing
            else:
                globals.turn_command_buffer.pop(0)
        else:
            stearing = 0
        bus.write((str(throttle) + ' ' + str(stearing) + '\n').encode())
        print('command : ' + str(throttle) + ' ' + str(stearing))
        time.sleep(0.1)


