import serial
from loguru import logger
from serial import Serial
from typing import override

from src.config_manager import Config
from src.utils import Command

from ..driver import Driver


class SerialDriver(Driver):
    """Driver pour la communication série (UART/USB) avec le robot."""

    def __init__(self, config: Config):
        super().__init__(config)

        logger.info("Initialisation du bus série...")
        self.serial_bus = Serial(
            port=config.protocols.serial.port_name,
            baudrate=config.protocols.serial.baud_rate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=config.protocols.serial.timeout,
        )
        logger.info("Bus série initialisé.")

    @override
    def send_command(self, command: Command) -> bool:
        command = Command(command.rotate, command.forward, command.translate)
        self.serial_bus.write(bytes(command))

        return True

    @override
    def stop(self):
        super().stop()
        self.serial_bus.close()
