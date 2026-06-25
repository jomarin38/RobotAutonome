from typing import override

from numba import njit

from src.utils import Position, AllCommandBuffers, CommandBuffer, CommandBufferItem, SimPoint, Color, logger
from src.trajectories.trajectory_strategy import TrajectoryStrategy

DEBUG = False

MAX_FORWARD_SPEED: float = 100.0
MAX_TRANSLATE_SPEED: float = 100.0

@njit(cache=True)
def compute_inertia_coast_delta(
        previous_pos: float,
        current_pos: float,
        elapsed_time: float,
        inertia_factor: float,
        tick_interval: float,
        target_position: float,
) -> float:
    """Calcule le delta signé entre la position d'arrêt prédite par inertie et la cible.

    Retourne une valeur :
    - Positive  → le robot doit encore pousser (l'inertie ne suffit pas à atteindre la cible).
    - Zéro      → l'inertie arrêtera le robot exactement sur la cible.
    - Négative  → l'inertie dépasse la cible, arrêter de pousser.

    Formule de la distance totale de glissement (série géométrique) :
        coast_distance = measured_speed * tick_interval / (1 - inertia_factor)
    """
    if previous_pos == current_pos or elapsed_time <= 0.0:
        return abs(target_position - current_pos)

    measured_speed = (current_pos - previous_pos) / elapsed_time

    if abs(measured_speed) < 1e-4:
        return abs(target_position - current_pos)

    if inertia_factor <= 0.0 or inertia_factor >= 1.0:
        return abs(target_position - current_pos)

    coast_distance = measured_speed * tick_interval / (1.0 - inertia_factor)
    predicted_stop_pos = current_pos + coast_distance

    direction_sign = 1.0 if target_position > current_pos else -1.0
    return (target_position - predicted_stop_pos) * direction_sign


@njit(cache=True)
def compute_trajectory_independent_axes(
        tick_interval: float,
        x_target: float,
        y_target: float,
        prev_x: float,
        prev_y: float,
        inertia_factor_fwd: float,
        inertia_factor_tra: float,
        elapsed_time: float,
        x_pos: float,
        y_pos: float,
        forward_scale: float,
        translate_scale: float,
) -> tuple[float, float, float, float, float, float, float, float, float, float]:
    """Noyau de calcul Numba (JIT) pour generate_trajectory.

    Calcule les vitesses, durées et deltas d'inertie pour les axes forward et translate.

    Retour (dans l'ordre) :
        abs_dx, abs_dy              : distances absolues à la cible
        forward_finish_time         : temps de fin pour le buffer forward (s)
        translate_finish_time       : temps de fin pour le buffer translate (s)
        forward_command_speed       : vitesse de consigne forward
        translate_command_speed     : vitesse de consigne translate
        x_coast_delta               : delta inertie signé sur l'axe X
        y_coast_delta               : delta inertie signé sur l'axe Y
        x_dir                       : signe de la direction vers la cible en X (+1 / -1)
        y_dir                       : signe de la direction vers la cible en Y (+1 / -1)
    """

    dx = x_target - x_pos
    dy = y_pos - y_target

    translate_command_speed = min(MAX_TRANSLATE_SPEED, max(abs(dx), 1e-4) * translate_scale / tick_interval)
    translate_finish_time = abs(dx) / translate_command_speed * translate_scale

    forward_command_speed = min(MAX_FORWARD_SPEED, max(abs(dy), 1e-4) * forward_scale / tick_interval)
    forward_finish_time = abs(dy) / forward_command_speed * forward_scale

    x_dir = dx / max(abs(dx), 1e-4)
    y_dir = dy / max(abs(dy), 1e-4)

    x_coast_delta = compute_inertia_coast_delta(prev_x, x_pos, elapsed_time, inertia_factor_tra, tick_interval,
                                                x_target)
    y_coast_delta = compute_inertia_coast_delta(prev_y, y_pos, elapsed_time, inertia_factor_fwd, tick_interval,
                                                y_target)

    return (
        abs(dx),
        abs(dy),
        forward_finish_time,
        translate_finish_time,
        forward_command_speed,
        translate_command_speed,
        x_coast_delta,
        y_coast_delta,
        x_dir,
        y_dir,
    )

class MixedMovementStrategy(TrajectoryStrategy):
    """Stratégie moderne : mouvement mixte simultané.

    Cette stratégie calcule les mouvements d'avance et de translation indépendamment
    et les exécute simultanément pour un mouvement plus naturel et rapide.
    """

    def __init__(self, config) -> None:
        super().__init__(config)
        self._sim_points: list[SimPoint] = []

    @property
    def sim_points(self) -> list[SimPoint]:
        """Points de debug pour l'affichage dans le simulateur."""
        return self._sim_points

    @override
    def compute(
        self,
        target_position: Position,
        robot_position: Position,
        previous_position: Position,
        elapsed_time: float,
    ) -> AllCommandBuffers:
        """Implémentation avec axes indépendants (forward + translate simultanés)."""

        forward_buffer: CommandBuffer = []
        translate_buffer: CommandBuffer = []
        rotate_buffer: CommandBuffer = []

        prev_x = previous_position.x
        prev_y = previous_position.y

        # Reset des points de debug
        self._sim_points = []

        (
            abs_dx,
            abs_dy,
            forward_finish_time,
            translate_finish_time,
            forward_command_speed,
            translate_command_speed,
            x_coast_delta,
            y_coast_delta,
            x_dir,
            y_dir,
        ) = compute_trajectory_independent_axes(
            float(self.config.rc_control_dt),
            float(target_position.x),
            float(target_position.y),
            float(prev_x),
            float(prev_y),
            float(self.config.inertia_factor.forward),
            float(self.config.inertia_factor.translate),
            float(elapsed_time),
            float(robot_position.x),
            float(robot_position.y),
            float(self.config.movement_coeff.forward),
            float(self.config.movement_coeff.translate),
        )

        # Ajout d'un point de debug pour l'inertie
        self._sim_points.append(SimPoint(
            name="target_point",
            position=Position(
                x=target_position.x,
                y=target_position.y,
                direction=0,
            ),
            color=Color(red=255, green=0, blue=0),
            radius=8,
        ))

        # Construction des buffers simultanément (mouvement mixte)
        if x_coast_delta > 0:
            translate_buffer.append(CommandBufferItem(
                finish_time=translate_finish_time,
                command=translate_command_speed * x_dir,
            ))

        if y_coast_delta > 0:
            forward_buffer.append(CommandBufferItem(
                finish_time=forward_finish_time,
                command=forward_command_speed * y_dir,
            ))

        if DEBUG:
            logger.debug(
                f"""Stratégie {self.strategy_name}:
                   target position : {target_position.x} {target_position.y}
                   distance X     : {abs_dx}
                   distance Y     : {abs_dy}
                   direction X    : {x_dir}
                   direction Y    : {y_dir}
                   delta inertie X: {x_coast_delta}
                   delta inertie Y: {y_coast_delta}
                   buffer forward : {forward_buffer}
                   buffer translate: {translate_buffer}"""
            )

        return AllCommandBuffers(
            forward=forward_buffer,
            translate=translate_buffer,
            rotate=rotate_buffer,
        )

    @property
    @override
    def strategy_name(self) -> str:
        return "MixedMovement"
