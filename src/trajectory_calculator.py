from math import sqrt, atan2, pi, ceil, log, cos, sin

from src import *

import time
from collections import deque
from typing import cast, Optional, override

from loguru import logger
from numba import njit  # type: ignore[import-untyped]

from src.processes import RobotProcess, ProcessConfig, SharedResources
from src.utils import ProcessNames
from src.trajectories import TrajectoryStrategy, TrajectoryStrategies, StrategyConfig

DEBUG = False

MAX_FORWARD_SPEED: float = 100.0
MAX_TRANSLATE_SPEED: float = 100.0
MAX_ROTATE_SPEED: float = 100.0

class TrajectoryCalculatorProcess(RobotProcess):
    """Processus de calcul de trajectoire.

    Lit la position du robot et la cible, calcule les buffers de commandes
    à appliquer pour atteindre la cible en tenant compte de l'inertie.
    """

    def __init__(self, shared: SharedResources, config: ProcessConfig, strategy_class: type[TrajectoryStrategy]) -> None:
        super().__init__(shared, config, daemon=True)
        self._position_history: Optional[deque[PreviousPosition]] = None
        self._robot_position: Optional[Position] = None
        self._current_time = time.time()
        self._sim_points: list[SimPoint] = []
        self._strategy_class = strategy_class
        self._strategy: Optional[TrajectoryStrategy] = None

    @override
    @property
    def process_name(self) -> ProcessNames:
        return ProcessNames.TRAJECTORY_CALCULATOR

    @override
    @property
    def exit_code_on_error(self) -> int:
        return 1

    @property
    def position_history(self) -> deque[PreviousPosition]:
        if self._position_history is None:
            self._position_history = deque(maxlen=self.config.others.previous_position_buffer_len)
        assert self._position_history is not None
        return self._position_history

    @position_history.setter
    def position_history(self, history: deque[PreviousPosition]) -> None:
        self._position_history = history

    @property
    def robot_position(self) -> Position:
        assert self._robot_position is not None
        return self._robot_position

    @robot_position.setter
    def robot_position(self, position: Position) -> None:
        self._robot_position = position

    @property
    def strategy(self) -> TrajectoryStrategy:
        """Stratégie de trajectoire initialisée lazily."""
        if self._strategy is None:
            # Créer une config pour la stratégie
            strategy_config = StrategyConfig(
                movement_coeff=self.config.movement_coeff,
                inertia_factor=self.config.inertia_factor,
                rc_control_dt=self.config.others.rc_control_dt,
            )
            self._strategy = self._strategy_class(strategy_config)
            logger.info(f"Stratégie de trajectoire initialisée : {cast(TrajectoryStrategy, self._strategy).strategy_name}")

        return cast(TrajectoryStrategy, self._strategy)

    def _get_previous_position(self) -> tuple[Position, float]:
        """Calcule la position de référence pour mesurer la vitesse."""
        if len(self.position_history) >= self.config.others.previous_position_buffer_len:
            oldest_position_record = self.position_history.popleft()
            return oldest_position_record.position, self._current_time - oldest_position_record.timestamp
        else:
            return self.robot_position, 0

    def _update_command_buffers(self, command_buffers: AllCommandBuffers) -> None:
        """Écrit les buffers de commandes dans le partage multiprocessing."""
        with self.shared.command_buffers_lock:
            self.shared.forward_command_buffer[:] = command_buffers.forward
            self.shared.translate_command_buffer[:] = command_buffers.translate
            self.shared.rotate_command_buffer[:] = command_buffers.rotate

    def _planify_trajectory(
            self,
            target_position: Position,
            previous_position: Position,
            elapsed_time: float,
    ) -> AllCommandBuffers:
        """Calcule les buffers de commandes via la stratégie configurée."""
        command_buffers = self.strategy.compute(
            target_position=target_position,
            robot_position=self.robot_position,
            previous_position=previous_position,
            elapsed_time=elapsed_time,
        )

        # Si la stratégie fournit des points de debug (cas MixedMovementStrategy)
        if hasattr(self.strategy, 'sim_points'):
            self._sim_points.extend(self.strategy.sim_points)

        return command_buffers

    @override
    def stop(self) -> None:
        self.shared.stop_event.set()
        self.driver.stop()

    @override
    def _run_impl(self) -> None:
        while not self.shared.stop_event.is_set():
            time.sleep(0.02)

            self._sim_points = []
            self._current_time = time.time()

            target_position = self.driver.get_target_position()
            if not self.driver.has_target():
                continue

            self.robot_position = self.driver.get_robot_position()
            previous_position, elapsed_time = self._get_previous_position()

            command_buffers = self._planify_trajectory(
                cast(Position, target_position),
                previous_position,
                elapsed_time,
            )

            self.position_history.append(PreviousPosition(position=self.robot_position, timestamp=self._current_time))

            self._update_command_buffers(command_buffers)

            with self.shared.shared_sim_points_lock:
                self.shared.shared_sim_points[:] = self._sim_points.copy()