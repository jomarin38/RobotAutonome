import socket
from typing import override

from src.config_manager import Config
from src.utils import Command

from ..driver import Driver


class WifiDriver(Driver):
    """Driver pour la communication Wi-Fi TCP avec le robot."""

    def __init__(self, config: Config):
        super().__init__(config)

        self.tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_client.connect((self.config.protocols.wifi.host, config.protocols.wifi.port))

    @override
    def send_command(self, command: Command) -> bool:
        command = Command(command.rotate, command.forward, command.translate)
        self.tcp_client.sendall(bytes(command))

        return True

    @override
    def stop(self) -> None:
        super().stop()
        self.tcp_client.shutdown(socket.SHUT_RDWR)
        self.tcp_client.close()
