from __future__ import annotations

from abc import ABC, abstractmethod

from dataclasses import dataclass
from multiprocessing import Process
from multiprocessing.managers import ValueProxy, ListProxy, DictProxy
from multiprocessing.synchronize import Lock as MpLock, Event as MpEvent
from pathlib import Path
from typing import Optional, cast, TYPE_CHECKING

import rpyc
from loguru import logger

if TYPE_CHECKING:
    from loguru import Logger

from src.drivers import Driver
from src.config_manager import Config
from src.utils import CommandBufferItem, SimPoint, ProcessNames, LoggerUtils


@dataclass(frozen=True)
class ProcessConfig:
    """Configuration pour un processus robot."""
    config_file_path: Path

@dataclass
class SharedResources:
    """Ressources partagées entre les processus via multiprocessing.Manager."""
    stop_event: MpEvent
    process_exit_code: ValueProxy[int]
    command_buffers: DictProxy[str, list[CommandBufferItem]]
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

        self._config: Optional[Config] = None
        self._driver: Optional[Driver] = None

        self._logger: Optional[Logger] = None
        
    @property
    def logger(self) -> Logger:
        if self._logger is None:
            self._logger = logger.bind(cls=self.__class__.__name__)
        return cast(Logger, self._logger)

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            rpyc_config = {
                "allow_public_attrs": True,
                "allow_all_attrs": True,
                "allow_getattr": True,
                "allow_safe_attrs": True,
                "safe_attrs": set(),
                "include_local_traceback": True,
            }
            self._driver = rpyc.connect("localhost", 18861, config=rpyc_config).root.driver()
        return cast(Driver, self._driver)


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
