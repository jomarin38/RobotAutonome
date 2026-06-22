from math import sqrt, atan2, pi, ceil, log, cos, sin

from src import *

import time
from collections import deque
from typing import cast, Optional, override

from loguru import logger
from numba import njit  # type: ignore[import-untyped]

from src.processes import RobotProcess, ProcessConfig, SharedResources
from src.utils import ProcessNames

DEBUG = False

MAX_FORWARD_SPEED: float = 100.0
MAX_TRANSLATE_SPEED: float = 100.0
MAX_ROTATE_SPEED: float = 100.0


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
def compute_trajectory_core1(
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

@njit(cache=True)
def compute_trajectory_core2(
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
    dy = y_position - y_target
    target_distance = sqrt(dx * dx + dy * dy)
    target_direction = atan2(dy, dx)

    # 2) Delta angle (alignement vers la cible)
    delta_angle = target_direction - current_direction_deg * pi / 180.0
    delta_angle = (delta_angle + pi) % (2 * pi) - pi
    #delta_angle = -delta_angle

    # Signe (même logique que `calculate_sens`)
    abs_delta_angle = abs(delta_angle)
    sens = delta_angle / abs_delta_angle if abs_delta_angle > 1e-6 else 0.0

    # 3) Durée de rotation
    current_time_rotate = 0.0
    if abs(delta_angle) > 0.034:
        deg = abs(delta_angle) * 180.0 / pi
        current_time_rotate += (deg * rotate_coeff / 100.0 if deg > 1.0 else 0.0)

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
        sens
    )


class TrajectoryCalculatorProcess(RobotProcess):
    """Processus de calcul de trajectoire.

    Lit la position du robot et la cible, calcule les buffers de commandes
    à appliquer pour atteindre la cible en tenant compte de l'inertie.
    """

    def __init__(self, shared: SharedResources, config: ProcessConfig) -> None:
        super().__init__(shared, config, daemon=True)
        self._position_history: Optional[deque[PreviousPosition]] = None
        self._robot_position: Optional[Position] = None
        self._current_time = time.time()
        self._sim_points: list[SimPoint] = []

    @override
    @property
    def process_name(self) -> ProcessNames:
        return ProcessNames.TRAJECTORY_CALCULATOR

    @override
    @property
    def exit_code_on_error(self) -> int:
        return 1

    @property
    def position_history(self) -> deque[PreviousPosition]:
        if self._position_history is None:
            self._position_history = deque(maxlen=self.config.others.previous_position_buffer_len)
        assert self._position_history is not None
        return self._position_history

    @position_history.setter
    def position_history(self, history: deque[PreviousPosition]) -> None:
        self._position_history = history

    @property
    def robot_position(self) -> Position:
        assert self._robot_position is not None
        return self._robot_position

    @robot_position.setter
    def robot_position(self, position: Position) -> None:
        self._robot_position = position

    def _get_previous_position(self) -> tuple[Position, float]:
        """Calcule la position de référence pour mesurer la vitesse."""
        if len(self.position_history) >= self.config.others.previous_position_buffer_len:
            oldest_position_record = self.position_history.popleft()
            return oldest_position_record.position, self._current_time - oldest_position_record.timestamp
        else:
            return self.robot_position, 0

    def _update_command_buffers(self, command_buffers: AllCommandBuffers) -> None:
        """Écrit les buffers de commandes dans le partage multiprocessing."""
        with self.shared.command_buffers_lock:
            self.shared.forward_command_buffer[:] = command_buffers.forward
            self.shared.translate_command_buffer[:] = command_buffers.translate
            self.shared.rotate_command_buffer[:] = command_buffers.rotate

    def _planify_trajectory(
            self,
            target_position: Position,
            previous_position: Position,
            elapsed_time: float,
    ) -> AllCommandBuffers:
        """Calcule les buffers de commandes pour atteindre la cible."""
        forward_buffer: CommandBuffer = []
        translate_buffer: CommandBuffer = []
        rotate_buffer: CommandBuffer = []

        prev_x = previous_position.x
        prev_y = previous_position.y

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
        ) = compute_trajectory_core2(
            float(self.config.others.rc_control_dt),
            float(target_position.x),
            float(target_position.y),
            float(prev_x),
            float(prev_y),
            float(self.config.inertia_factor.forward),
            float(self.config.inertia_factor.translate),
            float(elapsed_time),
            float(self.robot_position.x),
            float(self.robot_position.y),
            float(self.config.movement_coeff.forward),
            float(self.config.movement_coeff.translate),
        )

        self._sim_points.append(SimPoint(
            name="inertie_point",
            position=Position(
                x=target_position.x - x_dir * x_coast_delta,
                y=target_position.y + y_dir * y_coast_delta,
                direction=0,
            ),
            color=Color(red=0, green=255, blue=0),
            radius=10,
        ))

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
                f"""target position : {target_position.x} {target_position.y}
                       distance X     : {abs_dx}
                       distance Y     : {abs_dy}
                       position robot : {self.robot_position.x, self.robot_position.y, self.robot_position.direction}
                       direction X    : {x_dir}
                       direction Y    : {y_dir}
                       delta inertie X: {x_coast_delta}
                       delta inertie Y: {y_coast_delta}
                       buffer forward : {forward_buffer}
                       buffer translate: {translate_buffer}
                       buffer rotate  : {rotate_buffer}"""
            )

        return AllCommandBuffers(forward=forward_buffer, translate=translate_buffer, rotate=rotate_buffer)

    @override
    def stop(self) -> None:
        self.shared.stop_event.set()
        self.driver.stop()

    @override
    def _run_impl(self) -> None:
        while not self.shared.stop_event.is_set():
            time.sleep(0.02)

            self._sim_points = []
            self._current_time = time.time()

            target_position = self.driver.get_target_position()
            if not self.driver.has_target():
                continue

            self.robot_position = self.driver.get_robot_position()
            previous_position, elapsed_time = self._get_previous_position()

            command_buffers = self._planify_trajectory(
                cast(Position, target_position),
                previous_position,
                elapsed_time,
            )

            self.position_history.append(PreviousPosition(position=self.robot_position, timestamp=self._current_time))

            self._update_command_buffers(command_buffers)

            with self.shared.shared_sim_points_lock:
                self.shared.shared_sim_points[:] = self._sim_points.copy()