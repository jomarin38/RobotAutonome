import time
from math import cos, sqrt, pi, atan2, sin
from typing import override

from loguru import logger
from numba import njit

from src.utils import Position, AllCommandBuffers, CommandBuffer, CommandBufferItem
from ..trajectory_strategy import TrajectoryStrategy

DEBUG = False

MAX_FORWARD_SPEED: float = 100.0
MAX_ROTATE_SPEED: float = 100.0


@njit(cache=True)
def compute_trajectory_core(
    dt: float,
    x_target: float,
    y_target: float,
    x_mesure: float,
    y_mesure: float,
    inertia_factor: float,
    dt_mesure: float,
    x_position: float,
    y_position: float,
    current_direction_deg: float,
    rotate_scale: float,
    forward_scale: float,
) -> tuple[float, float, float, float, float, float, float, float]:
    """Noyau de calcul compilé (numba) pour la stratégie TurnThenMove.

    Regroupe plusieurs petits calculs pour réduire l'overhead d'appel et laisser
    numba optimiser un bloc plus gros.

    Retour (dans l'ordre) :
    - target_distance        : distance euclidienne jusqu'à la cible
    - target_direction       : angle vers la cible (radians)
    - delta_angle            : écart angulaire à corriger (radians)
    - current_time_rotate    : durée estimée de la phase de rotation (secondes)
    - forward_command_speed  : vitesse de consigne pour l'avance
    - current_time_forward   : durée totale rotation + avance (secondes)
    - inertie_to_target_delta: distance corrigée tenant compte de l'inertie
    - angle_sign                   : signe de delta_angle (+1 / -1 / 0)
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

    # Signe (même logique que `calculate_angle_sign`)
    abs_delta_angle = abs(delta_angle)
    angle_sign = delta_angle / abs_delta_angle if abs_delta_angle > 1e-6 else 0.0

    # 3) Durée de rotation
    current_time_rotate = 0.0
    deg = abs(delta_angle) * 180.0 / pi
    if deg > 5:
        current_time_rotate = deg * rotate_scale / 100.0 if deg > 1.0 else 0.0

    # 4) Durée d'avance
    forward_command_speed = 0
    current_time_forward = current_time_rotate
    if target_distance >= 10:
        forward_command_speed = min(MAX_FORWARD_SPEED, max(abs(target_distance), 1e-4) * forward_scale / dt)
        current_time_forward = current_time_rotate + target_distance / forward_command_speed * forward_scale

    # 5) Heuristique d'inertie : prédit la position future du robot pour compenser l'inertie
    if (x_mesure, y_mesure) != (x_position, y_position):
        actual_speed = sqrt((x_position - x_mesure) ** 2 + (y_position - y_mesure) ** 2) / dt_mesure

        # Prédiction de la position avec inertie
        if actual_speed <= 1e-4:
            inertie_dist_predicted = 0.0
            inertie_pos_predicted_x = x_position
            inertie_pos_predicted_y = y_position
        else:
            if inertia_factor >= 1.0:
                total_dist = actual_speed
            else:
                total_dist = actual_speed * dt / (1.0 - inertia_factor)

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
        forward_command_speed,
        current_time_forward,
        inertie_to_target_delta,
        angle_sign
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
        measured_position: Position,
        dt_mesure: float,
    ) -> AllCommandBuffers:
        """Implémentation avec rotation séquentielle puis avance."""
        forward_buffer: CommandBuffer = []
        translate_buffer: CommandBuffer = []
        rotate_buffer: CommandBuffer = []

        x_mesure = measured_position.x
        y_mesure = measured_position.y

        current_time = time.time()
        dt = current_time - self.previous_time
        self.previous_time = current_time

        (
            target_distance,
            target_direction,
            delta_angle,
            current_time_rotate,
            forward_command_speed,
            current_time_forward,
            inertie_to_target_delta,
            angle_sign,
        ) = compute_trajectory_core(
            dt,
            float(target_position.x),
            float(target_position.y),
            float(x_mesure),
            float(y_mesure),
            float(self.config.inertia_factor.forward),
            float(dt_mesure),
            float(robot_position.x),
            float(robot_position.y),
            float(robot_position.direction),
            float(self.config.movement_coeff.rotate),
            float(self.config.movement_coeff.forward),
        )

        # Construction des buffers : d'abord rotation, puis avance
        # Rotation d'abord si l'angle delta est significatif
        
        rotate_buffer.append(CommandBufferItem(
            finish_time=current_time_rotate,
            command=angle_sign * 100.0,
        ))
        forward_buffer.append(CommandBufferItem(finish_time=current_time_rotate, command=0))

        # Puis avance après la rotation (décalée temporellement)
        if inertie_to_target_delta > 0 or True:
            forward_buffer.append(CommandBufferItem(
                finish_time=current_time_forward,
                command=forward_command_speed,
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
