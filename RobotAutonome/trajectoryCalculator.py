import time

from math import sqrt, pow, atan2, pi
debug = True
delay = 1

import redis
redis_host='localhost'
redis_port=6379
redis_db=0

r = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)

coeff_dist = 0.38
coeff_angle = 1.105

vitesse = 100
direction_vitesse = 100

def generate_trajectory(x_target, y_target, direction_target):

    if debug:
        print('target : '+str(x_target) + ' ' + str(y_target))

    throttle_command_buffer = []
    turn_command_buffer = []

    x_position = float(r.get('x_position'))
    y_position = float(r.get('y_position'))

    target_distance = sqrt(pow(x_target-x_position,2) +
                           pow(y_target-y_position,2))
    target_direction = atan2(y_target - y_position,
                             x_target - x_position)

    target_direction = -target_direction

    if target_direction<0:
        target_direction += 2 * pi

    if debug:
        print()
        print('target_distance : ' + str(target_distance))
        print('target_direction :' + str(target_direction * 180 / pi))
        print('actual position : {},{}'.format(x_position, y_position))

    current_time = 0.0 + delay
    current_time_throttle, current_time_direction = current_time, current_time
    #globals.throttle_command_buffer.append({'time': current_time + 10, 'value': 100})
    delta_angle = (target_direction - float(r.get('direction')) * pi/180.0)
    print(delta_angle / (pi / 180))
    delta_angle = -(2*pi - delta_angle) if delta_angle > pi else delta_angle
    print(delta_angle/(pi/180))
    turn_move_duration = abs(delta_angle * 180 / pi / 100 * coeff_angle)
    turn_command_buffer.append({'time': current_time ,
                                        'value': 0})
    current_time_direction += turn_move_duration
    sens = delta_angle / abs(delta_angle)
    turn_command_buffer.append({'time': current_time_direction,
                                        'value': sens * direction_vitesse})
    current_time_direction += 0.1
    turn_command_buffer.append({'time': current_time_direction,
                                        'value': -sens * direction_vitesse})
    direction = target_direction

    forward_move_duration = target_distance/100 * coeff_dist
    throttle_command_buffer.append({'time': current_time,
                                        'value': 0})
    current_time_throttle = current_time_direction
    throttle_command_buffer.append({'time': current_time_throttle,
                                        'value': 0})
    current_time_throttle += forward_move_duration
    throttle_command_buffer.append({'time': current_time_throttle,
                                            'value': vitesse})
    #current_time_throttle += 0.15
    #globals.throttle_command_buffer.append({'time': current_time_throttle,
    #                                        'value': -vitesse})

    turn_command_buffer.append({'time': current_time_throttle,
                                        'value': 0})



    current_time_throttle += (direction_target - direction) * 180 / pi / 100 * coeff_angle
    turn_command_buffer.append({'time': current_time_throttle,
                                        'value': vitesse})

    current_time_throttle += 0.1
    turn_command_buffer.append({'time': current_time_throttle,
                                        'value': -vitesse})

    return throttle_command_buffer, turn_command_buffer


