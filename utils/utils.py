from __future__ import annotations

import asyncio
import copy
import multiprocessing as mp
import sys
import threading
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, astuple
from enum import Enum
from functools import singledispatchmethod
from io import TextIOWrapper
from multiprocessing.managers import ListProxy
from multiprocessing.queues import Queue as MpQueue
from multiprocessing.synchronize import Event as MpEvent
from pprint import pformat
from typing import Optional, TYPE_CHECKING, Any, TypedDict, cast, Protocol, Literal, override

import colorama
import serial
from bleak import BleakClient
from colorama import init
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import PythonTracebackLexer
from redis import StrictRedis
from serial import Serial

init()  # IMPORTANT pour Windows CMD

if TYPE_CHECKING:
    from simulateur import Sim

from .config_manager import *

# ============================================================================
# ============================================================================
# ÉNUMÉRATIONS
# ============================================================================

_counter = 0
def auto():
    global _counter
    _counter += 1
    return _counter

@dataclass(frozen=True)
class LoggingLevelData:
    level: int
    name: str


class LoggingLevel(Enum):
    """Niveaux de logging disponibles."""
    DEBUG = LoggingLevelData(level=auto(), name=colorama.Fore.GREEN + "DEBUG" + colorama.Fore.RESET)
    INFO = LoggingLevelData(level=auto(), name=colorama.Fore.BLUE + "INFO" + colorama.Fore.RESET)
    WARNING = LoggingLevelData(level=auto(), name=colorama.Fore.YELLOW + "WARNING" + colorama.Fore.RESET)
    ERROR = LoggingLevelData(level=auto(), name=colorama.Fore.RED + "ERROR" + colorama.Fore.RESET)
    CRITICAL = LoggingLevelData(level=auto(), name=colorama.Fore.RED + colorama.Style.BRIGHT + "CRITICAL" + colorama.Style.RESET_ALL)


class ProcessNames(str, Enum):
    RC_CONTROL = "RC contrôle"
    TRAJECTORY_CALCULATOR = "Trajectory calculator"
    MAIN = "Main"
    LOGGER = "LOGGER"


class DataclassInstance(Protocol):
    __dataclass_fields__: dict

class DataClassUtils[T, DataclassInstance](ABC):
    """Classe de base utilitaire pour les dataclasses avec méthode copy."""
    def copy(self, use_deepcopy: bool=True) -> DataClassUtils:
        return copy.deepcopy(self) if use_deepcopy else copy.copy(self)

    def astuple(self: T) -> tuple[Any, ...]:
        return astuple(self)

    def aslist(self: T) -> list[Any]:
        return list(astuple(self))

    def asdict(self: T) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls: type[T], data: dict | TypedDict) -> T:
        return from_dict(data_class=cls, data=data)  # type: ignore[arg-type]


@dataclass(frozen=True)
class LogItem(DataClassUtils):
    """Item de log avec niveau et message."""
    level: LoggingLevel
    msg: str


@dataclass(frozen=True)
class Position(DataClassUtils):
    """Position du robot (x, y, direction en degrés)."""
    x: float
    y: float
    direction: float


@dataclass(frozen=True)
class Color(DataClassUtils):
    """Couleur RGB pour l'affichage dans le simulateur."""
    red: int
    green: int
    blue: int


@dataclass(frozen=True)
class SimPoint(DataClassUtils):
    """Point de debug affiché dans la fenêtre du simulateur."""
    name: str
    position: Position
    color: Color
    radius: int


@dataclass(frozen=True)
class PreviousPosition:
    """Position précédente avec timestamp pour calcul de vitesse."""
    position: Position
    timestamp: float


@dataclass(frozen=True)
class Observation(DataClassUtils):
    """Observation complète : position courante du robot et cible optionnelle."""
    robot_position: Position
    target_position: Optional[Position]


@dataclass(frozen=True)
class Command(DataClassUtils):
    """Commande de mouvement : forward, translate, rotate."""
    forward: float
    translate: float
    rotate: float


@dataclass(frozen=True)
class CommandBufferItem(DataClassUtils):
    """Item de buffer de commande avec temps de fin et valeur."""
    finish_time: float
    command: float


@dataclass(frozen=True)
class AllCommandBuffers(DataClassUtils):
    """Ensemble des buffers de commandes pour tous les axes."""
    forward: CommandBuffer
    translate: CommandBuffer
    rotate: CommandBuffer


