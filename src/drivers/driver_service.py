from pathlib import Path
from typing import cast

from loguru import logger
from rpyc import Service, ThreadedServer

from src.config_manager import Config
from src.drivers import Driver
from src.utils import LockedProxy


class DriverService(Service):
    _driver: Driver
    initialised = False

    @staticmethod
    def set_driver(driver: Driver) -> None:
        DriverService._driver = driver
        DriverService.initialised = True
        
    def driver(self) -> Driver:
        if not DriverService.initialised:
            raise RuntimeError(
                "Le service doit être initialiser avant de pouvoir utiliser le driver."
            )
        return self._driver
    

def run_driver_server(driver_class: type[Driver], config_file: Path) -> None:
    DriverService.set_driver(cast(Driver, LockedProxy(driver_class(Config.load_from_yml(config_file)))))

    server = ThreadedServer(
        DriverService,
        port=18861,
        protocol_config={
            "allow_public_attrs": True,
            "allow_all_attrs": True,
            "allow_getattr": True,
            "allow_safe_attrs": True,
            "safe_attrs": set(),  # IMPORTANT
            "include_local_traceback": True,
        },
    )

    logger.info("[RPyC] Server started")
    server.start()

