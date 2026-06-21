from src import *

import copy
import time
from typing import Optional

from src.processes import RobotProcess, ProcessConfig, SharedResources
from src.utils import ProcessNames


class RCControlProcess(RobotProcess):
    """Processus d'exécution des commandes sur le robot.

    Lit les buffers de commandes, extrait la consigne courante et l'applique
    au robot via le driver. Écrit la position mise à jour dans le système.
    """

    def __init__(self, shared: SharedResources, config: ProcessConfig) -> None:
        super().__init__(shared, config)
        self._buffer_start_time = time.time()
        self._previous_buffers: Optional[AllCommandBuffers] = None
        self._current_buffers: Optional[AllCommandBuffers] = None

    @property
    def previous_buffers(self) -> AllCommandBuffers:
        assert self._previous_buffers is not None
        return self._previous_buffers

    @previous_buffers.setter
    def previous_buffers(self, buffers: AllCommandBuffers) -> None:
        self._previous_buffers = buffers

    @property
    def current_buffers(self) -> AllCommandBuffers:
        assert self._current_buffers is not None
        return self._current_buffers

    @current_buffers.setter
    def current_buffers(self, buffers: AllCommandBuffers) -> None:
        self._current_buffers = buffers

    @override
    @property
    def process_name(self) -> ProcessNames:
        return ProcessNames.RC_CONTROL

    @override
    @property
    def exit_code_on_error(self) -> int:
        return 2

    @staticmethod
    def get_active_command(
            buffer: CommandBuffer,
            current_time: float,
            buffer_start_time: float,
    ) -> float:
        """Retourne la consigne courante depuis un buffer temporel (récursif).

        Consomme (pop) les items dont le temps de fin (finish_time) est dépassé par rapport
        au temps courant, puis retourne la valeur du premier item encore actif.
        Retourne 0.0 si le buffer est vide ou tous les items sont expirés.

        Args:
            buffer: Buffer temporel de commandes.
            current_time: Temps courant (en secondes).
            buffer_start_time: Temps auquel le buffer a commencé à être appliqué.

        Returns:
            La valeur de commande du premier item actif, ou 0.0.
        """
        if len(buffer) == 0:
            return 0.0
        if current_time <= buffer_start_time + buffer[0].finish_time:
            return buffer[0].command
        buffer.pop(0)
        return RCControlProcess.get_active_command(buffer, current_time, buffer_start_time)

    def _initialize_buffers(self) -> None:
        """Capture initiale des buffers pour détecter les changements de consigne."""
        self._buffer_start_time = time.time()
        with self.shared.command_buffers_lock:
            self.previous_buffers = AllCommandBuffers(
                forward=copy.deepcopy(list(self.shared.forward_command_buffer)),
                translate=copy.deepcopy(list(self.shared.translate_command_buffer)),
                rotate=copy.deepcopy(list(self.shared.rotate_command_buffer)),
            )

    def _update_buffers(self) -> None:
        """Lit les buffers partagés et détecte les changements."""
        with self.shared.command_buffers_lock:
            self.current_buffers = AllCommandBuffers(
                forward=copy.deepcopy(list(self.shared.forward_command_buffer)),
                translate=copy.deepcopy(list(self.shared.translate_command_buffer)),
                rotate=copy.deepcopy(list(self.shared.rotate_command_buffer)),
            )

        if self.current_buffers != self.previous_buffers:
            self._buffer_start_time = time.time()
            self.previous_buffers = self.current_buffers.copy(use_deepcopy=True)

    @override
    def stop(self) -> None:
        self.shared.stop_event.set()
        self.driver.stop()

    @override
    def _run_impl(self) -> None:
        self._initialize_buffers()
        running = self.driver.send_command(Command(None, None, None))

        while not self.shared.stop_event.is_set():
            time.sleep(0.01)  # tick RC à ~100 Hz

            with self.shared.shared_sim_points_lock:
                sim_points = copy.deepcopy(list(self.shared.shared_sim_points))

            self.driver.add_all_sim_points(sim_points)

            if not running:
                break

            if not self.driver.has_target():
                running = self.driver.send_command(Command(None, None, None))
                continue

            self._update_buffers()
            current_time = time.time()

            forward_command = (
                self.get_active_command(self.current_buffers.forward, current_time, self._buffer_start_time)
                if self.current_buffers and len(self.current_buffers.forward) > 0 else None
            )
            translate_command = (
                self.get_active_command(self.current_buffers.translate, current_time, self._buffer_start_time)
                if self.current_buffers and len(self.current_buffers.translate) > 0 else None
            )
            rotate_command = (
                self.get_active_command(self.current_buffers.rotate, current_time, self._buffer_start_time)
                if self.current_buffers and len(self.current_buffers.rotate) > 0 else None
            )

            running = self.driver.send_command(
                Command(
                    rotate=-rotate_command if rotate_command else None,
                    forward=forward_command,
                    translate=translate_command,
                ),
            )