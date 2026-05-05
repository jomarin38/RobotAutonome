from utils import *

import copy
import multiprocessing as mp
import sys
import time
from multiprocessing.managers import ListProxy, DictProxy, ValueProxy  # type: ignore
from multiprocessing.synchronize import Event as MpEvent
from multiprocessing.synchronize import Lock as MpLock
from collections import deque

from rcControl import rc_control
from simulateur import Sim
from trajectoryCalculator import generate_trajectory

CONFIG_FILE = "config.yml"
ENV_DATA = EnvHandler.SIM

def generate_trajectory_process(
    stop_event: MpEvent,
    exit_code: ValueProxy[int],
    logger: LoggerAPI,
    global_target_point: DictProxy[str, Optional[float]],
    target_pos_lock: MpLock,
    forward_command_buffer: SharedCommandBuffer,
    rotate_command_buffer: SharedCommandBuffer,
    command_buffers_lock: MpLock,
) -> None:
    """Génère périodiquement les buffers de commandes pour atteindre la cible.

    - Lit la cible depuis `global_target_point`.
    - Lit la pose robot depuis Redis.
    - Écrit des buffers partagés (`forward_command_buffer`, `rotate_command_buffer`).
    """
    config = Config.load_for_yml(CONFIG_FILE)

    r = create_redis_client(config.redis)

    target_handler = TargetHandler(sim_handler=TargetSimHandler(global_target_point=global_target_point, lock=target_pos_lock), redis_handler=TargetRedisHandler(redis_db=r))
    use_target_handler = ENV_DATA.value.use_target_handler(target_handler)

    prevs_pos: deque[PreviousPosition] = deque(maxlen=config.others.prev_pos_buffer_len)

    def terminate():
        stop_event.set()
        r.close()

    # noinspection PyBroadException
    try:
        while not stop_event.is_set():
            # Récupération des coordonnées cibles
            target_pos = get_target(use_target_handler)
                
            if target_pos.x is None: continue
            
            # Récupération des coordonnées actuelles du robot
            robot_position = get_robot_pose(r)
            
            current_time = time.time()

            prev_position: Position
            if len(prevs_pos) >= config.others.prev_pos_buffer_len:
                prev_position_item = prevs_pos.popleft()
                prev_position = prev_position_item.position
                prev_position_time = prev_position_item.timestamp
                delta_time = current_time - prev_position_time
            else:
                prev_position = robot_position
                prev_position_time = current_time
                delta_time = 0

            command_buffers = generate_trajectory(
                logger,
                ProcessNames.TRAJECTORY_CALCULATOR,
                target_pos,
                prev_position,
                delta_time,
                robot_position,
                config
            )

            prevs_pos.append(PreviousPosition(position=prev_position, timestamp=prev_position_time))

            #logger.log(f"{command_buffers.forward}\n", ProcessNames.TRAJECTORY_CALCULATOR, LoggingLevel.DEBUG, use_pprint=True)

            # Envoie de la chaine d'instruction du robot vers la liste partagé
            with command_buffers_lock:
                forward_command_buffer[:] = command_buffers.forward
                rotate_command_buffer[:] = command_buffers.rotate

        terminate()
                
    except KeyboardInterrupt:
        terminate()
    except BaseException as e:
        logger.log(e, ProcessNames.TRAJECTORY_CALCULATOR, level=LoggingLevel.CRITICAL, force=True)
        terminate()
        exit_code.set(1)
        

