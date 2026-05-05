from numba import njit  # type: ignore[import-untyped]
from utils import *
from math import sqrt, atan2, pi, sin, cos, log, ceil

debug = False
delay = 0

# Vitesse de consigne pour les mouvements
forward_speed_command = 100
rotate_speed_command = 100

prev_time = time.time()


@njit(cache=True)
def compute_trajectory_core(
    x_target: float,
    y_target: float,
    prev_x: float,
    prev_y: float,
    inertie_coeff: float,
    delta_time: float,
    x_position: float,
    y_position: float,
    current_direction_deg: float,
    rotate_coeff: float,
    forward_coeff: float,
) -> tuple[float, float, float, float, float, float, float, list[Optional[float]]]:
    """Noyau de calcul compilé (numba) pour `generate_trajectory`.

    Regroupe plusieurs petits calculs pour réduire l'overhead d'appel et laisser
    numba optimiser un bloc plus gros.

    Retour:
    - target_distance
    - target_direction (radians)
    - delta_angle (radians)
    - current_time_direction
    - current_time_throttle
    - inertie_to_target_delta
    - sens (signe de delta_angle, ou 0 si delta_angle ~ 0)
    """

    logs: list[Optional[float]] = [None]

    # 1) Target distance + direction
    dx = x_target - x_position
    dy = y_target - y_position
    target_distance = sqrt(dx * dx + dy * dy)
    target_direction = atan2(dy, dx)

    # 2) Delta angle (alignement vers la cible)
    delta_angle = target_direction - current_direction_deg * pi / 180.0
    delta_angle = (delta_angle + pi) % (2 * pi) - pi
    delta_angle = -delta_angle

    # Signe (même logique que `calculate_sens`)
    abs_delta_angle = abs(delta_angle)
    sens = delta_angle / abs_delta_angle if abs_delta_angle > 1e-6 else 0.0

    # 3) Durée de rotation
    current_time_rotate = 0.0
    if abs(delta_angle) > 0.034:
        deg = abs(delta_angle) * 180.0 / pi
        current_time_rotate += (deg * rotate_coeff / 100.0 if deg > 1.0 else 0.0)

    #logs.append(current_time_rotate)

    # 4) Durée d'avance
    current_time_forward = current_time_rotate + (target_distance / 100.0 * forward_coeff)

    # 5) Heuristique d'inertie : prédit la position future du robot pour compenser l'inertie
    if (prev_x != x_position) or (prev_y != y_position):
        actual_speed = sqrt((x_position - prev_x) ** 2 + (y_position - prev_y) ** 2) / delta_time

        # Prédiction de la position avec inertie
        if actual_speed <= 0.1:
            inertie_dist_predicted = 0.0
            inertie_pos_predicted_x = x_position
            inertie_pos_predicted_y = y_position
        else:
            if inertie_coeff >= 1.0:
                total_dist = actual_speed
            else:
                n = ceil(log(0.1 / actual_speed) / log(inertie_coeff))
                total_dist = actual_speed * (inertie_coeff * (1.0 - inertie_coeff ** n) / (1.0 - inertie_coeff))

            current_direction_rad = current_direction_deg * pi / 180.0
            inertie_pos_predicted_x = x_position + total_dist * cos(current_direction_rad)
            inertie_pos_predicted_y = y_position + total_dist * sin(current_direction_rad)
            inertie_dist_predicted = total_dist

        # Calcul de la distance corrigée tenant compte de l'inertie
        sign_term = (target_distance - inertie_dist_predicted)
        inertie_to_target_delta = sqrt(
            (x_target - inertie_pos_predicted_x) ** 2 + (y_target - inertie_pos_predicted_y) ** 2
        ) * sign_term / abs(sign_term) if abs(sign_term) > 0 else target_distance
    else:
        inertie_to_target_delta = target_distance

    return (
        target_distance,
        target_direction,
        delta_angle,
        current_time_rotate,
        current_time_forward,
        inertie_to_target_delta,
        sens,
        logs
    )

def generate_trajectory(
    logger: LoggerAPI,
    process_name: ProcessNames,
    target_pos: Position,
    prev_pos: Position,
    delta_time: float,
    robot_position: Position,
    config: Config
) -> AllCommandBuffers:
    """Génère les buffers de commandes pour atteindre la cible.

    La logique est simple : une phase de rotation vers la cible, puis une phase d'avance.
    Les temps sont relatifs (en secondes) et seront interprétés par le contrôleur.
    """
    global prev_time
    if debug:
        logger.log(f"target: {target_pos.x} {target_pos.y}", process=process_name, level=LoggingLevel.DEBUG)

    forward_command_buffer: CommandBuffer = []
    translate_command_buffer: CommandBuffer = []
    rotate_command_buffer: CommandBuffer = []

    prev_x, prev_y = prev_pos.x, prev_pos.y
    (
        target_distance,
        target_direction,
        delta_angle,
        current_time_rotate,
        current_time_forward,
        inertie_to_target_delta,
        sens,
        logs
    ) = compute_trajectory_core(
        float(target_pos.x),
        float(target_pos.y),
        float(prev_x),
        float(prev_y),
        1 - float(config.inertie_factor.forward),
        float(delta_time),
        float(robot_position.x),
        float(robot_position.y),
        float(robot_position.direction),
        float(config.movement_coeff.rotate),
        float(config.movement_coeff.forward),
    )

    """for log in logs:
        if log is not None: logger.log(str(float(log)), process=process_name, level=LoggingLevel.DEBUG)"""

    if debug:
        logger.log(f"""target_distance: {target_distance}
                          target_direction: {target_direction * 180 / pi}
                          target position: {target_pos.x, target_pos.y, target_pos.direction}
                          actual position: {robot_position.x, robot_position.y, robot_position.direction}
                          """, process=process_name, level=LoggingLevel.DEBUG)
    
    # Phase de rotation
    if abs(delta_angle) > 0.034:
        rotate_command_buffer.append(CommandBufferItem(finish_time=current_time_rotate, command=sens * rotate_speed_command))
    else:
        rotate_command_buffer.append(CommandBufferItem(finish_time=current_time_rotate, command=0))

    # Phase d'avance (initialement à 0)
    forward_command_buffer.append(CommandBufferItem(finish_time=current_time_rotate, command=0))

    #logger.log(str(inertie_to_target_delta), process=process_name, level=LoggingLevel.DEBUG)

    # Ajout de la commande d'avance si l'inertie le permet
    if inertie_to_target_delta >= 30 and target_distance >= 5:
        forward_command_buffer.append(CommandBufferItem(finish_time=current_time_forward, command=forward_speed_command))

    # Fin de rotation
    rotate_command_buffer.append(CommandBufferItem(finish_time=current_time_forward, command=0))

    return AllCommandBuffers(forward=forward_command_buffer, translate=translate_command_buffer, rotate=rotate_command_buffer)


