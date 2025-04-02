import globals
import time
from math import sqrt, pow, atan2, pi
debug = True
delay = 1

coeff_dist = 2.2 / 1.94 * 5.0 / 6.0
coeff_angle = 1.68

def generate_trajectory():
    running = True
    while running:
        if debug:
            print('target : '+str(globals.x_target) + ' ' + str(globals.y_target))

        globals.throttle_command_buffer.clear()
        globals.turn_command_buffer.clear

        target_distance = sqrt(pow(globals.x_target-globals.x_position,2) +
                               pow(globals.y_target-globals.y_position,2))
        target_direction = atan2(globals.y_target - globals.y_position,
                                 globals.x_target - globals.x_position)

        if debug:
            print('target_distance : ' + str(target_distance))
            print('target_direction :' + str(target_direction * 180 / pi))
            print('actual position : {},{}'.format(globals.x_position, globals.y_position))

        current_time = time.time() + delay
        #globals.throttle_command_buffer.append({'time': current_time + 10, 'value': 100})
        delta_angle = target_direction - globals.direction
        turn_move_duration = delta_angle*180/pi/100 * coeff_angle
        globals.turn_command_buffer.append({'time': current_time ,
                                            'value': 0})
        globals.turn_command_buffer.append({'time': current_time + turn_move_duration,
                                            'value': 100})

        forward_move_duration = target_distance/100 * coeff_dist
        globals.throttle_command_buffer.append({'time': current_time,
                                            'value': 0})
        globals.throttle_command_buffer.append({'time': current_time + turn_move_duration,
                                            'value': 0})
        globals.throttle_command_buffer.append({'time': current_time + turn_move_duration + forward_move_duration,
                                                'value': 100})

        #qtime.sleep(20)

        #Uncomment if you want to compute only one trajectory
        running = False

