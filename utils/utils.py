from __future__ import annotations

import asyncio
import copy
import sys
import threading
import time
import traceback
from abc import ABC
from dataclasses import dataclass, asdict, field
from enum import Enum
import multiprocessing as mp
from functools import singledispatch, singledispatchmethod
from io import TextIOWrapper
from multiprocessing.managers import DictProxy, ListProxy
from multiprocessing.synchronize import Event as MpEvent
from multiprocessing.synchronize import Lock as MpLock
from multiprocessing.queues import Queue as MpQueue
from typing import Optional, Callable, TYPE_CHECKING, Any

import colorama
from bleak import BleakClient
from redis import Redis, StrictRedis

import serial
from serial import Serial

from pprint import pformat

from pygments import highlight
from pygments.lexers import PythonTracebackLexer
from pygments.formatters import TerminalFormatter

from colorama import init
init()  # IMPORTANT pour Windows CMD

if TYPE_CHECKING:
    from simulateur import Sim

from .config_manager import *

# ============================================================================
# VARIABLES GLOBALES
# ============================================================================

serial_bus: Optional[Serial] = None

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





class DataClassUtils(ABC):
    """Classe de base utilitaire pour les dataclasses avec méthode copy."""
    def copy(self, use_deepcopy: bool=True) -> DataClassUtils:
        return copy.deepcopy(self) if use_deepcopy else copy.copy(self)


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
class PreviousPosition:
    """Position précédente avec timestamp pour calcul de vitesse."""
    position: Position
    timestamp: float


@dataclass(frozen=True)
class Observation(DataClassUtils):
    """Observation complète : position robot et cible optionnelle."""
    robot_position: Position
    target_point: Optional[Position]


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


# ============================================================================
# DATACLASSES - HANDLERS CIBLE
# ============================================================================

@dataclass(frozen=True)
class TargetSimHandler(DataClassUtils):
    """Handler de cible pour le mode simulation."""
    global_target_point: DictProxy[str, Optional[float]]
    lock: MpLock
    sim: Optional[Sim] = field(default=None)


@dataclass(frozen=True)
class TargetRedisHandler(DataClassUtils):
    """Handler de cible pour le mode Redis."""
    redis_db: Redis


@dataclass(frozen=True)
class TargetHandler(DataClassUtils):
    """Handler de cible polymorphique (sim ou redis)."""
    sim_handler: Optional[TargetSimHandler] = field(default=None)
    redis_handler: Optional[TargetRedisHandler] = field(default=None)


@dataclass(frozen=True)
class RobotPosSimHandler(DataClassUtils):
    """Handler de position robot pour le mode simulation."""
    redis_db: Redis


@dataclass(frozen=True)
class RobotPosRedisHandler(DataClassUtils):
    """Handler de position robot pour le mode Redis."""
    redis_db: Redis


@dataclass(frozen=True)
class RobotPosHandler(DataClassUtils):
    """Handler de position robot polymorphique (sim ou redis)."""
    sim_handler: Optional[RobotPosSimHandler] = field(default=None)
    redis_handler: Optional[RobotPosRedisHandler] = field(default=None)


class ControlHandlerBase:
    ...


@dataclass(frozen=True)
class ControlSimHandler(DataClassUtils, ControlHandlerBase):
    """Handler de contrôle pour le mode simulation."""
    sim: Sim
    redis_db: Redis


@dataclass(frozen=True)
class ControlSerialHandler(DataClassUtils, ControlHandlerBase):
    """Handler de contrôle pour le mode série."""
    config: SerialConfig


@dataclass(frozen=True)
class ControlI2CHandler(DataClassUtils, ControlHandlerBase):
    """Handler de contrôle pour le mode I2C (non implémenté)."""
    ...


@dataclass(frozen=True)
class ControlBluetoothHandler(DataClassUtils, ControlHandlerBase):
    bluetooth_manager: BluetoothManager


@dataclass(frozen=True)
class ControlHandler(DataClassUtils):
    """Handler de contrôle polymorphique (sim, serial ou i2c)."""
    sim_handler: ControlSimHandler
    serial_handler: ControlSerialHandler
    i2c_handler: ControlI2CHandler
    bluetooth_handler: ControlBluetoothHandler


