import copy
import multiprocessing as mp
import sys
import time
from collections import deque
from multiprocessing.managers import ListProxy, DictProxy, ValueProxy  # type: ignore
from multiprocessing.synchronize import Event as MpEvent
from multiprocessing.synchronize import Lock as MpLock

from rcControl import rc_control
from trajectoryCalculator import generate_trajectory
from utils import *

CONFIG_FILE = "config.yml"
driver_class = Drivers.SIM.value


def generate_trajectory_process(
    stop_event: MpEvent,
    process_exit_code: ValueProxy[int],
    logger: LoggerAPI,
    forward_command_buffer: SharedCommandBuffer,
    translate_command_buffer: SharedCommandBuffer,
    rotate_command_buffer: SharedCommandBuffer,
    shared_sim_points: ListProxy[SimPoint],
    command_buffers_lock: MpLock,
    shared_sim_points_lock: MpLock,
) -> None:
    """Calcule périodiquement les buffers de commandes pour atteindre la cible.

    Lit la position du robot depuis le driver et écrit les buffers partagés
    (forward / translate / rotate) qui seront appliqués par rc_control_process.
    """
    config = Config.load_for_yml(CONFIG_FILE)

    driver: Driver = driver_class(config, logger, ProcessNames.TRAJECTORY_CALCULATOR)

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
                logger,
                ProcessNames.TRAJECTORY_CALCULATOR,
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
        logger.log(e, ProcessNames.TRAJECTORY_CALCULATOR, level=LoggingLevel.CRITICAL, force=True)
        terminate()
        process_exit_code.set(1)


def rc_control_process(
    stop_event: MpEvent,
    process_exit_code: ValueProxy[int],
    logger: LoggerAPI,
    forward_command_buffer: SharedCommandBuffer,
    translate_command_buffer: SharedCommandBuffer,
    rotate_command_buffer: SharedCommandBuffer,
    shared_sim_points: ListProxy[SimPoint],
    command_buffers_lock: MpLock,
    shared_sim_points_lock: MpLock,
) -> None:
    """Applique les buffers de commandes au robot à chaque tick.

    Lit les buffers partagés, récupère la commande courante via rc_control(),
    l'applique via le driver, puis met à jour la position du robot.
    """

    config = Config.load_for_yml(CONFIG_FILE)

    driver: Driver = driver_class(config, logger, ProcessNames.RC_CONTROL)
    # Capture initiale des buffers pour détecter les changements de consigne
    with command_buffers_lock:
        previous_buffers = AllCommandBuffers(
            forward=copy.deepcopy(list(forward_command_buffer)),
            translate=copy.deepcopy(list(translate_command_buffer)),
            rotate=copy.deepcopy(list(rotate_command_buffer)),
        )

    buffer_start_time = time.time()

    def terminate() -> None:
        stop_event.set()
        driver.stop()

    # noinspection PyBroadException
    try:
        running = driver.send_command(Command(None, None, None))
        while not stop_event.is_set():
            time.sleep(0.01)  # tick RC à ~100 Hz

            with shared_sim_points_lock:
                sim_points = copy.deepcopy(list(shared_sim_points))

            driver.add_all_sim_points(sim_points)

            if not running:
                terminate()
                break

            if not driver.has_target():
                # Pas de cible : arrêt progressif via l'inertie
                running = driver.send_command(Command(None, None, None))
                continue

            with command_buffers_lock:
                current_buffers = AllCommandBuffers(
                    forward=copy.deepcopy(list(forward_command_buffer)),
                    translate=copy.deepcopy(list(translate_command_buffer)),
                    rotate=copy.deepcopy(list(rotate_command_buffer)),
                )

            # Nouveaux buffers détectés → réinitialise l'horloge de lecture
            if current_buffers != previous_buffers:
                buffer_start_time = time.time()
                previous_buffers = current_buffers.copy(use_deepcopy=True)

            running = rc_control(
                logger,
                ProcessNames.RC_CONTROL,
                current_buffers,
                buffer_start_time,
                driver
            )

        terminate()

    except KeyboardInterrupt:
        terminate()
    except BaseException as e:
        logger.log(e, process=ProcessNames.RC_CONTROL, level=LoggingLevel.CRITICAL, force=True)
        terminate()
        process_exit_code.set(2)


if __name__ == "__main__":
    config = Config.load_for_yml(CONFIG_FILE)

    stop_event = mp.Event()

    logger = LoggerAPI(log_freq=config.utils.logger.log_freq)
    logger_process = logger.create_logger(stop_event, LoggingLevel.DEBUG)
    logger_process.start()

    logger.log("Initialisation du manager et des variables partagées...", process=ProcessNames.MAIN, level=LoggingLevel.INFO)

    manager = mp.Manager()

    process_exit_code = manager.Value("i", 0)

    forward_command_buffer: SharedCommandBuffer = manager.list()
    translate_command_buffer: SharedCommandBuffer = manager.list()
    rotate_command_buffer: SharedCommandBuffer = manager.list()
    shared_sim_points: ListProxy[SimPoint] = manager.list()

    command_buffers_lock = mp.Lock()
    shared_sim_points_lock = mp.Lock()

    logger.log("Manager et variables partagées initialisés.", process=ProcessNames.MAIN, level=LoggingLevel.INFO)
    logger.log("Lancement des processus...", process=ProcessNames.MAIN, level=LoggingLevel.INFO)

    trajectory_process = mp.Process(
        target=generate_trajectory_process,
        args=(
            stop_event, process_exit_code, logger,
            forward_command_buffer, translate_command_buffer, rotate_command_buffer,
            shared_sim_points, command_buffers_lock, shared_sim_points_lock,
        ),
        daemon=True,
    )
    trajectory_process.start()

    rc_process = mp.Process(
        target=rc_control_process,
        args=(
            stop_event, process_exit_code, logger,
            forward_command_buffer, translate_command_buffer, rotate_command_buffer,
            shared_sim_points, command_buffers_lock, shared_sim_points_lock,
        ),
        daemon=True,
    )
    rc_process.start()

    logger.log("Processus lancés.", process=ProcessNames.MAIN, level=LoggingLevel.INFO)

    try:
        trajectory_process.join()
        rc_process.join()
        logger_process.join()
    except KeyboardInterrupt:
        stop_event.set()
        process_exit_code.set(0)

    if process_exit_code.value == 0:
        logger.instant_log("Arrêt du programme.", process=ProcessNames.MAIN, level=LoggingLevel.INFO)
    else:
        logger.instant_log(
            f"Le programme a planté. Code de sortie : {process_exit_code.value}. Arrêt.",
            process=ProcessNames.MAIN,
            level=LoggingLevel.CRITICAL,
        )

    sys.exit()
