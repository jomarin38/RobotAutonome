from enum import Enum

from .driver_classes import Driver, SimDriver, SerialDriver, I2CDriver, BluetoothDriver, WifiDriver


class Drivers(Enum):
    value: type[Driver]

    SIM = SimDriver
    SERIAL = SerialDriver
    I2C = I2CDriver
    BLUETOOTH = BluetoothDriver
    WIFI = WifiDriver
