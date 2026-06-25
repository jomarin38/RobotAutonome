import time
from math import ceil, log, cos, sqrt, pi, atan2, sin
from typing import override

from numba import njit

from src.utils import Position, AllCommandBuffers, CommandBuffer, CommandBufferItem, logger
from src.trajectories.trajectory_strategy import TrajectoryStrategy

DEBUG = False

MAX_FORWARD_SPEED: float = 100.0
MAX_ROTATE_SPEED: float = 100.0

@njit(cache=True)
def compute_trajectory_with_rotation(
    tick_interval: float,
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
) -> tuple[float, float, float, float, float, float, float]:
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

    # 4) Durée d'avance
    #current_time_forward = current_time_rotate + (target_distance / 100.0 * forward_coeff)
    forward_command_speed = min(MAX_FORWARD_SPEED, max(abs(dy), 1e-4) * forward_coeff / tick_interval)
    current_time_forward = target_distance / forward_command_speed * forward_coeff

    # 5) Heuristique d'inertie : prédit la position future du robot pour compenser l'inertie
    if (prev_x, prev_y) != (x_position, y_position):
        actual_speed = sqrt((x_position - prev_x) ** 2 + (y_position - prev_y) ** 2) / delta_time

        # Prédiction de la position avec inertie
        if actual_speed <= 1e-4:
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
        sens
    )

class TurnThenMoveStrategy(TrajectoryStrategy):
    """Stratégie classique : rotation d'abord, puis avance (séquentiel).

    Cette stratégie tourne d'abord le robot pour l'aligner avec la cible,
    puis l'avance tout droit sans translation latérale.
    """

    @override
    def compute(
        self,
        target_position: Position,
        robot_position: Position,
        previous_position: Position,
        elapsed_time: float,
    ) -> AllCommandBuffers:
        """Implémentation avec rotation séquentielle puis avance."""
        forward_buffer: CommandBuffer = []
        translate_buffer: CommandBuffer = []
        rotate_buffer: CommandBuffer = []

        prev_x = previous_position.x
        prev_y = previous_position.y

        current_time = time.time()
        tick_interval = current_time - self.prev_time
        self.prev_time = current_time

        (
            target_distance,
            target_direction,
            delta_angle,
            current_time_rotate,
            current_time_forward,
            inertie_to_target_delta,
            sens,
        ) = compute_trajectory_with_rotation(
            tick_interval,
            float(target_position.x),
            float(target_position.y),
            float(prev_x),
            float(prev_y),
            float(self.config.inertia_factor.forward),
            float(elapsed_time),
            float(robot_position.x),
            float(robot_position.y),
            float(robot_position.direction),
            float(self.config.movement_coeff.rotate),
            float(self.config.movement_coeff.forward),
        )

        # Construction des buffers : d'abord rotation, puis avance
        # Rotation d'abord si l'angle delta est significatif
        if abs(delta_angle) > 0.034:
            rotate_buffer.append(CommandBufferItem(
                finish_time=current_time_rotate,
                command=sens * 100.0,
            ))
            forward_buffer.append(CommandBufferItem(finish_time=current_time_rotate, command=0))

        # Puis avance après la rotation (décalée temporellement)
        if inertie_to_target_delta > 0:
            forward_buffer.append(CommandBufferItem(
                finish_time=current_time_forward,
                command=100.0,
            ))

        if DEBUG:
            logger.debug(
                f"""Stratégie {self.strategy_name}:
                   target position : {target_position.x} {target_position.y}
                   target distance : {target_distance}
                   delta angle : {delta_angle}
                   inertie_to_target_delta : {inertie_to_target_delta}
                   buffer rotate  : {rotate_buffer}
                   buffer forward : {forward_buffer}"""
            )

        return AllCommandBuffers(
            forward=forward_buffer,
            translate=translate_buffer,
            rotate=rotate_buffer,
        )

    @property
    @override
    def strategy_name(self) -> str:
        return "TurnThenMove"
