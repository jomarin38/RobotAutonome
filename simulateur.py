import pygame
import math
from pathlib import Path
from utils import *
from typing import Optional



class Robot(pygame.sprite.Sprite):
    position_x: float
    position_y: float

    def __init__(self, x: float, y: float, angle: float, rotate_coeff: float, forward_coeff: float):
        super().__init__()
        self.image = pygame.image.load(Path(__file__).parent / "robot.png")
        self.rect = self.image.get_rect()

        self.rect.center = (int(x), int(y))
        self.angle = angle
        self.original_image = self.image
        self.position_x: float = float(self.rect.centerx)
        self.position_y: float = float(self.rect.centery)
        self.rotate_coeff = rotate_coeff
        self.forward_coeff = forward_coeff

    def rotate(self, angle: float, dt: float=1.0):
        old_center = self.rect.center
        self.angle += angle * dt / self.rotate_coeff
        self.angle %= 360
        self.image = pygame.transform.rotate(self.original_image, -self.angle)
        self.rect = self.image.get_rect()
        self.rect.center = old_center

    def move(self, distance: float, translate=False, dt: float=1):
        radian_angle = math.radians(self.angle + (translate * 90))
        dx = distance * math.cos(radian_angle)
        dy = distance * math.sin(radian_angle)
        self.position_x += dx * dt / self.forward_coeff
        self.position_y += dy * dt / self.forward_coeff
        self.rect.center = (int(self.position_x), int(self.position_y))

    def set_pos(self, x: float, y: float, angle: float):
        self.position_x = x
        self.position_y = y
        self.angle = angle
        self.image = pygame.transform.rotate(self.original_image, -self.angle)
        self.rect = self.image.get_rect()
        self.rect.center = (int(self.position_x), int(self.position_y))


