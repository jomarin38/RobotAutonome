from enum import Enum

from .trajectory_strategy import TrajectoryStrategy
from .strategy_classes import TurnThenMoveStrategy, ForwardAndTranslate


class TrajectoryStrategies(Enum):
    """Énumération des stratégies de trajectoire disponibles."""
    value: type[TrajectoryStrategy]

    # Stratégie classique : calcul d'avance et translation indépendants
    TURN_THEN_MOVE = TurnThenMoveStrategy

    # Stratégie moderne : mouvement mixte simultané
    FORWARD_AND_TRANSLATE = ForwardAndTranslate
