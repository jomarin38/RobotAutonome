from multiprocessing import Process
from multiprocessing.managers import ValueProxy, ListProxy
from multiprocessing.synchronize import Lock as MpLock, Event as MpEvent

from src import *

import time

from .drivers import *

class RCControlProcess(Process):
    def __init__(
        self, stop_event: MpEvent, process_exit_code: ValueProxy[int], forward_command_buffer: SharedCommandBuffer,
        translate_command_buffer: SharedCommandBuffer, rotate_command_buffer: SharedCommandBuffer,
        shared_sim_points: ListProxy[SimPoint], command_buffers_lock: MpLock, shared_sim_points_lock: MpLock,
        config_file_path: Path, driver_class: type[Driver]
    ):
        super().__init__()
        self.config_file_path = config_file_path
        self.driver_class = driver_class
        self.buffer_start_time = time.time()

        self._config: Optional[Config] = None
        self._driver: Optional[Driver] = None
        self._previous_buffers = None
        self._current_buffers = None

        self.stop_event = stop_event
        self.process_exit_code = process_exit_code
        self.forward_command_buffer = forward_command_buffer
        self.translate_command_buffer = translate_command_buffer
        self.rotate_command_buffer = rotate_command_buffer
        self.shared_sim_points = shared_sim_points
        self.command_buffers_lock = command_buffers_lock
        self.shared_sim_points_lock = shared_sim_points_lock

    @property
    def config(self) -> Config:
        assert self._config is not None
        return self._config

    @config.setter
    def config(self, config: Config) -> None:
        self._config = config

    @property
    def driver(self) -> Driver:
        assert self._driver is not None
        return self._driver

    @driver.setter
    def driver(self, driver: Driver) -> None:
        self._driver = driver

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

    def setup(self):
        self.config = Config.load_for_yml(self.config_file_path)
        self.driver = self.driver_class(self.config, ProcessNames.RC_CONTROL)

        # Capture initiale des buffers pour détecter les changements de consigne
        self.buffer_start_time = time.time()
        with self.command_buffers_lock:
            self.previous_buffers = AllCommandBuffers(
                forward=copy.deepcopy(list(self.forward_command_buffer)),
                translate=copy.deepcopy(list(self.translate_command_buffer)),
                rotate=copy.deepcopy(list(self.rotate_command_buffer)),
            )

    def stop(self):
        self.stop_event.set()
        self.driver.stop()

    def update_buffers(self):
        with self.command_buffers_lock:
            self.current_buffers = AllCommandBuffers(
                forward=copy.deepcopy(list(self.forward_command_buffer)),
                translate=copy.deepcopy(list(self.translate_command_buffer)),
                rotate=copy.deepcopy(list(self.rotate_command_buffer)),
            )

        # Nouveaux buffers détectés → réinitialise l'horloge de lecture
        if self.current_buffers != self.previous_buffers:
            self.buffer_start_time = time.time()
            self.previous_buffers = self.current_buffers.copy(use_deepcopy=True)

    @staticmethod
    def get_active_command(
            process_name: ProcessNames,
            buffer: CommandBuffer,
            current_time: float,
            buffer_start_time: float,
    ) -> float:
        """Retourne la consigne courante depuis un buffer temporel (récursif).

        Consomme (pop) les items dont le temps de fin (finish_time) est dépassé par rapport
        au temps courant, puis retourne la valeur du premier item encore actif.
        Retourne 0.0 si le buffer est vide ou tous les items sont expirés.

        Args:
            process_name: Nom du processus appelant.
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
        return RCControlProcess.get_active_command(process_name, buffer, current_time, buffer_start_time)

    @override
    def run(self):
        # noinspection PyBroadException
        try:
            self.setup()
            running = self.driver.send_command(Command(None, None, None))
            while not self.stop_event.is_set():
                time.sleep(0.01)  # tick RC à ~100 Hz

                with self.shared_sim_points_lock:
                    sim_points = copy.deepcopy(list(self.shared_sim_points))

                self.driver.add_all_sim_points(sim_points)

                if not running:
                    break

                if not self.driver.has_target():
                    # Pas de cible : arrêt progressif via l'inertie
                    running = self.driver.send_command(Command(None, None, None))
                    continue

                self.update_buffers()

                current_time = time.time()

                # None si le buffer est vide : aucune consigne, l'inertie décroît librement
                forward_command = (
                    self.get_active_command(ProcessNames.RC_CONTROL, self.current_buffers.forward, current_time, self.buffer_start_time)
                    if len(self.current_buffers.forward) > 0 else None
                )
                translate_command = (
                    self.get_active_command(ProcessNames.RC_CONTROL, self.current_buffers.translate, current_time,
                                            self.buffer_start_time)
                    if len(self.current_buffers.translate) > 0 else None
                )
                rotate_command = (
                    self.get_active_command(ProcessNames.RC_CONTROL, self.current_buffers.rotate, current_time,
                                            self.buffer_start_time)
                    if len(self.current_buffers.rotate) > 0 else None
                )

                running = self.driver.send_command(
                    Command(
                        rotate=-rotate_command if rotate_command else None,
                        forward=forward_command,
                        translate=translate_command,
                    ),
                )

        except KeyboardInterrupt:
            pass
        except BaseException as e:
            logger.critical(LoggerUtils.format_traceback(e))
            self.process_exit_code.set(2)
        finally:
            self.stop()