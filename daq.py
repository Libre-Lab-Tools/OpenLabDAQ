"""
daq.py

Controls the complete OpenLabDAQ data acquisition system.

Responsibilities
----------------
- Load the configuration.
- Create enabled sensor drivers.
- Connect and disconnect sensors.
- Acquire measurements.
- Add acquisition records to History.
- Start and stop CSV logging.
"""

from datetime import datetime
from importlib import import_module
from time import monotonic

from config import load_config
from history import History
from logger import Logger


class DAQ:
    """
    Coordinates sensors, History, and Logger.
    """

    def __init__(self):

        self.config = load_config()

        self.period = (
            self.config["acquisition"]["period_ms"] / 1000
        )

        self.history = History()

        self.logger = Logger(
            self.config["logging"]["directory"]
        )

        self.sensors = self.create_enabled_sensors()

        # Automatic mode logs by default.
        # The GUI disables logging until LOAD is pressed.
        self.logging = True

        self.first_record = True

        # Runtime sensor failures are isolated after startup.
        # Startup connection errors still abort DAQ startup in connect().
        self.sensor_states = {
            sensor: {
                "failed": False,
                "last_retry": 0.0,
            }
            for sensor in self.sensors
        }

        # Failed sensors are reconnected periodically rather than on every
        # acquisition cycle.
        self.reconnect_interval = 60.0

        # Runtime events are collected here for the GUI to add to the
        # existing human-readable logbook.
        self.runtime_events = []

    # ---------------------------------------------------------
    # Sensor creation
    # ---------------------------------------------------------

    def load_sensor_class(self, sensor_name):
        """
        Import and return a sensor class by name.
        """

        module = import_module(
            f"sensors.{sensor_name}"
        )

        return getattr(
            module,
            sensor_name,
        )

    def create_enabled_sensors(self):
        """
        Create driver objects for all enabled sensors.

        Disabled sensors remain in config.json but are ignored.
        """

        sensors = []

        for sensor_name, settings in self.config["sensors"].items():

            if not settings["enabled"]:
                continue

            port = settings["port"]

            if not port:
                raise ValueError(
                    f"{sensor_name} is enabled but has no COM port."
                )

            sensor_class = self.load_sensor_class(
                sensor_name
            )

            sensors.append(
                sensor_class(port)
            )

        return sensors

    # ---------------------------------------------------------
    # Connection control
    # ---------------------------------------------------------

    def connect(self):
        """
        Connect every enabled sensor.
        """

        print("\nConnecting sensors...")

        for sensor in self.sensors:

            sensor.connect()

            print(
                f"Connected: {sensor.NAME}"
            )

    def disconnect(self):
        """
        Disconnect every sensor and close the log file.
        """

        print("\nDisconnecting sensors...")

        for sensor in self.sensors:

            sensor.disconnect()

            print(
                f"Disconnected: {sensor.NAME}"
            )

        self.logger.close()

    # ---------------------------------------------------------
    # Logging control
    # ---------------------------------------------------------

    def start_logging(self):
        """
        Enable CSV logging.
        """

        self.logging = True

    def stop_logging(self):
        """
        Disable CSV logging.
        """

        self.logging = False

    # ---------------------------------------------------------
    # Acquisition
    # ---------------------------------------------------------

    def acquire_once(self):
        """
        Read every enabled sensor and create one record.

        Returns
        -------
        dict
            Complete acquisition record.
        """

        record = {
            "Timestamp": datetime.now()
        }

        for sensor in self.sensors:

            column = (
                f"{sensor.NAME} ({sensor.UNIT})"
            )

            state = self.sensor_states[sensor]

            if state["failed"]:
                record[column] = self._retry_failed_sensor(
                    sensor,
                    state,
                )
                continue

            try:
                record[column] = sensor.read()

            except Exception as error:
                record[column] = None
                state["failed"] = True
                state["last_retry"] = monotonic()

                self._add_runtime_event(
                    "Sensor communication failed",
                    f"{sensor.NAME}: {error}",
                )

        self.history.add(record)

        if self.logging:

            if self.first_record:

                self.logger.new_file(record)

                self.first_record = False

            self.logger.write(record)

        return record
    # ---------------------------------------------------------
    # Runtime sensor recovery
    # ---------------------------------------------------------

    def _retry_failed_sensor(self, sensor, state):
        """
        Periodically try to reconnect and read a failed sensor.

        Returns
        -------
        float or None
            A recovered reading, or None while the sensor remains unavailable.
        """

        now = monotonic()

        if now - state["last_retry"] < self.reconnect_interval:
            return None

        state["last_retry"] = now

        try:
            try:
                sensor.disconnect()
            except Exception:
                pass

            sensor.connect()
            value = sensor.read()

        except Exception:
            return None

        state["failed"] = False

        self._add_runtime_event(
            "Sensor communication restored",
            sensor.NAME,
        )

        return value

    def _add_runtime_event(self, event, comment=""):
        """
        Store one DAQ event for the GUI to add to the active logbook.
        """

        self.runtime_events.append(
            {
                "event": str(event),
                "comment": str(comment),
            }
        )

    def pop_runtime_events(self):
        """
        Return and clear runtime sensor events.
        """

        events = self.runtime_events.copy()
        self.runtime_events.clear()
        return events