@dataclass(frozen=True)
class SimEnvHandler(DataClassUtils):
    """Configuration environnement simulation."""
    use_target_handler: Callable[[TargetHandler], TargetSimHandler]
    use_robot_pos_handler: Callable[[RobotPosHandler], RobotPosSimHandler]
    use_control_handler: Callable[[ControlHandler], ControlSimHandler]


@dataclass(frozen=True)
class SerialEnvHandler(DataClassUtils):
    """Configuration environnement série."""
    use_target_handler: Callable[[TargetHandler], TargetRedisHandler]
    use_robot_pos_handler: Callable[[RobotPosHandler], RobotPosRedisHandler]
    use_control_handler: Callable[[ControlHandler], ControlSerialHandler]


@dataclass(frozen=True)
class I2CEnvHandler(DataClassUtils):
    """Configuration environnement I2C."""
    use_target_handler: Callable[[TargetHandler], TargetRedisHandler]
    use_robot_pos_handler: Callable[[RobotPosHandler], RobotPosRedisHandler]
    use_control_handler: Callable[[ControlHandler], ControlI2CHandler]


@dataclass(frozen=True)
class BluetoothEnvHandler(DataClassUtils):
    """Configuration environnement bluetooth."""
    use_target_handler: Callable[[TargetHandler], TargetRedisHandler]
    use_robot_pos_handler: Callable[[RobotPosHandler], RobotPosRedisHandler]
    use_control_handler: Callable[[ControlHandler], ControlBluetoothHandler]


class EnvHandler(Enum):
    """Énumération des environnements disponibles."""
    SIM = SimEnvHandler(use_target_handler=lambda target_handler: getattr(target_handler, "sim_handler"), use_robot_pos_handler=lambda robot_pos_handler: getattr(robot_pos_handler, "sim_handler"), use_control_handler=lambda control_data: getattr(control_data, "sim_handler"))
    SERIAL = SerialEnvHandler(use_target_handler=lambda target_handler: getattr(target_handler, "redis_handler"), use_robot_pos_handler=lambda robot_pos_handler: getattr(robot_pos_handler, "redis_handler"), use_control_handler=lambda control_data: getattr(control_data, "serial_handler"))
    I2C = I2CEnvHandler(use_target_handler=lambda target_handler: getattr(target_handler, "redis_handler"), use_robot_pos_handler=lambda robot_pos_handler: getattr(robot_pos_handler, "redis_handler"), use_control_handler=lambda control_data: getattr(control_data, "bluetooth_handler"))
    BLUETOOTH = BluetoothEnvHandler(use_target_handler=lambda target_handler: getattr(target_handler, "redis_handler"),
                        use_robot_pos_handler=lambda robot_pos_handler: getattr(robot_pos_handler, "redis_handler"),
                        use_control_handler=lambda control_data: getattr(control_data, "bluetooth_handler"))


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
                    print(self.logger_api.format_traceback(e, process=ProcessNames.LOGGER, level=LoggingLevel.ERROR), file=streams, flush=True)
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
# LOGGING
# ============================================================================

class BluetoothManager:
    def __init__(self, config: Config):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._config = config

    async def _send(self, command: Command):
        async with BleakClient(self._config.bluetooth.adress) as client:
            await client.write_gatt_char(self._config.bluetooth.char_uuid, f"{command.forward};{command.translate};{command.rotate}".encode())

    def send(self, command: Command):
        asyncio.run_coroutine_threadsafe(self._send(command), self._loop)


# ============================================================================
# GESTION DES CIBLES (GET/SET)
# ============================================================================

@singledispatch
def get_target(data) -> Position:
    raise NotImplementedError(f"No handler for type {type(data).__name__}")

@singledispatch
def set_target(data) -> Position:
    raise NotImplementedError(f"No handler for type {type(data)}")

@get_target.register(TargetSimHandler)
def _(sim_handler: TargetSimHandler) -> Position:
    with sim_handler.lock:
        return Position(**copy.deepcopy(dict(sim_handler.global_target_point)))

@set_target.register(TargetSimHandler)
def _(sim_handler: TargetSimHandler) -> Optional[Position]:
    target = sim_handler.sim.target_point or None
    with sim_handler.lock:
        sim_handler.global_target_point.clear()
        if target is not None: sim_handler.global_target_point.update(asdict(target))
        else: sim_handler.global_target_point.update({"x": None, "y": None, "direction": None})
    return target

