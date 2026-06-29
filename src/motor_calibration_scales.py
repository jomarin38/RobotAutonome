import time
from math import sqrt
from pathlib import Path

from src.config_manager import Config
from src.drivers import Driver
from src.drivers import Drivers
from src.utils import Command
from src.utils import ProcessNames

driver_class = Drivers.WIFI.value

SPEED = 30

def calibrate(command: Command, rc_driver: Driver, tc_driver: Driver):
    start_time = time.time()
    start_position = tc_driver.get_robot_position()
    while True:
        if start_time + 1 < time.time():
            break
        rc_driver.send_command(command)
    end_position = tc_driver.get_robot_position()
    traveled_distance = sqrt((end_position.x - start_position.x) ** 2 + (end_position.y - start_position.y) ** 2)
    return SPEED / traveled_distance

def main():
    config = Config.load_from_yml(Path(__file__).parent.parent / "configs" / "config.yml")
    rc_driver = driver_class(config=config, process_name=ProcessNames.RC_CONTROL)
    tc_driver = driver_class(config=config, process_name=ProcessNames.TRAJECTORY_CALCULATOR)

    print(f"forward scale: {calibrate(Command(forward=SPEED, translate=0, rotate=0), rc_driver, tc_driver)}")
    print(f"translate scale: {calibrate(Command(forward=0, translate=SPEED, rotate=0), rc_driver, tc_driver)}")
    print(f"rotate scale: {calibrate(Command(forward=0, translate=0, rotate=SPEED), rc_driver, tc_driver)}")

if __name__ == '__main__':
    main()