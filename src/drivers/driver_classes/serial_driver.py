import serial
from serial import Serial
from typing import Literal, override

from src.config_manager import Config
from src.utils import ProcessNames, Command, logger

from .driver import Driver


class SerialDriver(Driver):
    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        super().__init__(config, process_name)

        if process_name == ProcessNames.RC_CONTROL:
            logger.info("Initialisation du bus série...")
            self.serial_bus = Serial(
                port=config.serial.port_name,
                baudrate=config.serial.baud_rate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=config.serial.timeout,
            )
            logger.info("Bus série initialisé.")

    @override
    def _send_command(self, command: Command) -> bool:
        self.serial_bus.write(bytes(command))
        return True

    @override
    def stop(self):
        super().stop()
        self.serial_bus.close()
