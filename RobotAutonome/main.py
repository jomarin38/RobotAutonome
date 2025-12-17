from rcControl import rc_control
import time
import redis
from pprint import pprint
from simulateur import Sim

from trajectoryCalculator import generate_trajectory

redis_host='localhost'
redis_port=6379
redis_db=0

r = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)


time.sleep(10)

x_target = 750
y_target = 780
direction_target = 0.0

sim = Sim(window_size=(1000, 1000), tick_rate=60)
running, obs = sim.reset((500, 500, 0))
sim.target_point = (x_target, y_target, direction_target)

r.set('x_position', obs[0])
r.set('y_position', obs[1])
r.set('direction', obs[2])

target_pos = sim.target_point
throttle_command_buffer, turn_command_buffer = generate_trajectory(*target_pos)

#print("\n===========throttle===========")
#pprint(throttle_command_buffer)

#print("\n===========turn===========")
#pprint(turn_command_buffer)

rc_control(throttle_command_buffer, turn_command_buffer, sim)


while True:
    print(f'POSITION FROM MAIN : {r.get('x_position')},{r.get('y_position')},{r.get('direction')}')
    target_pos = sim.target_point
    throttle_command_buffer, turn_command_buffer = generate_trajectory(*target_pos)
    rc_control(throttle_command_buffer, turn_command_buffer, sim)
    #time.sleep(1)
