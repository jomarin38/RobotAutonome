def init():
    global x_position, y_position, direction
    x_position = 1000
    y_position = 1000
    direction = 0

    global throttle_command_buffer, turn_command_buffer
    throttle_command_buffer = []
    turn_command_buffer = []

    global x_target, y_target
    x_target = 1000
    y_target = 1000