def rc_control_process(
    stop_event: MpEvent,
    exit_code: ValueProxy[int],
    logger: LoggerAPI,
    global_target_point: DictProxy[str, float],
    target_pos_lock: MpLock,
    forward_command_buffer: SharedCommandBuffer,
    rotate_command_buffer: SharedCommandBuffer,
    command_buffers_lock: MpLock,
) -> None:
    """Applique les buffers de commandes au robot (simulateur ou vrai robot).

    Ici, on utilise `Sim` comme source de cible (clic souris) et comme actionneur.
    La pose du robot est publiée dans Redis.
    """
    config = Config.load_for_yml(CONFIG_FILE)

    sim = Sim(window_size=(config.sim.window.width, config.sim.window.height),
              tick_rate=config.sim.tick_rate,
              forward_coeff=config.movement_coeff.forward,
              translate_coeff=config.movement_coeff.translate,
              rotate_coeff=config.movement_coeff.rotate,
              inertie_factor_forward=config.inertie_factor.forward,
              inertie_factor_translate=config.inertie_factor.translate,
              inertie_factor_rotate=config.inertie_factor.rotate)
    r = create_redis_client(config.redis)

    target_handler = TargetHandler(sim_handler=TargetSimHandler(sim=sim, global_target_point=global_target_point, lock=target_pos_lock), redis_handler=TargetRedisHandler(redis_db=r))
    use_target_handler = ENV_DATA.value.use_target_handler(target_handler)

    robot_pos_handler = RobotPosHandler(sim_handler=RobotPosSimHandler(redis_db=r), redis_handler=RobotPosRedisHandler(redis_db=r))
    use_robot_pos_handler = ENV_DATA.value.use_robot_pos_handler(robot_pos_handler)

    control_data = ControlHandler(sim_handler=ControlSimHandler(sim=sim, redis_db=r), serial_handler=ControlSerialHandler(config=config.serial), i2c_handler=ControlI2CHandler())
    use_control_data = ENV_DATA.value.use_control_handler(control_data)
    
    # Copie des listes partagées d'instruction vers des listes locales
    with command_buffers_lock:
        prev_command_buffers = AllCommandBuffers(
                    forward=copy.deepcopy(list(forward_command_buffer)),
                    translate=[CommandBufferItem(finish_time=0, command=0)],
                    rotate=copy.deepcopy(list(rotate_command_buffer))
                )
        
    initial_time = time.time()

    def terminate():
        stop_event.set()
        sim.close()
        r.close()

    # noinspection PyBroadException
    try:
        running, obs = sim.reset(Position(x=config.sim.start_position.x, y=config.sim.start_position.y, direction=config.sim.start_position.direction))
        
        # Mise à jour des coordonnées du robot dans la base de donnée
        set_robot_pose(use_robot_pos_handler, obs.robot_position)

        while not stop_event.is_set():
            time.sleep(0.01)

            if not running:
                terminate()
                break
            
            # Récupération des coordonnées de la cible
            local_target_point = set_target(use_target_handler)
                
            # Ne rien faire si pas de cible
            if local_target_point is None:
                running, _ = sim.move(rotate=0, forward=0, translate=0)
                continue
            
            # Copie des chaines d'instruction du robot dans une liste locale
            with command_buffers_lock:
                command_buffers = AllCommandBuffers(
                    forward=copy.deepcopy(list(forward_command_buffer)),
                    translate=[CommandBufferItem(finish_time=0, command=0)],
                    rotate=copy.deepcopy(list(rotate_command_buffer))
                )
            
            # Si une nouvelle chaine d'instruction arrive, on reprend sa lecture a 0 en actualisant initial_time
            if command_buffers != prev_command_buffers:
                initial_time = time.time()
                prev_command_buffers = command_buffers.copy(use_deepcopy=True)
            
            running = rc_control(logger, ProcessNames.RC_CONTROL, command_buffers, initial_time, use_control_data)

        terminate()

    except KeyboardInterrupt:
        terminate()
    except BaseException as e:
        logger.log(e, process=ProcessNames.RC_CONTROL, level=LoggingLevel.CRITICAL, force=True)
        terminate()
        exit_code.set(2)

if __name__ == "__main__":
    config = Config.load_for_yml(CONFIG_FILE)

    stop_event = mp.Event()
    target_update_event = mp.Event()

    logger = LoggerAPI(log_freq=config.utils.logger.log_freq)
    logger_process = logger.create_logger(stop_event, level=LoggingLevel.DEBUG)
    logger_process.start()

    logger.log("Initialisation du manager et des variables partagées...", process=ProcessNames.MAIN, level=LoggingLevel.INFO)

    manager = mp.Manager()

    exit_code = manager.Value('i', 0)
    
    global_target_point: DictProxy[str, Optional[float]] = manager.dict()
    global_target_point.clear()
    global_target_point.update({"x": None, "y": None, "direction": None})
    
    # Création des listes partagé pour les chaines d'instruction ainsi que leur vérou.
    forward_command_buffer: SharedCommandBuffer = manager.list()
    rotate_command_buffer: SharedCommandBuffer = manager.list()
    command_buffers_lock = mp.Lock()
    target_pos_lock = mp.Lock()

    logger.log("Manager et variables partagées initialisés !", process=ProcessNames.MAIN, level=LoggingLevel.INFO)

    logger.log("Lancement des processus...", process=ProcessNames.MAIN, level=LoggingLevel.INFO)

    # Création et lancement du processus pour générer la chaine d'instruction
    generate_trajectory_process_object = mp.Process(target=generate_trajectory_process, args=(stop_event, exit_code, logger, global_target_point, target_pos_lock, forward_command_buffer, rotate_command_buffer, command_buffers_lock), daemon=True)
    generate_trajectory_process_object.start()
    
    # Création en lancement du processus pour envoyer les instructions au robot
    rc_controle_process_object = mp.Process(target=rc_control_process, args=(stop_event, exit_code, logger, global_target_point, target_pos_lock, forward_command_buffer, rotate_command_buffer, command_buffers_lock), daemon=True)
    rc_controle_process_object.start()

    logger.log("Processus lancés !...", process=ProcessNames.MAIN, level=LoggingLevel.INFO)

    try:
        generate_trajectory_process_object.join()
        rc_controle_process_object.join()
        logger_process.join()
    except KeyboardInterrupt:
        stop_event.set()
        exit_code.set(0)

    if exit_code.value == 0:
        logger.instant_log("Arrêt du programme...", process=ProcessNames.MAIN, level=LoggingLevel.INFO)
    else:
        logger.instant_log(f"Le programme a planté. code de sortie : {exit_code.value} Arret...", process=ProcessNames.MAIN, level=LoggingLevel.CRITICAL)

    sys.exit()