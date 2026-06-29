import platform
from typing import override

from src.config_manager import Config
from src.utils import Command

from ..driver import Driver

if platform.system() != "Windows":
    from smbus2 import SMBus, i2c_msg


class I2CDriver(Driver):
    """Driver pour la communication I2C avec le robot (Linux uniquement)."""

    def __init__(self, config: Config):
        if platform.system() == "Windows":
            raise NotImplementedError("Le driver I2C n'est pas implémenté pour Windows.")
        super().__init__(config)
        self.i2c_bus = SMBus(self.config.protocols.i2c.bus)

    @override
    def send_command(self, command: Command) -> bool:
        command = Command(command.rotate, command.forward, command.translate)
        self.i2c_bus.i2c_rdwr(i2c_msg.write(self.config.protocols.i2c.address, bytes(command)))

        return True

    @override
    def stop(self) -> None:
        super().stop()
        self.i2c_bus.close()
