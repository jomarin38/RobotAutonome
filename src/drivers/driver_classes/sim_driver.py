from typing import Literal, override

from src.config_manager import Config
from src.utils import ProcessNames, Position, Command, SimPoint

from .driver import Driver


class SimDriver(Driver):
    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        super().__init__(config, process_name)

        from src.simulateur import Sim

        if process_name == ProcessNames.RC_CONTROL:
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
    def _send_command(self, command: Command) -> bool:
        running, _ = self.sim.move(rotate=command.rotate, forward=command.forward, translate=command.translate)
        return running















    @override
    def stop(self):
        super().stop()
        if self.process_name == ProcessNames.RC_CONTROL: self.sim.close()

    @override
    def _add_sim_point(self, point: SimPoint) -> None:
        self.sim.add_sim_point(point)

    @override
    def _add_all_sim_points(self, points: list[SimPoint]) -> None:
        self.sim.add_all_sim_points(points)