from .utils import *


def get_active_command(
    process_name: ProcessNames,
    buffer: CommandBuffer,
    current_time: float,
    buffer_start_time: float,
) -> float:
    """Retourne la consigne courante depuis un buffer temporel (récursif).

    Consomme (pop) les items dont le temps de fin (finish_time) est dépassé par rapport
    au temps courant, puis retourne la valeur du premier item encore actif.
    Retourne 0.0 si le buffer est vide ou tous les items sont expirés.

    Args:
        process_name: Nom du processus appelant.
        buffer: Buffer temporel de commandes.
        current_time: Temps courant (en secondes).
        buffer_start_time: Temps auquel le buffer a commencé à être appliqué.

    Returns:
        La valeur de commande du premier item actif, ou 0.0.
    """
    if len(buffer) == 0:
        return 0.0
    if current_time <= buffer_start_time + buffer[0].finish_time:
        return buffer[0].command
    buffer.pop(0)
    return get_active_command(process_name, buffer, current_time, buffer_start_time)


def rc_control(
    process_name: ProcessNames,
    command_buffers: AllCommandBuffers,
    buffer_start_time: float,
    driver: Driver,
) -> bool:
    """Applique la commande courante de chaque axe au robot.

    Lit la consigne active dans chaque buffer (forward / translate / rotate) selon
    l'horodatage, puis envoie la commande résultante via le driver de contrôle.

    None sur un axe = buffer vide, l'inertie s'applique naturellement.
    """
    current_time = time.time()

    # None si le buffer est vide : aucune consigne, l'inertie décroît librement
    forward_command = (
        get_active_command(process_name, command_buffers.forward, current_time, buffer_start_time)
        if len(command_buffers.forward) > 0 else None
    )
    translate_command = (
        get_active_command(process_name, command_buffers.translate, current_time, buffer_start_time)
        if len(command_buffers.translate) > 0 else None
    )
    rotate_command = (
        get_active_command(process_name, command_buffers.rotate, current_time, buffer_start_time)
        if len(command_buffers.rotate) > 0 else None
    )

    running = driver.send_command(
        Command(
            rotate=-rotate_command if rotate_command else None,
            forward=forward_command,
            translate=translate_command,
        ),
    )
    return running