@get_target.register(TargetRedisHandler)
def _(redis_handler: TargetRedisHandler) -> Position:
    redis_db = redis_handler.redis_db
    x = redis_db.get("x_target")
    y = redis_db.get("y_target")
    direction = redis_db.get("target_direction")
    return Position(x=x, y=y, direction=direction)

@set_target.register(TargetRedisHandler)
def _(redis_handler: TargetRedisHandler) -> Optional[Position]:
    return get_target(redis_handler)


# ============================================================================
# REDIS - CLIENT ET POSITION ROBOT
# ============================================================================

def create_redis_client(cfg: RedisConfig) -> Redis:
    """Crée et retourne un client Redis."""
    return StrictRedis(host=cfg.host, port=cfg.port, db=cfg.db, decode_responses=True)

def get_robot_pose(redis_db: Redis, process_name: ProcessNames, logger: Optional[LoggerAPI] = None) -> Position:
    """Récupère la position du robot depuis Redis."""
    x_position_raw = redis_db.get('x_position')
    y_position_raw = redis_db.get('y_position')
    current_direction_raw = redis_db.get('direction')

    if x_position_raw is None or y_position_raw is None or current_direction_raw is None:
        raise ValueError("Position ou direction absent de Redis")

    return Position(x=float(x_position_raw), y=float(y_position_raw), direction=float(current_direction_raw))

@singledispatch
def set_robot_pose(data, _robot_pos: Position) -> None:
    raise NotImplementedError(f"No handler for type {type(data).__name__}")

@set_robot_pose.register(RobotPosSimHandler)
def _(redis_handler: RobotPosSimHandler, robot_pos: Position) -> None:
    redis_handler.redis_db.set('x_position', robot_pos.x)
    redis_handler.redis_db.set('y_position', robot_pos.y)
    redis_handler.redis_db.set('direction', robot_pos.direction)

@set_robot_pose.register(RobotPosRedisHandler)
def _(_redis_handler: RobotPosRedisHandler, _robot_pos: Position) -> None:
    pass


# ============================================================================
# ENVOI DE COMMANDES (SIMULATION / SÉRIE / I2C)
# ============================================================================

@singledispatch
def send_command(data, _command: Command) -> bool:
    raise NotImplementedError(f"No handler for type {type(data).__name__}")

@send_command.register(ControlSimHandler)
def _(sim_handler: ControlSimHandler, command: Command, _logger_or_none: Optional[LoggerAPI] = None) -> bool:
    """Envoie une commande au simulateur."""
    running, obs = sim_handler.sim.move(rotate=command.rotate, forward=command.forward, translate=command.translate)
    sim_handler.redis_db.set('x_position', obs.robot_position.x)
    sim_handler.redis_db.set('y_position', obs.robot_position.y)
    sim_handler.redis_db.set('direction', obs.robot_position.direction)
    return running

@send_command.register(ControlSerialHandler)
def _(serial_handler: ControlSerialHandler, command: Command, logger_or_none: Optional[LoggerAPI] = None) -> bool:
    """Envoie une commande via le port série."""
    global serial_bus
    logger = logger_or_none or type("NotLoggerAPI", (LoggerAPI,), {"log": lambda msg, process_name, logging_level: None})()
    config = serial_handler.config
    if serial_bus is None:
        # noinspection PyCallingNonCallable
        logger.log("Initializing serial bus...", ProcessNames.RC_CONTROL, LoggingLevel.INFO)
        serial_bus = Serial(port=config.port_name, baudrate=config.baud_rate, parity=serial.PARITY_NONE,
                      stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=config.timeout)
        # noinspection PyCallingNonCallable
        logger.log("Serial bus initialized !", ProcessNames.RC_CONTROL, LoggingLevel.INFO)

    serial_bus.write(f"{command.forward} {command.rotate} {command.translate}\n".encode())
    return True

@send_command.register(ControlI2CHandler)
def _(_i2c_handler: ControlI2CHandler, _command: Command, _logger_or_none: Optional[LoggerAPI] = None) -> bool:
    raise NotImplementedError("I2C control not implemented yet")

@send_command.register(ControlBluetoothHandler)
def _(bluetooth_handler: ControlBluetoothHandler, command: Command, _logger_or_none: Optional[LoggerAPI] = None) -> bool:
    bluetooth_handler.bluetooth_manager.send(command)
    return True

# ============================================================================
# TYPES ALIAS
# ============================================================================

type CommandBuffer = list[CommandBufferItem]
type SharedCommandBuffer = ListProxy[CommandBufferItem]