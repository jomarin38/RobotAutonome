import platform
from typing import Literal, override

from src.config_manager import Config
from src.utils import ProcessNames, Command

from .driver import Driver

if platform.system() != "Windows":
    from smbus2 import SMBus, i2c_msg


class I2CDriver(Driver):
    """Driver pour la communication I2C avec le robot (Linux uniquement)."""

    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        if platform.system() == "Windows":
            raise NotImplementedError("Le driver I2C n'est pas implémenté pour Windows.")
        super().__init__(config, process_name)
        if process_name == ProcessNames.RC_CONTROL:
            self.i2c_bus = SMBus(self.config.protocols.i2c.bus)

    @override
    def _send_command(self, command: Command) -> bool:
        self.i2c_bus.i2c_rdwr(i2c_msg.write(self.config.protocols.i2c.address, bytes(command)))
        return True

    @override
    def stop(self) -> None:
        super().stop()
        self.i2c_bus.close()
