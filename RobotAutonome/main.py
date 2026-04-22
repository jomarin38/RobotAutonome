from rcControl import rc_control
import time
import redis
from simulateur import Sim
import multiprocessing as mp
import sys
import traceback
import queue
from pprint import pprint
import copy
from collections import deque
from typing import Any, Tuple, cast
from multiprocessing.synchronize import Event as MpEvent
from multiprocessing.synchronize import Lock as MpLock

from trajectoryCalculator import generate_trajectory

USE_SIM = True

# Ports de la base de donnée
redis_host='localhost'
redis_port=6379
redis_db=0

# Coefficients de vitesse du robot
coef_rotate = 1.105
coef_forward = 0.38

def generate_trajectory_process(stop_event: MpEvent, log_queue: Any, traceback_queue: Any, global_target_point, target_pos_lock: MpLock, throttle_command_buffer, turn_command_buffer, command_buffers_lock, target_update_event: MpEvent):
    """
    processus de génération de la chaine d'instruction pour le robot
    """
    r = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
    
    prev_time = time.perf_counter()
    prev_pos = None
    
    delta_time = float("inf")
    
    try:
        while not stop_event.is_set():
            # Récupération des coordonnées cibles
            with target_pos_lock:
                local_target_pos = list(global_target_point)
                
            if local_target_pos[0] is None:
                target_update_event.wait(timeout=0.2)
                target_update_event.clear()
                #log_queue.put("Pas de target_pos !")
                continue
            
            # Récupération des coordonnées actuellles du robot
            x_position_raw = r.get('x_position')
            y_position_raw = r.get('y_position')
            current_direction_raw = r.get('direction')

            if x_position_raw is None or y_position_raw is None or current_direction_raw is None:
                raise ValueError("Position ou direction absente de Redis")

            x_position = float(cast(str, x_position_raw))
            y_position = float(cast(str, y_position_raw))
            current_direction = float(cast(str, current_direction_raw))
            
            if prev_pos is None:
                prev_pos = [x_position, y_position]

            target_pos = cast(Tuple[float, float, float], tuple(local_target_pos))
            
            current_time = time.time()
            
            
            # Génération de la chaine d'instruction du robot
            if current_time - prev_time >= 0.05:
                delta_time = current_time - prev_time
            
            #log_queue.put(f"actual pos: {(x_position, y_position, current_direction)}, target pos: {target_pos}")

            command_buffers = generate_trajectory(
                log_queue,
                *target_pos,
                prev_pos,
                0.9,
                delta_time,
                x_position,
                y_position,
                current_direction,
                coef_rotate,
                coef_forward,
            )
            
            if current_time - prev_time >= 0.05:
                prev_pos = [x_position, y_position]
                prev_time = current_time

            #log_queue.put(f"[rc_contrôle_process] {command_buffers[1]}\n\n")
            # Envoie de la chaine d'instruction du robot vers la liste partagé
            with command_buffers_lock:
                throttle_command_buffer[:] = command_buffers[0]
                turn_command_buffer[:] = command_buffers[1]
                
            #log_queue.put(f"[rc_contrôle_process] {copy.deepcopy(list(turn_command_buffer))}\n\n")
    except BaseException as e:
        traceback_queue.put(traceback.format_exc())
        stop_event.set()
        r.close()

