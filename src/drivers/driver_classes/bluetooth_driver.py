import asyncio
import threading
from typing import Literal, override

from bleak import BleakClient

from src.config_manager import Config
from src.utils import ProcessNames, Command

from .driver import Driver


class BluetoothDriver(Driver):
    def __init__(self, config: Config, process_name: Literal[ProcessNames.TRAJECTORY_CALCULATOR, ProcessNames.RC_CONTROL]):
        super().__init__(config, process_name)

        if process_name == ProcessNames.RC_CONTROL:
            self.loop = asyncio.new_event_loop()
            self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
            self.thread.start()  # démarre la boucle asyncio dans le thread dédié
            self.client = BleakClient(self.config.bluetooth.address)

    @override
    def _send_command(self, command: Command) -> bool:
        asyncio.run_coroutine_threadsafe(self._send_ble(command), self.loop)
        return True

    async def _send_ble(self, command: Command):
        await self.client.write_gatt_char(self.config.bluetooth.char_uuid, bytes(command))

    @override
    def stop(self) -> None:
        super().stop()
        self.client.disconnect()
        self.loop.stop()
        self.thread.join()
