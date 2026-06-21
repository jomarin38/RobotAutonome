from src import *

import os
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import math
from pathlib import Path

import pygame

class RobotBase(ABC):
    x: float
    y: float
    direction: float

class Robot(pygame.sprite.Sprite, RobotBase):
    """Sprite du robot : gère la physique de déplacement et la rotation."""

    def __init__(
        self,
        x: float,
        y: float,
        direction: float,
        forward_scale: float,
        translate_scale: float,
        rotate_scale: float,
    ):
        super().__init__()
        self.image = pygame.image.load(Path(__file__).parent.parent / "assets" / "robot.png")
        self.rect = self.image.get_rect()

        self.rect.center = (int(x), int(y))
        self.direction: float = direction
        self.original_image = self.image
        self.x: float = float(self.rect.centerx)
        self.y: float = float(self.rect.centery)
        self.forward_scale = forward_scale
        self.translate_scale = translate_scale
        self.rotate_scale = rotate_scale

    def rotate(self, speed: float, dt: float = 1.0) -> None:
        """Applique une rotation proportionnelle au temps écoulé."""
        old_center = self.rect.center
        self.direction += speed * dt / self.rotate_scale
        self.direction %= 360
        self.image = pygame.transform.rotate(self.original_image, -self.direction)
        self.rect = self.image.get_rect()
        self.rect.center = old_center

    def move(self, speed: float, translate: bool = False, dt: float = 1.0) -> None:
        """Déplace le robot selon son cap ou en translation latérale."""
        angle_rad = math.radians(self.direction + (translate * 90))
        delta_x = speed * math.cos(angle_rad)
        delta_y = speed * math.sin(angle_rad)
        self.x += delta_x * dt / self.translate_scale
        self.y += delta_y * dt / self.forward_scale
        self.rect.center = (int(self.x), int(self.y))

    def set_pos(self, x: float, y: float, direction: float) -> None:
        """Téléporte le robot à une position et un angle donnés."""
        self.x = x
        self.y = y
        self.direction = direction
        self.image = pygame.transform.rotate(self.original_image, -self.direction)
        self.rect = self.image.get_rect()
        self.rect.center = (int(self.x), int(self.y))


@dataclass(frozen=True)
class NotDefinedRobot(RobotBase):
    x: float
    y: float
    direction: float