class Driver(ABC):
    """Classe abstraite pour gérer la communication avec le robot/simulateur.

    Les méthodes disponibles dépendent du processus appelant (trajectory ou RC control).
    Les méthodes conditionnelles sont assignées dans __init__ ; appeler une méthode
    non assignée pour le processus actuel lèvera AttributeError immédiatement.
    """
    def __init__(self, config: Config, logger: LoggerAPI, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR] | Literal[ProcessNames.RC_CONTROL]):
        self.config = config
        self.logger = logger
        self.process_name = process_name

        self.redis = StrictRedis(host=config.redis.host, port=config.redis.port, db=config.redis.db,
                                 decode_responses=True)

        match process_name:
            case ProcessNames.RC_CONTROL:
                self.send_command = self._send_command
                self.add_sim_point = self._add_sim_point
                self.add_all_sim_points = self._add_all_sim_points
            case ProcessNames.TRAJECTORY_CALCULATOR:
                self.get_robot_position = self._get_robot_position
                self.get_target_position = self._get_target_position

    def _get_target_position(self) -> Position:
        """Récupère la position cible depuis Redis.

        Returns:
            Position avec x, y, direction (peut contenir None si cible non définie).
        """
        x = float(self.redis.get("target_x")) if self.redis.get("target_x") is not None else None
        y = float(self.redis.get("target_y")) if self.redis.get("target_y") is not None else None
        direction = float(self.redis.get("target_direction")) if self.redis.get("target_direction") is not None else None
        return Position(x=x, y=y, direction=direction)

    @abstractmethod
    def _send_command(self, command: Command) -> bool: ...

    def _get_robot_position(self) -> Position:
        """Récupère la position courante du robot depuis Redis."""
        raw_x = cast(float, self.redis.get("robot_x"))
        raw_y = cast(float, self.redis.get("robot_y"))
        raw_direction = cast(float, self.redis.get("robot_direction"))

        if raw_x is None or raw_y is None or raw_direction is None:
            raise ValueError("Position ou direction absente de Redis")

        return Position(x=float(raw_x), y=float(raw_y), direction=float(raw_direction))

    def stop(self) -> None:
        """Arrête le driver : flush Redis et ferme la connexion."""
        self.redis.flushdb()
        self.redis.close()

    def has_target(self) -> bool:
        """Vérifie si une cible est définie et accessible."""
        return self._get_target_position().x is not None

    def _add_sim_point(self, point: SimPoint) -> None: ...

    def _add_all_sim_points(self, points: list[SimPoint]) -> None: ...


class SimDriver(Driver):
    def __init__(self, config: Config, logger: LoggerAPI, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR] | Literal[ProcessNames.RC_CONTROL]):
        super().__init__(config, logger, process_name)

        from simulateur import Sim

        if process_name == ProcessNames.RC_CONTROL:
            self.sim = Sim(
                window_size=(config.sim.window.width, config.sim.window.height),
                tick_rate=config.sim.tick_rate,
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
                    x=config.sim.start_position.x,
                    y=config.sim.start_position.y,
                    direction=config.sim.start_position.direction,
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
        for point in points:
            self.sim.add_sim_point(point)


class SerialDriver(Driver):
    def __init__(self, config: Config, logger: LoggerAPI,
                 process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR] | Literal[ProcessNames.RC_CONTROL]):
        super().__init__(config, logger, process_name)

        # noinspection PyCallingNonCallable
        logger.log("Initializing serial bus...", ProcessNames.RC_CONTROL, LoggingLevel.INFO)
        self.serial_bus = Serial(port=config.serial.port_name, baudrate=config.serial.baud_rate, parity=serial.PARITY_NONE,
                            stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=config.serial.timeout)
        # noinspection PyCallingNonCallable
        logger.log("Serial bus initialized !", ProcessNames.RC_CONTROL, LoggingLevel.INFO)

    @override
    def _send_command(self, command: Command) -> bool:
        self.serial_bus.write(f"{command.forward} {command.rotate} {command.translate}\n".encode())
        return True


class I2CDriver(Driver):
    def __init__(self, config: Config, logger: LoggerAPI,
                 process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR] | Literal[ProcessNames.RC_CONTROL]):
        raise NotImplementedError("I2CDriver is not implemented yet")

    @override
    def _get_target_position(self) -> Position:
        raise NotImplementedError("I2CDriver::_get_target_position is not implemented yet")

    @override
    def _send_command(self, command: Command) -> bool:
        raise NotImplementedError("I2CDriver::_send_command is not implemented yet")


class BluetoothDriver(Driver):
    def __init__(self, config: Config, logger: LoggerAPI,
                 process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR] | Literal[ProcessNames.RC_CONTROL]):
        super().__init__(config, logger, process_name)

        if process_name == ProcessNames.RC_CONTROL:
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)

    @override
    def _send_command(self, command: Command) -> bool:
        asyncio.run_coroutine_threadsafe(self._send_ble(command), self._loop)
        return True

    async def _send_ble(self, command: Command):
        async with BleakClient(self.config.bluetooth.adress) as client:
            await client.write_gatt_char(self.config.bluetooth.char_uuid, f"{command.forward};{command.translate};{command.rotate}".encode())


class WifiDriver(Driver):
    def __init__(self, config: Config, logger: LoggerAPI,
                 process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR] | Literal[ProcessNames.RC_CONTROL]):
        raise NotImplementedError("WifiDriver is not implemented yet")

    @override
    def _get_target_position(self) -> Position:
        raise NotImplementedError("WifiDriver::_get_target_position is not implemented yet")

    @override
    def _send_command(self, command: Command) -> bool:
        raise NotImplementedError("WifiDriver::_send_command is not implemented yet")


