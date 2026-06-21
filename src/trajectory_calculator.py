from src import *

from loguru import logger
from numba import njit  # type: ignore[import-untyped]

debug = False

# Vitesses de consigne maximales pour chaque axe (en unités simulateur)
MAX_FORWARD_SPEED: float = 100.0
MAX_TRANSLATE_SPEED: float = 100.0
MAX_ROTATE_SPEED: float = 100.0


@njit()
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

    dx = x_target - x_pos   # positif si cible à droite
    dy = y_pos - y_target    # positif si cible en haut (y écran inversé)

    # Vitesse proportionnelle à la distance pour éviter le dépassement au dernier tick
    translate_command_speed = min(MAX_TRANSLATE_SPEED, abs(dx) * translate_scale / tick_interval)
    translate_finish_time = abs(dx) / translate_command_speed * translate_scale

    forward_command_speed = min(MAX_FORWARD_SPEED, abs(dy) * forward_scale / tick_interval)
    forward_finish_time = abs(dy) / forward_command_speed * forward_scale

    # Signe de direction vers la cible sur chaque axe
    x_dir = dx / max(abs(dx), 1e-4)
    y_dir = dy / max(abs(dy), 1e-4)

    # Delta d'inertie : positif = encore besoin de pousser, négatif = déjà trop d'élan
    x_coast_delta = compute_inertia_coast_delta(prev_x, x_pos, elapsed_time, inertia_factor_tra, tick_interval, x_target)
    y_coast_delta = compute_inertia_coast_delta(prev_y, y_pos, elapsed_time, inertia_factor_fwd, tick_interval, y_target)

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


def generate_trajectory(
    target_position: Position,
    previous_position: Position,
    elapsed_time: float,
    robot_position: Position,
    config: Config,
    sim_points: list[SimPoint],
) -> AllCommandBuffers:
    """Génère les buffers de commandes pour atteindre la cible.

    Utilise l'heuristique d'inertie pour arrêter la poussée au bon moment afin
    que le robot glisse jusqu'à la cible sans la dépasser.
    """
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
        float(config.others.rc_control_dt),
        float(target_position.x),
        float(target_position.y),
        float(prev_x),
        float(prev_y),
        float(config.inertia_factor.forward),
        float(config.inertia_factor.translate),
        float(elapsed_time),
        float(robot_position.x),
        float(robot_position.y),
        float(config.movement_coeff.forward),
        float(config.movement_coeff.translate),
    )

    # Point de debug : position d'arrêt prédite par l'inertie.
    # predicted_x = target.x - x_dir * x_coast_delta  (car x_coast_delta = (target - predicted) * x_dir)
    # predicted_y = target.y + y_dir * y_coast_delta
    sim_points.append(SimPoint(
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
               position robot : {robot_position.x, robot_position.y, robot_position.direction}
               direction X    : {x_dir}
               direction Y    : {y_dir}
               delta inertie X: {x_coast_delta}
               delta inertie Y: {y_coast_delta}
               buffer forward : {forward_buffer}
               buffer translate: {translate_buffer}
               buffer rotate  : {rotate_buffer}"""
        )

    return AllCommandBuffers(forward=forward_buffer, translate=translate_buffer, rotate=rotate_buffer)
