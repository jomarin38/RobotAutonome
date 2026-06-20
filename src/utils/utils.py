from __future__ import annotations

import asyncio
import copy
import inspect
import multiprocessing as mp
import platform
import socket
import struct
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
from typing import Optional, TYPE_CHECKING, Any, TypedDict, cast, Protocol, Literal, override, Callable

import colorama
import serial
from bleak import BleakClient
from colorama import init
from loguru import logger
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import PythonTracebackLexer
from redis import StrictRedis
from serial import Serial
if platform.system() != "Windows": from smbus2 import SMBus, i2c_msg

init()  # IMPORTANT pour Windows CMD

if TYPE_CHECKING:
    from src.simulateur import Sim
    from loguru import Record

from .config_manager import *

# ============================================================================
# ÉNUMÉRATIONS
# ============================================================================


class ProcessNames(str, Enum):
    RC_CONTROL = "RC contrôle"
    TRAJECTORY_CALCULATOR = "Trajectory calculator"
    MAIN = "Main"


class DataclassInstance(Protocol):
    __dataclass_fields__: dict


class DataClassUtils[T](ABC):
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
    forward: Optional[float]
    translate: Optional[float]
    rotate: Optional[float]

    def __bytes__(self) -> bytes:
        return struct.pack(">hhh", *self.astuple())


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
    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        self.config = config
        self.process_name = process_name
        self.logger = logger.bind(cls=self.__class__.__name__)

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

    def _get_target_position(self) -> Optional[Position]:
        """Récupère la position cible depuis Redis.

        Returns:
            Position avec x, y, direction (peut contenir None si cible non définie).
        """
        raw_x = cast(Optional[str], self.redis.get("target_x"))
        raw_y = cast(Optional[str], self.redis.get("target_y"))
        raw_direction = cast(Optional[str], self.redis.get("target_direction"))

        x = float(raw_x) if raw_x is not None else None
        y = float(raw_y) if raw_y is not None else None
        direction = float(raw_direction) if raw_direction is not None else None
        return Position(x=cast(float, x), y=cast(float, y), direction=cast(float, direction)) if None not in [x, y, direction] else None

    @abstractmethod
    def _send_command(self, command: Command) -> bool: ...

    def _get_robot_position(self) -> Position:
        """Récupère la position courante du robot depuis Redis."""
        raw_x = cast(Optional[str], self.redis.get("robot_x"))
        raw_y = cast(Optional[str], self.redis.get("robot_y"))
        raw_direction = cast(Optional[str], self.redis.get("robot_direction"))

        if None in [raw_x, raw_y, raw_direction]:
            raise ValueError("Position ou direction absente de Redis")

        return Position(x=float(cast(str, raw_x)), y=float(cast(str, raw_y)), direction=float(cast(str, raw_direction)))

    def stop(self) -> None:
        """Arrête le driver : flush Redis et ferme la connexion."""
        self.redis.flushdb()
        self.redis.close()

    def has_target(self) -> bool:
        """Vérifie si une cible est définie et accessible."""
        return self._get_target_position() is not None

    def _add_sim_point(self, point: SimPoint) -> None: ...

    def _add_all_sim_points(self, points: list[SimPoint]) -> None: ...


class SimDriver(Driver):
    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        super().__init__(config, process_name)

        from src.simulateur import Sim

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
    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        super().__init__(config, process_name)

        # noinspection PyCallingNonCallable
        if process_name == ProcessNames.RC_CONTROL:
            logger.info("Initializing serial bus...")
            self.serial_bus = Serial(port=config.serial.port_name, baudrate=config.serial.baud_rate, parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=config.serial.timeout)
            # noinspection PyCallingNonCallable
            logger.info("Serial bus initialized !")

    @override
    def _send_command(self, command: Command) -> bool:
        self.serial_bus.write(bytes(command))
        return True

    @override
    def stop(self):
        super().stop()
        self.serial_bus.close()


class I2CDriver(Driver):
    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        if platform.system() == "Windows": raise NotImplementedError("Le driver I2C n'est pas implémenté pour windows.")
        super().__init__(config, process_name)
        if process_name == ProcessNames.RC_CONTROL: self.i2c_bus = SMBus(self.config.i2c.bus)

    @override
    def _send_command(self, command: Command) -> bool:
        self.i2c_bus.i2c_rdwr(i2c_msg.write(self.config.i2c.address, bytes(command)))
        return True

    @override
    def stop(self) -> None:
        super().stop()
        self.i2c_bus.close()


class BluetoothDriver(Driver):
    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        super().__init__(config, process_name)

        if process_name == ProcessNames.RC_CONTROL:
            self.loop = asyncio.new_event_loop()
            self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
            self.client = BleakClient(self.config.bluetooth.address)

    @override
    def _send_command(self, command: Command) -> bool:
        asyncio.run_coroutine_threadsafe(self._send_ble(command), self.loop)
        return True

    async def _send_ble(self, command: Command):
        await self.client.write_gatt_char(self.config.bluetooth.char_uuid, bytes(command))

    @override
    def stop(self) -> None:
        super().stop()
        self.client.disconnect()
        self.loop.stop()
        self.thread.join()


class WifiDriver(Driver):
    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        super().__init__(config, process_name)

        if process_name == ProcessNames.RC_CONTROL:
            self.tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_client.connect((self.config.wifi.host, config.wifi.port))

    @override
    def _send_command(self, command: Command) -> bool:
        self.tcp_client.sendall(bytes(command))
        return True

    @override
    def stop(self) -> None:
        super().stop()
        self.tcp_client.shutdown(socket.SHUT_RDWR)


class Drivers(Enum):
    value: type[Driver]

    SIM = SimDriver
    SERIAL = SerialDriver
    I2C = I2CDriver
    BLUETOOTH = BluetoothDriver
    WIFI = WifiDriver


# ============================================================================
# LOGGING
# ============================================================================

class LoggerUtils:
    @staticmethod
    def format_traceback(e: BaseException) -> str:
        return highlight(
            "".join(traceback.TracebackException.from_exception(e).format()),
            PythonTracebackLexer(),
            TerminalFormatter()
        )


# ============================================================================
# METHODES POUR LE LOGGER
# ============================================================================

def bind_context(record: Record):
    file = record["file"].name
    line = record["line"]
    func = record["function"]

    cls = record["extra"].get("cls")

    if func == "<module>":
        func = "main"

    if cls:
        record["extra"]["context"] = f"{file}::{cls}::{func}:{line}"
    else:
        record["extra"]["context"] = f"{file}::{func}:{line}"


# ============================================================================
# TYPES ALIAS
# ============================================================================

type CommandBuffer = list[CommandBufferItem]
type SharedCommandBuffer = ListProxy[CommandBufferItem]