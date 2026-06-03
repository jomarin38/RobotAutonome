from utils import *

def rc_control(
    logger: LoggerAPI,
    process_name: ProcessNames,
    commands_buffer: AllCommandBuffers,
    initial_time: float,
    use_control_data: ControlHandlerBase
) -> bool:
    """Applique les commandes (forward / rotate / translate) au robot.

    - Les commandes sont encodées sous forme de buffers temporels: chaque élément est
      un dict avec au minimum `time` (float) et `value` (consigne).
    - Si `sim` est fourni, on agit sur le simulateur et on publie la pose dans Redis.
    """

    translate = 0
    current_time = time.time()

    forward = get_buffer(logger, process_name, commands_buffer.forward, current_time, initial_time) if len(commands_buffer.forward) > 0 else 0.0
    rotate_command = get_buffer(logger, process_name, commands_buffer.rotate, current_time, initial_time) if len(commands_buffer.rotate) > 0 else 0.0

    running = send_command(use_control_data, Command(rotate=-rotate_command, forward=forward, translate=translate))
    return running

def get_buffer(
    logger: LoggerAPI,
    process_name: ProcessNames,
    command_buffer: CommandBuffer,
    current_time: float,
    initial_time: float,
) -> float:
    """Retourne la consigne courante pour un buffer temporel.

    Logique inchangée: on consomme (`pop(0)`) les items dont le temps est dépassé.
    """
    if len(command_buffer) == 0:
        return 0
    if current_time <= initial_time + command_buffer[0].finish_time:
        return command_buffer[0].command
    command_buffer.pop(0)
    return get_buffer(logger, process_name, command_buffer, current_time, initial_time)
