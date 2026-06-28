import serial
from loguru import logger
from serial import Serial
from typing import Literal, override

from src.config_manager import Config
from src.utils import ProcessNames, Command

from ..driver import Driver


class SerialDriver(Driver):
    """Driver pour la communication série (UART/USB) avec le robot."""

    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        super().__init__(config, process_name)

        if process_name == ProcessNames.RC_CONTROL:
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
    def _send_command(self, command: Command) -> bool:
        self.serial_bus.write(bytes(command))
        return True

    @override
    def stop(self):
        super().stop()
        if self.process_name == ProcessNames.RC_CONTROL: self.serial_bus.close()