class ControlDrivers(Enum):
    SIM = SimDriver
    SERIAL = SerialDriver
    I2C = I2CDriver
    BLUETOOTH = BluetoothDriver
    WIFI = WifiDriver


# ============================================================================
# LOGGING
# ============================================================================

class Tee:
    def __init__(self, *streams: TextIOWrapper):
        self.streams = streams

    def write(self, data: str):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()

    def close(self):
        for s in self.streams:
            s.close()


class Logger(mp.Process):
    """Processus de logging multiprocessus."""
    def __init__(self, log_queue: MpQueue[LogItem], logger_api: LoggerAPI, stop_event: MpEvent, level: LoggingLevel, files: Optional[list[str]]=None) -> None:
        super().__init__()
        self.log_queue = log_queue
        self.stop_event: MpEvent = stop_event
        self.level: LoggingLevel = level
        self.files = files
        self.logger_api = logger_api

    def run(self):
        streams = Tee(*(open(file, "w", encoding="utf-8") for file in self.files) if self.files is not None else [sys.stdout])
        while True:
            if self.stop_event.is_set() and self.log_queue.empty(): break

            # noinspection PyBroadException
            try:
                log_item = self.log_queue.get()
                if log_item.level.value.level >= self.level.value.level: print(log_item.msg, file=streams, flush=True)

            except KeyboardInterrupt:
                if self.log_queue.empty(): pass
                else:
                    self.stop_event.set()
                    streams.close()
            except BaseException as e:
                # noinspection PyBroadException
                try:
                    print(self.logger_api.format_traceback(e, ProcessNames.LOGGER, LoggingLevel.ERROR), file=streams, flush=True)
                except KeyboardInterrupt:
                    if self.log_queue.empty(): pass
                    else:
                        self.stop_event.set()
                        streams.close()
                except BaseException:
                    pass
                break


class LoggerAPI:
    """API de logging pour les processus."""
    def __init__(self, log_freq: float = 0.5):
        self.logger_is_defined = False
        self.files = None
        self._prev_time = time.perf_counter()
        self.log_freq = log_freq * 1000
        self.log_queue = mp.Queue()

    def create_logger(self, stop_event: MpEvent, level: LoggingLevel, files: Optional[list[str]]=None):
        self.files = files
        self.logger_is_defined = True
        return Logger(self.log_queue, self, stop_event, level=level, files=files)

    @staticmethod
    def format_log(msg: str, process: ProcessNames, level: LoggingLevel, use_pprint: bool = False):
        return f"{process.value} | {level.value.name} | {pformat(msg.replace("\n", "")) + ("\n" if msg.endswith("\n") else "") if use_pprint else msg}"

    @staticmethod
    def format_traceback(e: BaseException, process: ProcessNames, level: LoggingLevel):
        colored_e = highlight(
            "".join(traceback.TracebackException.from_exception(e).format()),
            PythonTracebackLexer(),
            TerminalFormatter()
        )
        return LoggerAPI.format_log(colored_e, process, level, use_pprint=False)

    def _log(self, msg: str, level: LoggingLevel, force: bool) -> bool:
        if not self.logger_is_defined:
            raise AttributeError("Logger instance has not been created yet")

        if self._prev_time + self.log_freq > (current_time := time.perf_counter()) or force:
            self.log_queue.put(LogItem(level=level, msg=msg))
            self._prev_time = current_time
            return True
        else:
            return False

    def instant_log(self, msg: str, process: ProcessNames, level: LoggingLevel=LoggingLevel.INFO, use_pprint: bool = False):
        if not self.logger_is_defined:
            raise AttributeError("Logger instance has not been created yet")
        streams = Tee(*(open(file, "w", encoding="utf-8") for file in self.files) if self.files is not None else [sys.stdout])
        print(self.format_log(msg, process, level, use_pprint=use_pprint), file=streams, flush=True)
        streams.close()

    @singledispatchmethod
    def log(self, msg, process: ProcessNames, level: LoggingLevel=LoggingLevel.INFO, use_pprint: bool = False, force: bool = False):
        raise NotImplementedError(f"No log handler for type {type(msg).__name__}")

    @log.register(str)
    def _(self, msg: str, process: ProcessNames, level: LoggingLevel=LoggingLevel.INFO, use_pprint: bool = False, force: bool = False) -> bool:
            return self._log(self.format_log(msg, process, level=level, use_pprint=use_pprint), level=level, force=force)

    @log.register(BaseException)
    def _(self, e: BaseException, process: ProcessNames, level: LoggingLevel=LoggingLevel.INFO, _use_pprint: Optional[Any] = None, force: bool = False) -> bool:
        return self._log(self.format_traceback(e, process, level=level), level=level, force=force)


# ============================================================================
# TYPES ALIAS
# ============================================================================

type CommandBuffer = list[CommandBufferItem]
type SharedCommandBuffer = ListProxy[CommandBufferItem]