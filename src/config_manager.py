from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class RedisConfig(BaseModel):
    """Configuration de la connexion Redis."""
    host: str = "localhost"
    port: int
    db: int = 0


class SerialConfig(BaseModel):
    """Configuration du port série."""
    port_name: str
    baud_rate: int
    timeout: float


class I2CConfig(BaseModel):
    """Configuration du bus I2C."""
    bus: int
    address: int


class BluetoothConfig(BaseModel):
    """Configuration de la connexion Bluetooth BLE."""
    address: str
    char_uuid: str


class WifiConfig(BaseModel):
    """Configuration de la connexion Wi-Fi (TCP)."""
    host: str
    port: int


class SimWindowConfig(BaseModel):
    """Configuration de la fenêtre du simulateur."""
    width: int
    height: int


class SimStartPositionConfig(BaseModel):
    """Position de départ du robot dans le simulateur."""
    x: float
    y: float
    direction: float


class SimConfig(BaseModel):
    """Configuration complète du simulateur Pygame."""
    window: SimWindowConfig
    tick_rate: int = 60
    start_position: SimStartPositionConfig


class ProtocolsConfig(BaseModel):
    """Configuration de tous les protocoles de communication disponibles."""
    serial: SerialConfig
    i2c: I2CConfig
    bluetooth: BluetoothConfig
    wifi: WifiConfig
    sim: SimConfig


class MovementCoeffConfig(BaseModel):
    """Coefficients de mise à l'échelle des mouvements par axe."""
    forward: float = 1.0
    translate: float = 1.0
    rotate: float = 1.0


class InertiaFactorConfig(BaseModel):
    """Facteurs d'inertie (patinage) par axe, entre 0.0 (aucun) et 1.0 (maximum)."""
    forward: float = Field(default=0.0, ge=0.0, le=1.0)
    translate: float = Field(default=0.0, ge=0.0, le=1.0)
    rotate: float = Field(default=0.0, ge=0.0, le=1.0)


class LoggerConfig(BaseModel):
    """Configuration du logger."""
    log_freq: float = 0.5


class UtilsConfig(BaseModel):
    """Configuration des utilitaires."""
    logger: LoggerConfig


class OthersConfig(BaseModel):
    """Paramètres divers du système."""
    previous_position_buffer_len: int
    # Intervalle entre deux ticks du contrôleur RC (doit correspondre au time.sleep dans rc_control_process)
    rc_control_dt: float = 0.01


class Config(BaseModel):
    """Configuration globale du système, chargée depuis un fichier YAML."""
    redis: RedisConfig
    protocols: ProtocolsConfig
    movement_coeff: MovementCoeffConfig
    inertia_factor: InertiaFactorConfig
    utils: UtilsConfig
    others: OthersConfig

    @classmethod
    def load_from_yml(cls, yml_path: Path) -> "Config":
        """Charge et valide la configuration depuis un fichier YAML.

        Args:
            yml_path: Chemin vers le fichier de configuration YAML.

        Returns:
            Instance Config validée par Pydantic.
        """
        with open(yml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return cls(**config)

    def save_to_yml(self, yml_path: Path) -> None:
        """Sauvegarde la configuration dans un fichier YAML.

        Args:
            yml_path: Chemin vers le fichier de destination.
        """
        with open(yml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False)