import threading
from abc import ABC, abstractmethod
from typing import Optional, cast

from loguru import logger
from redis import StrictRedis

from src.config_manager import Config
from src.utils import Position, Command, SimPoint


class Driver(ABC):
    """Classe abstraite pour gérer la communication avec le robot/simulateur.

    Les méthodes disponibles dépendent du processus appelant (trajectory ou RC control).
    Les méthodes conditionnelles sont assignées dans __init__ ; appeler une méthode
    non assignée pour le processus actuel lèvera AttributeError immédiatement.
    """
    def __init__(self, config: Config):
        self.config = config
        self.logger = logger.bind(cls=self.__class__.__name__)

        self.redis = StrictRedis(host=config.redis.host, port=config.redis.port, db=config.redis.db,
                                 decode_responses=True)

        self._lock = threading.Lock()

    def get_robot_position(self) -> Position:
        """Récupère la position courante du robot depuis Redis."""
        raw_x = cast(Optional[str], self.redis.get("robot_x"))
        raw_y = cast(Optional[str], self.redis.get("robot_y"))
        raw_direction = cast(Optional[str], self.redis.get("robot_direction"))

        if None in [raw_x, raw_y, raw_direction]:
            raise ValueError("Position ou direction absente de Redis")

        return Position(x=float(cast(str, raw_x)), y=float(cast(str, raw_y)), direction=float(cast(str, raw_direction)))

    def get_target_position(self) -> Optional[Position]:
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
    def send_command(self, command: Command) -> bool:
        """Envoie une commande de mouvement au robot.

        Args:
            command: Commande à envoyer (forward, translate, rotate).

        Returns:
            True si le robot est toujours actif, False sinon.
        """
        ...

    def stop(self) -> None:
        """Arrête le driver : flush Redis et ferme la connexion."""
        self.redis.close()

    def has_target(self) -> bool:
        """Vérifie si une cible est définie et accessible."""
        return self.get_target_position() is not None

    def add_sim_point(self, point: SimPoint) -> None:
        """Ajoute un point de debug au simulateur (no-op par défaut)."""
        ...

    def add_all_sim_points(self, points: list[SimPoint]) -> None:
        """Ajoute plusieurs points de debug au simulateur (no-op par défaut)."""
        ...