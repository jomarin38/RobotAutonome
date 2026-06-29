import multiprocessing as mp
import sys
from pathlib import Path
import time

from loguru import logger
from redis import StrictRedis

from src.config_manager import Config
from src.drivers import Drivers
from src.processes import ProcessConfig, SharedResources
from src.processes import RCControlProcess
from src.processes import TrajectoryCalculatorProcess
from src.trajectories import TrajectoryStrategies
from src.utils import bind_context
from utils import AllCommandBuffers, CommandBufferItem

CONFIG_FILE = Path(__file__).parent.parent / "configs" / "config.yml"
driver_class = Drivers.SIM.value
trajectory_strategy_class = TrajectoryStrategies.TURN_THEN_MOVE.value

log_dir_path = Path(__file__).parent.parent / "logs"
log_dir_path.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.configure(patcher=bind_context)
logger.add(
    log_dir_path / "latest.log",
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
    """Point d'entrée principal du programme.

    Initialise le manager multiprocessing, crée les ressources partagées,
    lance les processus de contrôle RC et de calcul de trajectoire,
    puis attend leur terminaison avant de nettoyer Redis.
    """
    logger.info("Initialisation du manager et des variables partagées...")

    manager = mp.Manager()

    stop_event = mp.Event()
    process_exit_code = manager.Value("i", 0)
    
    command_buffers = manager.dict()
    command_buffers.update(
        AllCommandBuffers(
            forward=[CommandBufferItem(finish_time=time.time(), command=0),],
            translate=[CommandBufferItem(finish_time=time.time(), command=0),],
            rotate=[CommandBufferItem(finish_time=time.time(), command=0),]
        ).asdict()
    )

    shared_resources = SharedResources(
        stop_event=stop_event,
        process_exit_code=process_exit_code,
        command_buffers=command_buffers,
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

    trajectory_calculator_process = TrajectoryCalculatorProcess(shared_resources, process_config, trajectory_strategy_class)
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
        trajectory_calculator_process.join()
        rc_control_process.join()

    config = Config.load_from_yml(CONFIG_FILE)
    redis = StrictRedis(host=config.redis.host, port=config.redis.port, db=config.redis.db,
                                 decode_responses=True)
    redis.flushdb()
    redis.close()

    if process_exit_code.value == 0:
        logger.info("Arrêt du programme.")
        sys.exit(0)
    else:
        logger.critical(f"Le programme a planté. Code de sortie : {process_exit_code.value}. Arrêt.")
        sys.exit(-1)


if __name__ == "__main__":
    main()