class Sim:
    def __init__(
        self,
        rotate_coeff: float = 1.0,
        translate_coeff: float = 1.0,
        forward_coeff: float = 1.0,
        window_size: tuple[int, int]=(1000, 700),
        tick_rate: int=60,
        inertie_factor: float=0.0,
        inertie_factor_rotate: Optional[float]=None,
        inertie_factor_forward: Optional[float]=None,
        inertie_factor_translate: Optional[float]=None,
    ):      
        """Simulateur du robot (pygame).

        - La cible est sélectionnée au clic gauche et stockée dans `target_point`.
        - `move()` applique une consigne de rotation / avance / translation.
        """
        self._target_point: Optional[Position] = None
        self.prev_time: Optional[float] = None
        self.robot: Optional[Robot] = None
        pygame.init()

        self.window = pygame.display.set_mode(window_size)
        pygame.display.set_caption("Simulateur")

        self.font = pygame.font.Font(None, 36)

        self.clock = pygame.time.Clock()

        self.running = True
        
        self.tick_rate = tick_rate

        self.forward_coeff = forward_coeff
        self.translate_coeff = translate_coeff
        self.rotate_coeff = rotate_coeff

        self.rotation_speed: float = 0.0
        self.forward_speed: float = 0.0
        self.translate_speed: float = 0.0

        self.inertie_coeff_rotate: float = inertie_factor_rotate or inertie_factor
        self.inertie_coeff_forward: float = inertie_factor_forward or inertie_factor
        self.inertie_coeff_translate: float = inertie_factor_translate or inertie_factor

    def reset(self, robot_position: Position) -> tuple[bool, Observation]:
        self.robot = Robot(robot_position.x, robot_position.y, robot_position.direction, rotate_coeff=self.rotate_coeff, forward_coeff=self.forward_coeff)
        self.target_point = None
        self.running = True
        self.prev_time = time.perf_counter()
        self.rotation_speed = 0.0
        self.forward_speed = 0.0
        self.translate_speed = 0.0
        return self.running, self.get_observation()

    @property
    def target_point(self) -> Optional[Position]:
        return self._target_point

    @target_point.setter
    def target_point(self, point: Optional[Position]):
        self._target_point = point

    def get_observation(self) -> Observation:
        assert self.robot is not None
        return Observation(robot_position=Position(float(self.robot.position_x), float(self.robot.position_y), float(self.robot.angle)), target_point=self.target_point)

    @property
    def tick_rate(self):
        return self._tick_rate

    @tick_rate.setter
    def tick_rate(self, tick_rate: float):
        self._tick_rate = tick_rate

    def get_dt(self) -> float:
        assert self.prev_time is not None
        current_time = time.perf_counter()
        dt = current_time - self.prev_time
        self.prev_time = current_time
        return dt

    @staticmethod
    def _clamp(x: float, lo: float, hi: float):
        return min(max(x, lo), hi)

    def move(self, rotate: float=0, forward: float=0, translate: float=0) -> tuple[bool, Observation]:
        if rotate != 0:
            self.rotation_speed = rotate
        if forward != 0:
            self.forward_speed = forward
        if translate != 0:
            self.translate_speed = translate

        return self.update(), self.get_observation()

    def _move(self, rotate: float=0, forward: float=0, translate: float=0) -> None:
        dt = self.get_dt()
        assert self.robot is not None
        self.robot.rotate(rotate, dt=dt)
        self.robot.move(forward, translate=False, dt=dt)
        self.robot.move(translate, translate=True, dt=dt)
        
    def set_pos(self, *args) -> bool:
        assert self.robot is not None
        self.robot.set_pos(*args)
        return self.update()

    def update(self) -> bool:
        assert self.robot is not None
        self._move(self.rotation_speed, self.forward_speed, self.translate_speed)
        self.rotation_speed *= self.inertie_coeff_rotate
        self.forward_speed *= self.inertie_coeff_forward
        self.translate_speed *= self.inertie_coeff_translate

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Clic gauche
                    self.target_point = Position(x=event.pos[0], y=event.pos[1], direction=0)
        
        # Remplir la fenetre de blanc
        self.window.fill((255, 255, 255))

        # Tracer un repère en haut a gauche
        pygame.draw.line(self.window, (0, 0, 0), (0, 0), (200, 0), 7)
        pygame.draw.line(self.window, (0, 0, 0), (0, 0), (0, 200), 7)
        x_text = self.font.render("X", True, (0, 0, 0))
        y_text = self.font.render("Y", True, (0, 0, 0))
        zero_text = self.font.render("0", True, (0, 0, 0))
        to_height_ech_text = self.font.render("200", True, (0, 0, 0))
        to_width_ech_text = self.font.render("200", True, (0, 0, 0))
        self.window.blit(x_text, (100, 10))
        self.window.blit(y_text, (10, 100))
        self.window.blit(zero_text, (10, 10))
        self.window.blit(to_width_ech_text, (200, 10))
        self.window.blit(to_height_ech_text, (10, 200))

        self.window.blit(self.robot.image, self.robot.rect)

        # Afficher les coordonnées et l'angle du robot au dessus de lui
        pygame.draw.circle(self.window, (50, 50, 50), (self.robot.position_x, self.robot.position_y), 8)
        pygame.draw.line(self.window, (50, 50, 50), (self.robot.position_x, self.robot.position_y), (self.robot.position_x, self.robot.position_y - 20), 5)
        pygame.draw.line(self.window, (50, 50, 50), (self.robot.position_x, self.robot.position_y -20), (self.robot.position_x - 30, self.robot.position_y - 50), 5)
        pygame.draw.line(self.window, (50, 50, 50), (self.robot.position_x - 30, self.robot.position_y - 50), (self.robot.position_x - 110, self.robot.position_y - 50), 5)

        x_robot_text = self.font.render(f"x: {int(self.robot.position_x)}", True, (0, 0, 0))
        y_robot_text = self.font.render(f"y: {int(self.robot.position_y)}", True, (0, 0, 0))
        a_robot_text = self.font.render(f"α: {int(self.robot.angle)}", True, (0, 0, 0))
        self.window.blit(x_robot_text, (self.robot.position_x - 105, self.robot.position_y - 130))
        self.window.blit(y_robot_text, (self.robot.position_x - 105, self.robot.position_y - 105))
        self.window.blit(a_robot_text, (self.robot.position_x - 105, self.robot.position_y - 80))

        # Si un point cible est sélectionné, tracer un cercle
        if self.target_point is not None:
            pygame.draw.circle(self.window, (255, 0, 0), (self.target_point.x, self.target_point.y), 10)

            # Afficher les coordonées de la cible au dessus d'elle
            x_target_text = self.font.render(f"x: {int(self.target_point.x)}", True, (0, 0, 0))
            y_target_text = self.font.render(f"y: {int(self.target_point.y)}", True, (0, 0, 0))
            self.window.blit(x_target_text, (self.target_point.x - 30, self.target_point.y - 65))
            self.window.blit(y_target_text, (self.target_point.x - 30, self.target_point.y - 40))

        pygame.display.update()

        return self.running

    @staticmethod
    def close():
        pygame.quit()
    
    
if __name__ == "__main__":
    sim = Sim(window_size=(1300, 700), tick_rate=60, rotate_coeff=1.105, forward_coeff=0.38)
    running, _ = sim.reset(Position(x=500, y=300, direction=0))
    obs: Observation = Observation(Position(x=0.0, y=0.0, direction=0.0), None)
    start_time = time.time()
    
    while obs.robot_position.direction <= 270:
        running, obs = sim.move(rotate=100)
    
    print(f"temps : {time.time() - start_time}")
    print(f"angle total : {obs.robot_position.direction}")
    print(f"vitesse : {obs.robot_position.direction/(time.time() - start_time)}°/s")
    sim.close()