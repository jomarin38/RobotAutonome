import sys
import pygame
import math

class Robot(pygame.sprite.Sprite):
    def __init__(self, x, y, angle):
        super().__init__()
        self.image = pygame.image.load("robot.png")
        self.rect = self.image.get_rect()
        self.rect.center = (x, y)
        self.angle = angle
        self.original_image = self.image
        self.position_x = self.rect.centerx
        self.position_y = self.rect.centery

    def rotate(self, angle, dt=1):
        old_center = self.rect.center
        self.angle += angle * dt
        self.angle %= 360
        self.image = pygame.transform.rotate(self.original_image, -self.angle)
        self.rect = self.image.get_rect()
        self.rect.center = old_center

    def move(self, distance, translate=False, dt=1):
        radian_angle = math.radians(self.angle + (translate * 90))
        dx = distance * math.cos(radian_angle)
        dy = distance * math.sin(radian_angle)
        self.position_x += dx * dt
        self.position_y += dy * dt
        self.rect.center = (int(self.position_x), int(self.position_y))
    
    def set_pos(self, x, y, angle):
        self.position_x = x
        self.position_y = y
        self.angle = angle
        
        self.rect.center = (int(self.position_x), int(self.position_y))
        self.image = pygame.transform.rotate(self.original_image, -self.angle)
        self.rect = self.image.get_rect()
        self.rect.center = (int(self.position_x), int(self.position_y))


class Sim:
    def __init__(self, window_size=(1000, 700), tick_rate=60):      
        pygame.init()

        self.window = pygame.display.set_mode(window_size)
        pygame.display.set_caption("Simulateur")

        self.font = pygame.font.Font(None, 36)

        self.clock = pygame.time.Clock()

        self.running = True

        self.tick_rate = tick_rate

    def reset(self, robot_position):
        self.robot = Robot(*robot_position)
        self.target_point = None
        self.running = True
        return self.running, self.get_observation()

    @property
    def target_point(self):
        return self._target_point

    @target_point.setter
    def target_point(self, point: tuple[int, int, int]):
        self._target_point = point

    def get_observation(self):
        return (int(self.robot.position_x), int(self.robot.position_y), int(self.robot.angle), self.target_point)

    @property
    def tick_rate(self):
        return self._tick_rate

    @tick_rate.setter
    def tick_rate(self, tick_rate):
        self._tick_rate = tick_rate

    def get_dt(self):
        return self.clock.tick(self.tick_rate) / 10
    
    def move(self, rotate=0, before_move=0, translate_move=0, dt=1):
        self.robot.rotate(rotate, dt=dt)
        self.robot.move(before_move, translate=False, dt=dt)
        self.robot.move(translate_move, translate=True, dt=dt)
        
        running = self.update()
        return running, self.get_observation()
        
    def set_pos(self, *args):
        self.robot.set_pos(*args)
        running = self.update()
        return running

    def update(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Clic gauche
                    self.target_point = (*event.pos, 0)
        
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

        # Afficher les coordonnees et l'angle du robot au dessus de lui
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

        # Si un point cible est selectionne, tracer un cercle
        if self.target_point is not None:
            pygame.draw.circle(self.window, (255, 0, 0), (self.target_point[0], self.target_point[1]), 10)

            # Afficher les coordonées de la cible au dessus d'elle
            x_target_text = self.font.render(f"x: {int(self.target_point[0])}", True, (0, 0, 0))
            y_target_text = self.font.render(f"y: {int(self.target_point[1])}", True, (0, 0, 0))
            self.window.blit(x_target_text, (self.target_point[0] - 30, self.target_point[1] - 65))
            self.window.blit(y_target_text, (self.target_point[0] - 30, self.target_point[1] - 40))

        pygame.display.update()

        return self.running

    def close(self):
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    sim = Sim(tick_rate=60, window_size=(1000, 1000))
    running, observation = sim.reset((500, 500, 0))
    while running:
        dt = sim.get_dt()
        running, _ = sim.move(rotate=1, before_move=1, translate_move=0, dt=dt)
        
        """
        x_robot, y_robot, _, pos_target = sim.get_observation()
        
        if pos_target:
            x_move = pos_target[0] - x_robot
            y_move = -(pos_target[0] - y_robot)
            
            #x_move = max(min(x_robot, 5), -5)
            #y_move = max(min(y_robot, 5), -5)
            
            print(x_move, y_move)
            
            running = sim.update(rotate=1, before_move=x_move, translate_move=y_move, dt=dt)
        else:
            running = sim.update(rotate=0, before_move=0, translate_move=0, dt=dt)"""

    sim.close()
    
