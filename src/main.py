from src import *

import multiprocessing as mp
import sys
from pathlib import Path

from loguru import logger

from src.drivers import Drivers
from src.processes import ProcessConfig, SharedResources
from src.rc_control import RCControlProcess
from src.trajectory_calculator import TrajectoryCalculatorProcess

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

def main() -> None:
    logger.info("Initialisation du manager et des variables partagées...")

    manager = mp.Manager()

    stop_event = mp.Event()
    process_exit_code = manager.Value("i", 0)

    shared_resources = SharedResources(
        stop_event=stop_event,
        process_exit_code=process_exit_code,
        forward_command_buffer=manager.list(),
        translate_command_buffer=manager.list(),
        rotate_command_buffer=manager.list(),
        shared_sim_points=manager.list(),
        command_buffers_lock=mp.Lock(),
        shared_sim_points_lock=mp.Lock(),
    )

    process_config = ProcessConfig(
        config_file_path=CONFIG_FILE,
        driver_class=driver_class,
    )

    logger.info("Manager et variables partagées initialisés.")
    logger.info("Lancement des processus...")

    trajectory_calculator_process = TrajectoryCalculatorProcess(shared_resources, process_config)
    trajectory_calculator_process.start()

    rc_control_process = RCControlProcess(shared_resources, process_config)
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


if __name__ == "__main__":
    main()
