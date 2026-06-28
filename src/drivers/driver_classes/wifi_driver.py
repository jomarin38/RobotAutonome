import socket
from typing import Literal, override

from src.config_manager import Config
from src.utils import ProcessNames, Command

from .driver import Driver


class WifiDriver(Driver):
    """Driver pour la communication Wi-Fi TCP avec le robot."""

    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        super().__init__(config, process_name)

        if process_name == ProcessNames.RC_CONTROL:
            self.tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_client.connect((self.config.protocols.wifi.host, config.protocols.wifi.port))

    @override
    def _send_command(self, command: Command) -> bool:
        self.tcp_client.sendall(bytes(command))
        return True

    @override
    def stop(self) -> None:
        super().stop()
        self.tcp_client.shutdown(socket.SHUT_RDWR)
        self.tcp_client.close()
