from typing import override, Optional

from src.config_manager import Config
from src.utils import Position, Command, SimPoint

from ..driver import Driver


class SimDriver(Driver):
    """Driver pour le simulateur Pygame.

    En mode RC_CONTROL, initialise et pilote le simulateur Pygame.
    En mode TRAJECTORY_CALCULATOR, n'instancie pas le simulateur
    (la position est lue via Redis).
    """

    def __init__(self, config: Config):
        super().__init__(config)

        from src.simulateur import Sim

        self.sim = Sim(
            window_size=(config.protocols.sim.window.width, config.protocols.sim.window.height),
            tick_rate=config.protocols.sim.tick_rate,
            forward_scale=config.movement_coeff.forward,
            translate_scale=config.movement_coeff.translate,
            rotate_scale=config.movement_coeff.rotate,
            inertia_factor_forward=config.inertia_factor.forward,
            inertia_factor_translate=config.inertia_factor.translate,
            inertia_factor_rotate=config.inertia_factor.rotate,
            redis=self.redis
        )
        self.sim.reset(
            Position(
                x=config.protocols.sim.start_position.x,
                y=config.protocols.sim.start_position.y,
                direction=config.protocols.sim.start_position.direction,
            )
        )

    @override
    def get_robot_position(self) -> Position:
        return self.sim.get_observation().robot_position

    @override
    def get_target_position(self) -> Optional[Position]:
        return self.sim.get_observation().target_position

    @override
    def send_command(self, command: Command) -> bool:
        command = Command(command.rotate, command.forward, command.translate)
        running, _ = self.sim.move(rotate=command.rotate, forward=command.forward, translate=command.translate)

        return running

    @override
    def add_sim_point(self, point: SimPoint) -> None:
        self.sim.add_sim_point(point)

    @override
    def add_all_sim_points(self, points: list[SimPoint]) -> None:
        self.sim.add_all_sim_points(points)

    @override
    def stop(self):
        super().stop()
        self.sim.close()