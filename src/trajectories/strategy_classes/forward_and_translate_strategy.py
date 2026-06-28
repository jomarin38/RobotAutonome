import time
from typing import override

from loguru import logger
from numba import njit

from src.utils import Position, AllCommandBuffers, CommandBuffer, CommandBufferItem, SimPoint, Color
from ..trajectory_strategy import TrajectoryStrategy

DEBUG = False

MAX_FORWARD_SPEED: float = 100.0
MAX_TRANSLATE_SPEED: float = 100.0


@njit(cache=True, fastmath=True)
def compute_inertia_drift_delta(
        previous_position: float,
        current_position: float,
        dt_mesure: float,
        inertia_factor: float,
        dt: float,
        target_position: float,
) -> float:
    """Calcule le delta signé entre la position d'arrêt prédite par inertie et la cible.

    Retourne une valeur :
    - Positive  → le robot doit encore pousser (l'inertie ne suffit pas à atteindre la cible).
    - Zéro      → l'inertie arrêtera le robot exactement sur la cible.
    - Négative  → l'inertie dépasse la cible, arrêter de pousser.

    Formule de la distance totale de dérive (série géométrique) :
        inertia_drift_distance = measured_speed * dt / (1 - inertia_factor)
    """
    if previous_position == current_position or dt_mesure <= 0.0:
        return abs(target_position - current_position)

    measured_speed = (current_position - previous_position) / dt_mesure

    if abs(measured_speed) < 1e-4:
        return abs(target_position - current_position)

    if inertia_factor <= 0.0 or inertia_factor >= 1.0:
        return abs(target_position - current_position)

    inertia_drift_distance = measured_speed * dt / (1.0 - inertia_factor)
    predicted_stop_pos = current_position + inertia_drift_distance

    direction_sign = 1.0 if target_position > current_position else -1.0
    return (target_position - predicted_stop_pos) * direction_sign


@njit(cache=True, fastmath=True)
def compute_trajectory_core(
        dt: float,
        x_target: float,
        y_target: float,
        x_mesure: float,
        y_mesure: float,
        inertia_factor_forward: float,
        inertia_factor_translate: float,
        dt_mesure: float,
        x_position: float,
        y_position: float,
        forward_scale: float,
        translate_scale: float,
) -> tuple[float, float, float, float, float, float, float, float, float, float]:
    """Noyau de calcul Numba (JIT) pour generate_trajectory.

    Calcule les vitesses, durées et deltas de dérive d'inertie pour les axes forward et translate.

    Retour (dans l'ordre) :
        abs_dx, abs_dy              : distances absolues à la cible
        forward_finish_time         : temps de fin pour le buffer forward (s)
        translate_finish_time       : temps de fin pour le buffer translate (s)
        forward_command_speed       : vitesse de consigne forward
        translate_command_speed     : vitesse de consigne translate
        x_inertia_drift_delta               : delta de dérive d'inertie signé sur l'axe X
        y_inertia_drift_delta               : delta de dérive d'inertie signé sur l'axe Y
        x_dir                       : signe de la direction vers la cible en X (+1 / -1)
        y_dir                       : signe de la direction vers la cible en Y (+1 / -1)
    """

    dx = x_target - x_position
    dy = y_position - y_target

    translate_command_speed = min(MAX_TRANSLATE_SPEED, max(abs(dx), 1e-4) * translate_scale / dt)
    translate_finish_time = abs(dx) / translate_command_speed * translate_scale

    forward_command_speed = min(MAX_FORWARD_SPEED, max(abs(dy), 1e-4) * forward_scale / dt)
    forward_finish_time = abs(dy) / forward_command_speed * forward_scale

    x_dir = dx / max(abs(dx), 1e-4)
    y_dir = dy / max(abs(dy), 1e-4)

    x_inertia_drift_delta = compute_inertia_drift_delta(x_mesure, x_position, dt_mesure, inertia_factor_translate, dt,
                                                x_target)
    y_inertia_drift_delta = compute_inertia_drift_delta(y_mesure, y_position, dt_mesure, inertia_factor_forward, dt,
                                                y_target)

    return (
        abs(dx),
        abs(dy),
        forward_finish_time,
        translate_finish_time,
        forward_command_speed,
        translate_command_speed,
        x_inertia_drift_delta,
        y_inertia_drift_delta,
        x_dir,
        y_dir,
    )


class ForwardAndTranslate(TrajectoryStrategy):
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
        measured_position: Position,
        dt_mesure: float,
    ) -> AllCommandBuffers:
        """Implémentation avec axes indépendants (forward + translate simultanés)."""

        forward_buffer: CommandBuffer = []
        translate_buffer: CommandBuffer = []
        rotate_buffer: CommandBuffer = []

        x_mesure = measured_position.x
        y_mesure = measured_position.y

        # Reset des points de debug
        self._sim_points = []

        current_time = time.time()
        dt = current_time - self.previous_time
        self.previous_time = current_time

        (
            abs_dx,
            abs_dy,
            forward_finish_time,
            translate_finish_time,
            forward_command_speed,
            translate_command_speed,
            x_inertia_drift_delta,
            y_inertia_drift_delta,
            x_dir,
            y_dir,
        ) = compute_trajectory_core(
            dt,
            float(target_position.x),
            float(target_position.y),
            float(x_mesure),
            float(y_mesure),
            float(self.config.inertia_factor.forward),
            float(self.config.inertia_factor.translate),
            float(dt_mesure),
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
        if x_inertia_drift_delta > 0 or True:
            translate_buffer.append(CommandBufferItem(
                finish_time=translate_finish_time,
                command=translate_command_speed * x_dir,
            ))

        if y_inertia_drift_delta > 0 or True:
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
                   dérive inertie X: {x_inertia_drift_delta}
                   dérive inertie Y: {y_inertia_drift_delta}
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
