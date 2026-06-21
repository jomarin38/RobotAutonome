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
from .trajectory_calculator import TrajectoryCalculatorProcess
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

    trajectory_calculator_process = TrajectoryCalculatorProcess(
        stop_event, process_exit_code,
        forward_command_buffer, translate_command_buffer, rotate_command_buffer,
        shared_sim_points, command_buffers_lock, shared_sim_points_lock, CONFIG_FILE, driver_class
    )
    trajectory_calculator_process.start()

    rc_control_process = RCControlProcess(
        stop_event, process_exit_code,
        forward_command_buffer, translate_command_buffer, rotate_command_buffer,
        shared_sim_points, command_buffers_lock, shared_sim_points_lock, CONFIG_FILE, driver_class
    )
    rc_control_process.start()

    logger.info("Processus lancés.")

    try:
        trajectory_calculator_process.join()
        rc_control_process.join()
    except KeyboardInterrupt:
        stop_event.set()
        process_exit_code.set(0)

    if process_exit_code.value == 0:
        logger.info("Arrêt du programme.")
    else:
        logger.critical(f"Le programme a planté. Code de sortie : {process_exit_code.value}. Arrêt.")

    sys.exit()