def rc_control_process(stop_event, log_queue: mp.Queue, traceback_queue: mp.Queue, global_target_point, target_pos_lock, throttle_command_buffer, turn_command_buffer, command_buffers_lock, target_update_event: MpEvent):
    """
    processus pour envoyer les instructions au robot
    """

    if USE_SIM:
        sim = Sim(window_size=(1300, 700), tick_rate=60, coef_rotate=coef_rotate, coef_forward=coef_forward, inertie_factor_forward=0.1, inertie_factor_rotate=0.6, inertie_factor_translate=0.1)
        r = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
    else:
        sim = None
    
    # Copi des listes partagé d'instruction vers des listes locales
    with command_buffers_lock:
        prev_command_buffers = [
            copy.deepcopy(list(throttle_command_buffer)),
            copy.deepcopy(list(turn_command_buffer))
            ]
        
    initial_time = time.time()
    
    try:
        if USE_SIM:
            running, obs = sim.reset((500, 400, 0))

            # Mise a jours des coordonnées du robot dans la base de donnée
            r.set('x_position', obs[0])
            r.set('y_position', obs[1])
            r.set('direction', obs[2])
        
        had_target = False
        while not stop_event.is_set():
            time.sleep(0.01)
            
            # Récupération des coordonnées de la cible
            if USE_SIM:
                with target_pos_lock:
                    local_target_point = sim.target_point or [None, None, None]
            else:
                local_target_point = [None, None, None]
                
            global_target_point[:] = local_target_point # mise a jours des coordonnées de la cible dans la valeur partagé

            has_target = global_target_point[0] is not None
            if has_target and not had_target:
                target_update_event.set()
            had_target = has_target
                
            # Ne rien faire si pas de cible
            if global_target_point[0] is None and USE_SIM:
                sim.move(0, 0, 0)
                continue
            
            #log_queue.put(f"[rc_contrôle_process] {copy.deepcopy(list(throttle_command_buffer))}\n\n")
            
            # Copie des chaines d'instruction du robot dans une liste locale
            with command_buffers_lock:
                command_buffers = [
                    copy.deepcopy(list(throttle_command_buffer)),
                    copy.deepcopy(list(turn_command_buffer))
                    ]

            command_buffers_typed = cast(Tuple[Any, Any], tuple(command_buffers))
            
            # Si une nouvelle chaine d'instruction arrive, on reprend sa lecture a 0 en actualisant initial_time
            if command_buffers != prev_command_buffers:
                initial_time = time.time()
                prev_command_buffers = copy.deepcopy(command_buffers)
            
            running = rc_control(log_queue, *command_buffers_typed, sim, r, initial_time)
            if not running:
                stop_event.set()
                break
    except Exception as e:
        traceback_queue.put(traceback.format_exc())
        stop_event.set()
        if USE_SIM: sim.close()
        r.close()
        
def logger_process(log_queue: Any, traceback_queue: mp.Queue, stop_event: MpEvent):
    while True:
        got_any = False
        try:
            try:
                print(traceback_queue.get(timeout=0.1), flush=True)
                got_any = True
            except queue.Empty:
                pass

            try:
                print(log_queue.get(timeout=0.1), flush=True)
                got_any = True
            except queue.Empty:
                pass
        except BaseException:
            try:
                print(traceback.format_exc(), file=sys.stderr, flush=True)
            except BaseException:
                pass
            break

        if stop_event.is_set() and not got_any:
            break

if __name__ == "__main__":
    manager = mp.Manager()
    
    global_target_point = manager.list()
    
    log_queue = manager.Queue()
    traceback_queue = manager.Queue()
    
    # On donne toujours 3 éléments a la valeur partagé des coordonnées de la cible
    for _ in range(3):
        global_target_point.append(None)
    
    # Création des listes partagé pour les chaines d'instruction ainsi que leur vérou.
    throttle_command_buffer, turn_command_buffer = manager.list(), manager.list()
    command_buffers_lock = mp.Lock()
    target_pos_lock = mp.Lock()
    
    stop_event = mp.Event()
    target_update_event = mp.Event()
    
    logger_proccess_object = mp.Process(target=logger_process, args=(log_queue, traceback_queue, stop_event), daemon=True)
    logger_proccess_object.start()
    
    # Création et lancement du processus pour générer la chaine d'instruction
    generate_trajectory_process_object = mp.Process(target=generate_trajectory_process, args=(stop_event, log_queue, traceback_queue, global_target_point, target_pos_lock, throttle_command_buffer, turn_command_buffer, command_buffers_lock, target_update_event), daemon=True)
    generate_trajectory_process_object.start()
    
    # Création en lancement du processus pour envoyer les instructions au robot
    rc_controle_process_object = mp.Process(target=rc_control_process, args=(stop_event, log_queue, traceback_queue, global_target_point, target_pos_lock, throttle_command_buffer, turn_command_buffer, command_buffers_lock, target_update_event), daemon=True)
    rc_controle_process_object.start()
    
    while not stop_event.is_set():
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()
            break
    sys.exit()