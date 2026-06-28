import asyncio
import threading
from typing import Literal, override

from bleak import BleakClient

from src.config_manager import Config
from src.utils import ProcessNames, Command

from ..driver import Driver


class BluetoothDriver(Driver):
    """Driver pour la communication Bluetooth BLE avec le robot.

    Utilise bleak dans une boucle asyncio dédiée (thread séparé) pour éviter
    les conflits avec la boucle principale.
    """

    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        super().__init__(config, process_name)

        if process_name == ProcessNames.RC_CONTROL:
            self.loop = asyncio.new_event_loop()
            self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
            self.thread.start()  # démarre la boucle asyncio dans le thread dédié
            self.client = BleakClient(self.config.protocols.bluetooth.address)

    @override
    def _send_command(self, command: Command) -> bool:
        asyncio.run_coroutine_threadsafe(self._send_ble(command), self.loop)
        return True

    async def _send_ble(self, command: Command) -> None:
        """Coroutine asyncio : écrit la commande sur la caractéristique GATT BLE."""
        await self.client.write_gatt_char(self.config.protocols.bluetooth.char_uuid, bytes(command))

    @override
    def stop(self) -> None:
        super().stop()

        # 1. Planifie la déconnexion
        future = asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)

        # 2. Attends la fin de la déconnexion
        try:
            future.result(timeout=5)  # ou None si tu veux bloquer indéfiniment
        except Exception as e:
            print(f"Erreur lors de la déconnexion BLE: {e}")

        # 3. Stoppe proprement la boucle asyncio
        # noinspection PyTypeChecker
        self.loop.call_soon_threadsafe(self.loop.stop)

        # 4. Attend la fin du thread
        self.thread.join()
