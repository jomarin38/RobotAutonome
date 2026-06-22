from pathlib import Path

import yaml
from pydantic import BaseModel


class RedisConfig(BaseModel):
    host: str = "localhost"
    port: int
    db: int = 0


class SerialConfig(BaseModel):
    port_name: str
    baud_rate: int
    timeout: float


class I2CConfig(BaseModel):
    bus: int
    address: int


class BluetoothConfig(BaseModel):
    address: str
    char_uuid: str


class WifiConfig(BaseModel):
    host: str
    port: int


class SimWindowConfig(BaseModel):
    width: int
    height: int


class SimStartPositionConfig(BaseModel):
    x: float
    y: float
    direction: float


class SimConfig(BaseModel):
    window: SimWindowConfig
    tick_rate: int = 60
    start_position: SimStartPositionConfig


class ProtocolsConfig(BaseModel):
    serial: SerialConfig
    i2c: I2CConfig
    bluetooth: BluetoothConfig
    wifi: WifiConfig
    sim: SimConfig


class MovementCoeffConfig(BaseModel):
    forward: float = 1.0
    translate: float = 1.0
    rotate: float = 1.0


class InertiaFactorConfig(BaseModel):
    forward: float = 0.0
    translate: float = 0.0
    rotate: float = 0.0


class LoggerConfig(BaseModel):
    log_freq: float = 0.5


class UtilsConfig(BaseModel):
    logger: LoggerConfig


class OthersConfig(BaseModel):
    previous_position_buffer_len: int
    # Intervalle entre deux ticks du contrôleur RC (doit correspondre au time.sleep dans rc_control_process)
    rc_control_dt: float = 0.01


class Config(BaseModel):
    redis: RedisConfig
    protocols: ProtocolsConfig
    movement_coeff: MovementCoeffConfig
    inertia_factor: InertiaFactorConfig
    utils: UtilsConfig
    others: OthersConfig

    @classmethod
    def load_from_yml(cls, yml_path: Path) -> "Config":
        with open(yml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return cls(**config)

    def save_to_yml(self, yml_path: Path):
        with open(yml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False)