class Sim:
    """Simulateur Pygame du robot.

    - La cible est sélectionnée au clic gauche et stockée dans `target_position`.
    - `move()` applique une consigne de rotation / avance / translation avec patinage :
      la vitesse converge graduellement vers la consigne via le facteur d'inertie.
    """

    def __init__(
        self,
        rotate_scale: float = 1.0,
        translate_scale: float = 1.0,
        forward_scale: float = 1.0,
        window_size: tuple[int, int] = (1000, 700),
        tick_rate: int = 60,
        inertia_factor: float = 0.0,
        inertia_factor_rotate: Optional[float] = None,
        inertia_factor_forward: Optional[float] = None,
        inertia_factor_translate: Optional[float] = None,
        redis: Optional[StrictRedis] = None,
    ):
        self.robot = cast(Robot, None)
        self._target_position: Optional[Position] = None
        self.previous_time: Optional[float] = None
        self.robot: Robot
        pygame.init()

        self.window = pygame.display.set_mode(window_size)
        pygame.display.set_caption("Simulateur")

        self.font = pygame.font.Font(None, 36)
        self.clock = pygame.time.Clock()
        self.running = True
        self._tick_rate = tick_rate

        self.forward_scale = forward_scale
        self.translate_scale = translate_scale
        self.rotate_scale = rotate_scale

        self.rotate_speed: float = 0.0
        self.forward_speed: float = 0.0
        self.translate_speed: float = 0.0

        # Facteurs d'inertie par axe (facteur individuel prioritaire sur le global)
        self.inertia_factor_rotate: float = inertia_factor_rotate if inertia_factor_rotate is not None else inertia_factor
        self.inertia_factor_forward: float = inertia_factor_forward if inertia_factor_forward is not None else inertia_factor
        self.inertia_factor_translate: float = inertia_factor_translate if inertia_factor_translate is not None else inertia_factor

        self.sim_points: dict[str, SimPoint] = {}

        self.redis = redis

        self.reseted = False

    def reset(self, initial_position: Position) -> tuple[bool, Observation]:
        """Réinitialise le simulateur et place le robot à la position de départ."""

        self.robot = Robot(
            initial_position.x,
            initial_position.y,
            initial_position.direction,
            self.forward_scale,
            self.translate_scale,
            self.rotate_scale,
        )
        self.target_position = None
        self.running = True
        self.previous_time = time.perf_counter()
        self.rotate_speed = 0.0
        self.forward_speed = 0.0
        self.translate_speed = 0.0

        self.reseted = True

        return self.running, self.get_observation()

    @property
    def target_position(self) -> Optional[Position]:
        """Position cible sélectionnée par l'utilisateur (clic gauche)."""
        return self._target_position

    @target_position.setter
    def target_position(self, position: Optional[Position]) -> None:
        self._target_position = position

    def add_sim_point(self, sim_point: SimPoint) -> None:
        """Enregistre ou met à jour un point de debug affiché dans la fenêtre."""
        self.sim_points[sim_point.name] = sim_point

    def add_all_sim_points(self, sim_points: list[SimPoint]) -> None:
        """Enregistre ou met à jour plusieurs points de debug en une seule opération."""
        self.sim_points.update({sp.name: sp for sp in sim_points})

    def remove_sim_point(self, name: str) -> bool:
        """Supprime un point de debug par son nom. Retourne True si trouvé."""
        if name in self.sim_points:
            self.sim_points.pop(name)
            return True
        return False

    def get_sim_point(self, name: str) -> Optional[SimPoint]:
        """Retourne un point de debug par son nom, ou None s'il n'existe pas."""
        return self.sim_points.get(name)

    def get_observation(self) -> Observation:
        """Retourne l'observation courante : position robot + cible."""
        assert self.robot is not None
        return Observation(
            robot_position=Position(
                float(self.robot.x),
                float(self.robot.y),
                float(self.robot.direction),
            ),
            target_position=self.target_position,
        )

    def get_dt(self) -> float:
        """Retourne le temps écoulé depuis le dernier appel (secondes réelles)."""
        assert self.previous_time is not None
        current_time = time.perf_counter()
        dt = current_time - self.previous_time
        self.previous_time = current_time
        return dt

    @staticmethod
    def _clamp(x: float, lo: float, hi: float) -> float:
        return min(max(x, lo), hi)

    def move(
        self,
        rotate: Optional[float] = None,
        forward: Optional[float] = None,
        translate: Optional[float] = None,
    ) -> tuple[bool, Observation]:
        """Applique une consigne de mouvement avec patinage (blend vers la consigne).

        None sur un axe = aucune consigne → la vitesse décroît naturellement (inertie).
        La physique est appliquée AVANT le blend pour que l'heuristique reste correcte :
            coast_distance = measured_speed * tick_interval / (1 - inertia_factor)
        """
        if not self.reseted: raise RuntimeError("Un reset doit être fait avant de pouvoir bouger.")

        # 1) Appliquer le mouvement à la vitesse courante (avant blend)
        result = self.update()

        # 2) Blender vers la consigne : speed_new = speed * alpha + cmd * (1 - alpha)
        #    None → cmd = 0 → décroissance exponentielle vers 0 (même formule que l'inertie)
        cmd_rotate = rotate if rotate is not None else 0.0
        cmd_forward = forward if forward is not None else 0.0
        cmd_translate = translate if translate is not None else 0.0

        self.rotate_speed = self.rotate_speed * self.inertia_factor_rotate + cmd_rotate * (1.0 - self.inertia_factor_rotate)
        self.forward_speed = self.forward_speed * self.inertia_factor_forward + cmd_forward * (1.0 - self.inertia_factor_forward)
        self.translate_speed = self.translate_speed * self.inertia_factor_translate + cmd_translate * (1.0 - self.inertia_factor_translate)

        if self.redis is not None:
            self.redis.set('robot_x', self.robot.x)
            self.redis.set('robot_y', self.robot.y)
            self.redis.set('robot_direction', self.robot.direction)

        return result, self.get_observation()

    def _move(self, rotate: float = 0.0, forward: float = 0.0, translate: float = 0.0) -> None:
        """Déplace physiquement le robot d'un tick selon les vitesses courantes."""
        dt = self.get_dt()
        assert self.robot is not None
        self.robot.rotate(rotate, dt=dt)
        self.robot.move(forward, translate=False, dt=dt)
        self.robot.move(translate, translate=True, dt=dt)

    def set_pos(self, *args) -> bool:
        """Téléporte le robot sans appliquer de blend de vitesse."""
        assert self.robot is not None
        self.robot.set_pos(*args)
        return self.update()

    def update(self) -> bool:
        """Applique un tick physique et redessine la fenêtre.

        Le blend/decay est géré par move() — update() n'applique que le déplacement.
        """
        assert self.robot is not None
        self._move(self.rotate_speed, self.forward_speed, self.translate_speed)

        # Traitement des événements Pygame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # clic gauche → définit la cible
                    self.target_position = Position(x=event.pos[0], y=event.pos[1], direction=0)
                    if self.redis:
                        self.redis.set('target_x', event.pos[0])
                        self.redis.set('target_y', event.pos[1])
                        self.redis.set('target_direction', 0)

        # Fond blanc
        self.window.fill((255, 255, 255))

        # Repère (axes X et Y) en haut à gauche
        pygame.draw.line(self.window, (0, 0, 0), (0, 0), (200, 0), 7)
        pygame.draw.line(self.window, (0, 0, 0), (0, 0), (0, 200), 7)
        x_label = self.font.render("X", True, (0, 0, 0))
        y_label = self.font.render("Y", True, (0, 0, 0))
        origin_label = self.font.render("0", True, (0, 0, 0))
        scale_x_label = self.font.render("200", True, (0, 0, 0))
        scale_y_label = self.font.render("200", True, (0, 0, 0))
        self.window.blit(x_label, (100, 10))
        self.window.blit(y_label, (10, 100))
        self.window.blit(origin_label, (10, 10))
        self.window.blit(scale_x_label, (200, 10))
        self.window.blit(scale_y_label, (10, 200))

        # Dessin du robot
        self.window.blit(self.robot.image, self.robot.rect)

        # Affichage des coordonnées du robot avec une ligne de repère
        x_label_robot = self.font.render(f"x: {int(self.robot.x)}", True, (0, 0, 0))
        y_label_robot = self.font.render(f"y: {int(self.robot.y)}", True, (0, 0, 0))
        direction_label_robot = self.font.render(f"α: {int(self.robot.direction)}", True, (0, 0, 0))
        self.window.blit(x_label_robot, (self.robot.x - 100, self.robot.y - 130))
        self.window.blit(y_label_robot, (self.robot.x - 100, self.robot.y - 105))
        self.window.blit(direction_label_robot, (self.robot.x - 100, self.robot.y - 80))

        pygame.draw.circle(self.window, (50, 50, 50), (self.robot.x, self.robot.y), 8)
        pygame.draw.line(self.window, (50, 50, 50), (self.robot.x, self.robot.y), (self.robot.x, self.robot.y - 20), 5)
        pygame.draw.line(self.window, (50, 50, 50), (self.robot.x, self.robot.y - 20), (self.robot.x - 30, self.robot.y - 50), 5)
        label_width = max(x_label_robot.get_width(), y_label_robot.get_width(), direction_label_robot.get_width())
        pygame.draw.line(self.window, (50, 50, 50), (self.robot.x - 30, self.robot.y - 50), (self.robot.x - 30 - label_width, self.robot.y - 50), 5)

        # Dessin de la cible (cercle rouge + coordonnées)
        if self.target_position is not None:
            target = cast(Position, self.target_position)
            pygame.draw.circle(self.window, (255, 0, 0), (target.x, target.y), 10)
            x_label_target = self.font.render(f"x: {int(target.x)}", True, (0, 0, 0))
            y_label_target = self.font.render(f"y: {int(target.y)}", True, (0, 0, 0))
            self.window.blit(x_label_target, (target.x + 30, target.y - 65))
            self.window.blit(y_label_target, (target.x + 30, target.y - 40))

        # Dessin des points de debug (heuristique inertie, etc.)
        for sim_point in self.sim_points.values():
            pygame.draw.circle(self.window, sim_point.color.astuple(), (sim_point.position.x, sim_point.position.y), sim_point.radius)
            point_label = self.font.render(sim_point.name, True, (0, 0, 0))
            self.window.blit(point_label, (sim_point.position.x + 30, sim_point.position.y - 45))

        pygame.display.update()
        return self.running

    @staticmethod
    def close() -> None:
        """Ferme la fenêtre Pygame et libère les ressources."""
        pygame.quit()


if __name__ == "__main__":
    sim = Sim(window_size=(1300, 700), tick_rate=60, rotate_scale=1.105, forward_scale=0.38)
    running, _ = sim.reset(Position(x=500, y=300, direction=0))
    observation: Observation = Observation(Position(x=0.0, y=0.0, direction=0.0), None)
    start_time = time.time()

    while observation.robot_position.direction <= 270:
        running, observation = sim.move(rotate=100)

    print(f"temps : {time.time() - start_time}")
    print(f"angle total : {observation.robot_position.direction}")
    print(f"vitesse : {observation.robot_position.direction / (time.time() - start_time)}°/s")
    sim.close()
