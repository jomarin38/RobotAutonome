from src import *

import sys
import time
from collections import deque
import multiprocessing as mp
from multiprocessing.managers import ListProxy, DictProxy, ValueProxy  # type: ignore
from multiprocessing.synchronize import Lock as MpLock
from multiprocessing.synchronize import Event as MpEvent
from pathlib import Path
from loguru import logger

from .drivers import *
from .rc_control import RCControlProcess
from .trajectory_calculator import generate_trajectory
from .utils import *

CONFIG_FILE = Path(__file__).parent.parent / "configs" / "config.yml"
driver_class = Drivers.SIM.value

logger.remove()
logger.configure(patcher=bind_context)
logger.add(
    Path(__file__).parent.parent / "logs" / "latests.log",
    format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[context]: <55}</cyan> | "
            "<level>{message}</level>"
        ),
    colorize=False,
    enqueue=True,
    backtrace=True,
    diagnose=True,
    level="INFO"
)
logger.add(
    sys.stdout,
    format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[context]: <55}</cyan> | "
            "<level>{message}</level>"
        ),
    colorize=True,
    enqueue=True,
    backtrace=True,
    diagnose=True,
    level="DEBUG"
)

def generate_trajectory_process(
    stop_event: MpEvent,
    process_exit_code: ValueProxy[int],
    forward_command_buffer: SharedCommandBuffer,
    translate_command_buffer: SharedCommandBuffer,
    rotate_command_buffer: SharedCommandBuffer,
    shared_sim_points: ListProxy[SimPoint],
    command_buffers_lock: MpLock,
    shared_sim_points_lock: MpLock,
) -> None:
    """Calcule périodiquement les buffers de commandes pour atteindre la cible.

    Lit la position du robot depuis le drivers et écrit les buffers partagés
    (forward / translate / rotate) qui seront appliqués par rc_control_process.
    """
    config = Config.load_for_yml(CONFIG_FILE)

    driver: Driver = driver_class(config, ProcessNames.TRAJECTORY_CALCULATOR)

    # Historique des positions passées pour mesurer la vitesse (heuristique d'inertie)
    position_history: deque[PreviousPosition] = deque(maxlen=config.others.previous_position_buffer_len)

    def terminate() -> None:
        stop_event.set()
        driver.stop()

    # noinspection PyBroadException
    try:
        while not stop_event.is_set():
            time.sleep(0.02)  # limite le taux de recalcul (~50 Hz)

            sim_points: list[SimPoint] = []

            target_position = driver.get_target_position()
            if not driver.has_target():
                continue

            robot_position = driver.get_robot_position()
            current_time = time.time()

            # Calcul du delta de temps et de la position de référence pour mesurer la vitesse
            if len(position_history) >= config.others.previous_position_buffer_len:
                oldest_position_record = position_history.popleft()
                previous_position = oldest_position_record.position
                elapsed_time = current_time - oldest_position_record.timestamp
            else:
                previous_position = robot_position
                elapsed_time = 0.0

            command_buffers = generate_trajectory(
                cast(Position, target_position),
                previous_position,
                elapsed_time,
                robot_position,
                config,
                sim_points,
            )

            # Enregistre la position courante pour le prochain calcul de vitesse
            position_history.append(PreviousPosition(position=robot_position, timestamp=current_time))

            with command_buffers_lock:
                forward_command_buffer[:] = command_buffers.forward
                translate_command_buffer[:] = command_buffers.translate
                rotate_command_buffer[:] = command_buffers.rotate

            with shared_sim_points_lock:
                shared_sim_points[:] = sim_points.copy()

        terminate()

    except KeyboardInterrupt:
        terminate()
    except BaseException as e:
        logger.critical(LoggerUtils.format_traceback(e))
        terminate()
        process_exit_code.set(1)


if __name__ == "__main__":
    config = Config.load_for_yml(CONFIG_FILE)

    stop_event = mp.Event()

    logger.info("Initialisation du manager et des variables partagées...")

    manager = mp.Manager()

    process_exit_code = manager.Value("i", 0)

    forward_command_buffer: SharedCommandBuffer = manager.list()
    translate_command_buffer: SharedCommandBuffer = manager.list()
    rotate_command_buffer: SharedCommandBuffer = manager.list()
    shared_sim_points: ListProxy[SimPoint] = manager.list()

    command_buffers_lock = mp.Lock()
    shared_sim_points_lock = mp.Lock()

    logger.info("Manager et variables partagées initialisés.")
    logger.info("Lancement des processus...")

    trajectory_process = mp.Process(
        target=generate_trajectory_process,
        args=(
            stop_event, process_exit_code,
            forward_command_buffer, translate_command_buffer, rotate_command_buffer,
            shared_sim_points, command_buffers_lock, shared_sim_points_lock,
        ),
        daemon=True,
    )
    trajectory_process.start()

    rc_control_process = RCControlProcess(
        stop_event, process_exit_code,
        forward_command_buffer, translate_command_buffer, rotate_command_buffer,
        shared_sim_points, command_buffers_lock, shared_sim_points_lock, CONFIG_FILE, driver_class
    )
    rc_control_process.start()

    logger.info("Processus lancés.")

    try:
        trajectory_process.join()
        rc_control_process.join()
    except KeyboardInterrupt:
        stop_event.set()
        process_exit_code.set(0)

    if process_exit_code.value == 0:
        logger.info("Arrêt du programme.")
    else:
        logger.critical(f"Le programme a planté. Code de sortie : {process_exit_code.value}. Arrêt.")

    sys.exit()
