import time
from collections import deque
from multiprocessing import Process
from multiprocessing.managers import ValueProxy
from multiprocessing.synchronize import Lock as MpLock, Event as MpEvent

from .drivers import *
from src import *

from loguru import logger
from numba import njit  # type: ignore[import-untyped]

debug = False

# Vitesses de consigne maximales pour chaque axe (en unités simulateur)
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
    # Pas de mouvement mesurable : robot considéré à l'arrêt
    if previous_pos == current_pos or elapsed_time <= 0.0:
        return abs(target_position - current_pos)

    measured_speed = (current_pos - previous_pos) / elapsed_time  # px/s, signé

    # Vitesse négligeable : pas de dérive significative
    if abs(measured_speed) < 1e-4:
        return abs(target_position - current_pos)

    # Facteur d'inertie hors domaine valide : pas de prédiction possible
    if inertia_factor <= 0.0 or inertia_factor >= 1.0:
        return abs(target_position - current_pos)

    coast_distance = measured_speed * tick_interval / (1.0 - inertia_factor)
    predicted_stop_pos = current_pos + coast_distance

    # Positif = encore besoin de poussée, négatif = dépassement prédit
    direction_sign = 1.0 if target_position > current_pos else -1.0
    return (target_position - predicted_stop_pos) * direction_sign

@njit(cache=True)
def compute_trajectory_core(
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
        logs                        : liste de messages de debug (None = pas de message)
    """

    dx = x_target - x_pos  # positif si cible à droite
    dy = y_pos - y_target  # positif si cible en haut (y écran inversé)

    # Vitesse proportionnelle à la distance pour éviter le dépassement au dernier tick
    translate_command_speed = min(MAX_TRANSLATE_SPEED, abs(dx) * translate_scale / tick_interval)
    translate_finish_time = abs(dx) / translate_command_speed * translate_scale

    forward_command_speed = min(MAX_FORWARD_SPEED, abs(dy) * forward_scale / tick_interval)
    forward_finish_time = abs(dy) / forward_command_speed * forward_scale

    # Signe de direction vers la cible sur chaque axe
    x_dir = dx / max(abs(dx), 1e-4)
    y_dir = dy / max(abs(dy), 1e-4)

    # Delta d'inertie : positif = encore besoin de pousser, négatif = déjà trop d'élan
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

class TrajectoryCalculatorProcess(Process):
    def __init__(self,
                 stop_event: MpEvent,
                 process_exit_code: ValueProxy[int],
                 forward_command_buffer: SharedCommandBuffer,
                 translate_command_buffer: SharedCommandBuffer,
                 rotate_command_buffer: SharedCommandBuffer,
                 shared_sim_points: ListProxy[SimPoint],
                 command_buffers_lock: MpLock,
                 shared_sim_points_lock: MpLock,
                 config_file_path: Path,
                 driver_class: type[Driver]
                 ):
        super().__init__(daemon=True)

        self.config_file_path = config_file_path
        self.driver_class = driver_class
        self.current_time = time.time()
        self.sim_points: list[SimPoint] = []

        self._config: Optional[Config] = None
        self._driver: Optional[Driver] = None
        self._position_history: Optional[deque[PreviousPosition]] = None
        self._robot_position = None

        self.stop_event = stop_event
        self.process_exit_code = process_exit_code
        self.forward_command_buffer = forward_command_buffer
        self.translate_command_buffer = translate_command_buffer
        self.rotate_command_buffer = rotate_command_buffer
        self.shared_sim_points = shared_sim_points
        self.command_buffers_lock = command_buffers_lock
        self.shared_sim_points_lock = shared_sim_points_lock

    @property
    def config(self) -> Config:
        assert self._config is not None
        return self._config

    @config.setter
    def config(self, config: Config) -> None:
        self._config = config

    @property
    def driver(self) -> Driver:
        assert self._driver is not None
        return self._driver

    @driver.setter
    def driver(self, driver: Driver) -> None:
        self._driver = driver

    @property
    def position_history(self) -> deque[PreviousPosition]:
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
    def robot_position(self, robot_position: Position) -> None:
        self._robot_position = robot_position

    def setup(self) -> None:
        self.config = Config.load_for_yml(self.config_file_path)
        self.driver = self.driver_class(self.config, ProcessNames.TRAJECTORY_CALCULATOR)
        self.position_history: deque[PreviousPosition] = deque(maxlen=self.config.others.previous_position_buffer_len)

    def stop(self) -> None:
        if self._position_history is None: raise RuntimeError("Vous devez lancer le processus avant de pouvoir l'arrêter")
        self.stop_event.set()
        self.driver.stop()

    def get_previous_position(self) -> tuple[Position, float]:
        # Calcul du delta de temps et de la position de référence pour mesurer la vitesse
        if len(self.position_history) >= self.config.others.previous_position_buffer_len:
            oldest_position_record = self.position_history.popleft()
            return oldest_position_record.position, self.current_time - oldest_position_record.timestamp
        else:
            return self.robot_position, 0

    def update_command_buffers(self, command_buffers: AllCommandBuffers) -> None:
        with self.command_buffers_lock:
            self.forward_command_buffer[:] = command_buffers.forward
            self.translate_command_buffer[:] = command_buffers.translate
            self.rotate_command_buffer[:] = command_buffers.rotate

    def planify_trajectory(
            self,
            target_position: Position,
            previous_position: Position,
            elapsed_time: float,
    ):
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
        ) = compute_trajectory_core(
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

        # Point de debug : position d'arrêt prédite par l'inertie.
        # predicted_x = target.x - x_dir * x_coast_delta  (car x_coast_delta = (target - predicted) * x_dir)
        # predicted_y = target.y + y_dir * y_coast_delta
        self.sim_points.append(SimPoint(
            name="inertie_point",
            position=Position(
                x=target_position.x - x_dir * x_coast_delta,
                y=target_position.y + y_dir * y_coast_delta,
                direction=0,
            ),
            color=Color(red=0, green=255, blue=0),
            radius=10,
        ))

        # Axe X : pousser tant que l'inertie ne suffit pas à atteindre la cible
        if x_coast_delta > 0:
            translate_buffer.append(CommandBufferItem(
                finish_time=translate_finish_time,
                command=translate_command_speed * x_dir,
            ))

        # Axe Y : même logique
        if y_coast_delta > 0:
            forward_buffer.append(CommandBufferItem(
                finish_time=forward_finish_time,
                command=forward_command_speed * y_dir,
            ))

        if debug:
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
    def run(self):
        # noinspection PyBroadException
        try:
            self.setup()
            while not self.stop_event.is_set():
                time.sleep(0.02)  # limite le taux de recalcul (~50 Hz)

                self.sim_points = []

                self.current_time = time.time()

                target_position = self.driver.get_target_position()
                if not self.driver.has_target():
                    continue

                self.robot_position = self.driver.get_robot_position()
                previous_position, elapsed_time = self.get_previous_position()

                command_buffers = self.planify_trajectory(
                    cast(Position, target_position),
                    previous_position,
                    elapsed_time,
                )

                # Enregistre la position courante pour le prochain calcul de vitesse
                self.position_history.append(PreviousPosition(position=self.robot_position, timestamp=self.current_time))

                self.update_command_buffers(command_buffers)

                with self.shared_sim_points_lock:
                    self.shared_sim_points[:] = self.sim_points.copy()

        except KeyboardInterrupt:
            pass
        except BaseException as e:
            logger.critical(LoggerUtils.format_traceback(e))
            self.process_exit_code.set(1)
        finally:
            self.stop()