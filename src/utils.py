from __future__ import annotations

import copy
import struct
import traceback
from abc import ABC
from pydantic.dataclasses import dataclass
from dataclasses import asdict, astuple
from enum import Enum
from multiprocessing.managers import ListProxy
from typing import Optional, TYPE_CHECKING, Any, Protocol

from colorama import init
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import PythonTracebackLexer

init()  # IMPORTANT pour Windows CMD (active les codes ANSI dans le terminal)

if TYPE_CHECKING:
    from loguru import Record

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
    forward: float #Optional[float]
    translate: float #Optional[float]
    rotate: float #Optional[float]

    def __bytes__(self) -> bytes:
        #assert None not in (self.forward, self.translate, self.rotate)
        return struct.pack(">iii", int(self.forward), int(self.translate), int(self.rotate))


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
# LOGGING
# ============================================================================

class LoggerUtils:
    """Utilitaires de formatage pour le logger."""

    @staticmethod
    def format_traceback(e: BaseException) -> str:
        """Formate une exception avec coloration syntaxique pour l'affichage terminal.

        Args:
            e: Exception à formater.

        Returns:
            Traceback formaté avec coloration ANSI.
        """
        return highlight(
            "".join(traceback.TracebackException.from_exception(e).format()),
            PythonTracebackLexer(),
            TerminalFormatter()
        )


# ============================================================================
# PATCHER POUR LE LOGGER
# ============================================================================

def bind_context(record: Record) -> None:
    """Injecte le contexte d'appel (fichier, classe, fonction, ligne) dans chaque log.

    Utilisé comme patcher loguru via logger.configure(patcher=bind_context).
    Ajoute la clé ``extra['context']`` au record sous la forme
    ``fichier::classe::fonction:ligne`` ou ``fichier::fonction:ligne``.

    Args:
        record: Enregistrement de log loguru à enrichir.
    """
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