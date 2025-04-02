from missionPlanner import generate_mission
from positionDisplay import display_position
#from positionUpdater import update_position
from Aruco_detection import main
from rcControl import rc_control
import globals
import threading
import time

from trajectoryCalculator import generate_trajectory

globals.init()

"""
current_time = time.time()
globals.throttle_command_buffer.append({'time':current_time+2, 'value':0})
globals.throttle_command_buffer.append({'time':current_time+7, 'value':50})
globals.throttle_command_buffer.append({'time':current_time+20, 'value':-50})

#globals.turn_command_buffer.append({'time':current_time+2, 'value':0})
#globals.turn_command_buffer.append({'time':current_time+3, 'value':45})

rc_control_thread = threading.Thread(target=rc_control)
rc_control_thread.start()
"""

position_updater_thread = threading.Thread(target=main)
position_updater_thread.start()

#time.sleep(20)

globals.x_position = 0.0
globals.y_position = 0.0

globals.x_target = 1500.0
globals.y_target = 1000.0

trajectory_calculator_thread = threading.Thread(target=generate_trajectory)
trajectory_calculator_thread.start()
rc_control_thread = threading.Thread(target=rc_control)
rc_control_thread.start()



"""

trajectory_calculator_thread = threading.Thread(target=generate_trajectory)

mission_planner_thread = threading.Thread(target=generate_mission)

rc_control_thread = threading.Thread(target=rc_control)

#position_updater_thread.start()
trajectory_calculator_thread.start()
mission_planner_thread.start()
rc_control_thread.start()

display_position()
"""