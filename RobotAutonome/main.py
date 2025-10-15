from rcControl import rc_control
import time
import redis
from pprint import pprint

from trajectoryCalculator import generate_trajectory

redis_host='localhost'
redis_port=6379
redis_db=0

r = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)


time.sleep(10)

x_target = 1500
y_target = 1500
direction_target = 0.0

throttle_command_buffer, turn_command_buffer = generate_trajectory(x_target, y_target, direction_target)

print("\n===========throttle===========")
pprint(throttle_command_buffer)

print("\n===========turn===========")
pprint(turn_command_buffer)

rc_control(throttle_command_buffer, turn_command_buffer)

"""
while True:
    print(f'POSITION FROM MAIN : {r.get('x_position')},{r.get('y_position')},{r.get('direction')}')
    throttle_command_buffer, turn_command_buffer = generate_trajectory(x_target, y_target, direction_target)
    rc_control(throttle_command_buffer, turn_command_buffer)
    time.sleep(1)"""
