from abc import ABC, abstractmethod
from typing import Literal, Optional, cast

from redis import StrictRedis

from src.config_manager import Config
from src.utils import ProcessNames, Position, Command, SimPoint, logger

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
        self.redis.close()

    def has_target(self) -> bool:
        """Vérifie si une cible est définie et accessible."""
        return self._get_target_position() is not None

    def _add_sim_point(self, point: SimPoint) -> None: ...

    def _add_all_sim_points(self, points: list[SimPoint]) -> None: ...