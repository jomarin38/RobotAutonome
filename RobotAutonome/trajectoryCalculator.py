import time
from numba import njit
import pprint
import multiprocessing as mp

from math import sqrt, pow, atan2, pi, sin, cos, log, ceil
debug = False
delay = 0

#coeff_dist = 0.38
#coeff_angle = 1.105

vitesse = 100
direction_vitesse = 100

prev_time = time.time()

@njit()
def calculate_targets(x_target, x_position, y_target,  y_position):
    target_distance = sqrt((x_target-x_position)**2 + (y_target-y_position)**2)
    target_direction = atan2(y_target - y_position,
                             x_target - x_position)
    return target_distance, target_direction

@njit()
def calculate_delta_angle(target_direction, current_direction):
    delta_angle = target_direction - current_direction * pi/180.0
    delta_angle = (delta_angle + pi) % (2 * pi) - pi
    return -delta_angle

@njit()
def calculate_current_time_direction(current_time_direction, delta_angle, coeff_angle):
    deg = abs(delta_angle) * 180 / pi
    return current_time_direction + (deg * coeff_angle / 100 if deg > 1 else 0)

@njit()
def calculate_sens(delta_angle):
    abs_delta_angle = abs(delta_angle)
    return delta_angle / abs_delta_angle if abs_delta_angle > 1e-6 else 0

@njit()
def calculate_current_time_throttle(current_time_throttle, target_distance, coeff_dist):
    return current_time_throttle + (target_distance / 100 * coeff_dist)

@njit
def predict_pos_with_inertie(x_pos, y_pos, move_speed, current_direction, inertie_coeff):

    if move_speed <= 0.1:
        return x_pos, y_pos

    if inertie_coeff >= 1:
        # sécurité pour éviter boucle infinie
        total_dist = move_speed
    else:
        
        n = ceil(log(0.1 / move_speed) / log(inertie_coeff))
        total_dist = move_speed * (inertie_coeff * (1 - inertie_coeff**n) / (1 - inertie_coeff))

    new_x = x_pos + total_dist * cos(current_direction)
    new_y = y_pos + total_dist * sin(current_direction)

    return new_x, new_y

def generate_trajectory(log_queue: mp.Queue, x_target: int, y_target: int, direction_target: float, prev_pos: list[int], inertie_coeff: float, delta_time: float, x_position: int, y_position: int, current_direction: float, coeff_angle: float, coeff_dist: float):
    global prev_time
    if debug:
        log_queue.put(f"target: {x_target} {y_target}")

    throttle_command_buffer = []
    turn_command_buffer = []

    target_distance, target_direction = calculate_targets(x_target, x_position, y_target, y_position)

    if debug:
        log_queue.put(f"""target_distance: {target_distance}
                          target_direction: {target_direction * 180 / pi}
                          target position: {x_target, y_target, direction_target}
                          actual position: {x_position, y_position, current_direction}""")

    current_time = 0.0 + delay
    current_time_throttle = current_time_direction = current_time
    
    delta_angle = calculate_delta_angle(target_direction, current_direction)
    
    if debug:
        log_queue.put(f"turn command: {delta_angle * 180 / pi}")
    
    current_time_direction = 0
    if abs(delta_angle) > 0.034:
        current_time_direction = calculate_current_time_direction(current_time_direction, delta_angle, coeff_angle)
        sens = calculate_sens(delta_angle)
        turn_command_buffer.append({'time': current_time_direction,
                                            'value': sens * direction_vitesse})
    else:
        turn_command_buffer.append({'time': current_time_direction,
                                            'value': 0})
        
    inertie_pos_predicted = predict_pos_with_inertie(x_position, y_position, vitesse, current_direction, inertie_coeff)
    current_time_throttle = current_time_direction
    throttle_command_buffer.append({'time': current_time_throttle,
                                        'value': 0})
    
    current_time_throttle = calculate_current_time_throttle(current_time_throttle, target_distance, coeff_dist)
    new_target_dist = calculate_targets(x_target, inertie_pos_predicted[0], y_target, inertie_pos_predicted[1])[0]
    #log_queue.put(inertie_dist)
    if new_target_dist >= 600 or True:
        throttle_command_buffer.append({'time': current_time_throttle,
                                            'value': vitesse})
    else:
        log_queue.put("stop !")

    turn_command_buffer.append({'time': current_time_throttle,
                                        'value': 0})


    """
    current_time_throttle += (direction_target - direction) * 180 / pi / 100 * coeff_angle
    turn_command_buffer.append({'time': current_time_throttle,
                                        'value': vitesse})

    current_time_throttle += 0.1
    turn_command_buffer.append({'time': current_time_throttle,
                                        'value': -vitesse})
    """
    return throttle_command_buffer, turn_command_buffer


