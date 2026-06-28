from abc import ABC, abstractmethod
from dataclasses import dataclass

import time

from src.utils import Position, AllCommandBuffers
from src.config_manager import MovementCoeffConfig, InertiaFactorConfig


@dataclass
class StrategyConfig:
    """Configuration pour les stratégies de trajectoire.

    Contient les paramètres de mouvement et d'inertie nécessaires aux stratégies.
    """
    movement_coeff: MovementCoeffConfig
    inertia_factor: InertiaFactorConfig
    rc_control_dt: float


class TrajectoryStrategy(ABC):
    """Classe abstraite pour les stratégies de calcul de trajectoire.

    Chaque stratégie implémente son propre algorithme pour planifier
    une trajectoire du robot vers une cible, en tenant compte de l'inertie.
    """

    def __init__(self, config: StrategyConfig) -> None:
        """Initialise la stratégie avec sa configuration.

        Args:
            config: Configuration de la stratégie (coefficients, facteurs, etc.)
        """
        self.config = config
        self.previous_time = time.time()

    @abstractmethod
    def compute(
        self,
        target_position: Position,
        robot_position: Position,
        measured_position: Position,
        dt_mesure: float,
    ) -> AllCommandBuffers:
        """Calcule les buffers de commandes pour atteindre la cible.

        Args:
            target_position: Position cible (x, y, direction)
            robot_position: Position courante du robot
            measured_position: Position mesurée précédemment (pour mesurer la vitesse)
            dt_mesure: Temps écoulé depuis la mesure précédente

        Returns:
            AllCommandBuffers contenant les buffers forward, translate, rotate
        """
        pass

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Nom explicite de la stratégie pour les logs."""
        pass
