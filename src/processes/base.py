from src import *

from abc import ABC, abstractmethod
from dataclasses import dataclass
from multiprocessing import Process
from multiprocessing.managers import ValueProxy, ListProxy
from multiprocessing.synchronize import Lock as MpLock, Event as MpEvent
from pathlib import Path
from typing import Optional, cast

from loguru import logger

from src.drivers import Driver
from src.utils import Config, ProcessNames, SimPoint, LoggerUtils, CommandBufferItem


@dataclass(frozen=True)
class ProcessConfig:
    """Configuration pour un processus robot."""
    config_file_path: Path
    driver_class: type[Driver]


@dataclass
class SharedResources:
    """Ressources partagées entre les processus via multiprocessing.Manager."""
    stop_event: MpEvent
    process_exit_code: ValueProxy[int]
    forward_command_buffer: ListProxy[CommandBufferItem]
    translate_command_buffer: ListProxy[CommandBufferItem]
    rotate_command_buffer: ListProxy[CommandBufferItem]
    shared_sim_points: ListProxy[SimPoint]
    command_buffers_lock: MpLock
    shared_sim_points_lock: MpLock


class RobotProcess(Process, ABC):
    """Classe de base abstraite pour les processus du robot.

    Gère l'initialisation, la gestion d'erreurs et l'arrêt uniforme.
    Les sous-classes implémentent juste _run_impl() avec leur logique métier.
    """

    def __init__(self, shared: SharedResources, config: ProcessConfig, daemon: bool = False) -> None:
        super().__init__(daemon=daemon)
        self._shared = shared
        self._config_path = config.config_file_path
        self._driver_class = config.driver_class

        self._config: Optional[Config] = None
        self._driver: Optional[Driver] = None

    @property
    def shared(self) -> SharedResources:
        """Accès aux ressources partagées."""
        return self._shared

    @property
    def config(self) -> Config:
        """Configuration chargée du fichier YAML."""
        if self._config is None:
            self._config = Config.load_from_yml(self._config_path)
        return cast(Config, self._config)

    @property
    def driver(self) -> Driver:
        """Driver initialisé pour ce processus."""
        if self._driver is None:
            self._driver = self._driver_class(self.config, self.process_name)
        return cast(Driver, self._driver)

    @property
    @abstractmethod
    def process_name(self) -> ProcessNames:
        """Nom du processus pour identification dans les logs."""
        pass

    @property
    @abstractmethod
    def exit_code_on_error(self) -> int:
        """Code de sortie à définir en cas d'erreur."""
        pass

    def run(self) -> None:
        """Point d'entrée du processus. Gère l'initialisation et la gestion d'erreurs."""
        try:
            self._run_impl()
        except KeyboardInterrupt:
            pass
        except BaseException as e:
            logger.critical(LoggerUtils.format_traceback(e))
            self._shared.process_exit_code.set(self.exit_code_on_error)
        finally:
            self.stop()

    @abstractmethod
    def _run_impl(self) -> None:
        """Logique métier du processus. À implémenter par les sous-classes."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Arrêt propre du processus."""
        pass
