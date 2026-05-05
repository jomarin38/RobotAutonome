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


class MovementCoeffConfig(BaseModel):
    forward: float = 1.0
    translate: float = 1.0
    rotate: float = 1.0


class InertieFactorConfig(BaseModel):
    forward: float = 0.0
    translate: float = 0.0
    rotate: float = 0.0


class LoggerConfig(BaseModel):
    log_freq: float = 0.5


class UtilsConfig(BaseModel):
    logger: LoggerConfig


class OthersConfig(BaseModel):
    prev_pos_buffer_len: int


class Config(BaseModel):
    redis: RedisConfig
    serial: SerialConfig
    sim: SimConfig
    movement_coeff: MovementCoeffConfig
    inertie_factor: InertieFactorConfig
    utils: UtilsConfig
    others: OthersConfig

    @classmethod
    def load_for_yml(cls, yml_path: str) -> "Config":
        with open(yml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return cls(**config)

    def save_to_yml(self, yml_path: str):
        with open(yml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False)