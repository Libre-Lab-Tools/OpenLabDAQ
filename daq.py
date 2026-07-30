"""
daq.py

Controls the complete OpenLabDAQ data acquisition system.

Responsibilities
----------------
- Load the configuration.
- Create enabled sensor drivers.
- Connect and disconnect sensors.
- Acquire measurements.
- Retry short read glitches before declaring a sensor failure.
- Add acquisition records to History.
- Start and stop independent CSV logging sessions.
"""

from datetime import datetime
from importlib import import_module
from time import monotonic, sleep

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

        # Optional name appended to the next timestamped CSV filename.
        # Automatic mode leaves this blank and keeps timestamp-only naming.
        self.logging_experiment_name = ""

        # Runtime sensor failures are isolated after startup.
        # Startup connection errors still abort DAQ startup in connect().
        self.sensor_states = {
            sensor: {
                "failed": False,
                "last_retry": 0.0,
            }
            for sensor in self.sensors
        }

        # A short read glitch is retried before the sensor is marked failed.
        # These are total attempts, including the first read.
        self.read_attempts = 3
        self.read_retry_delay = 0.1

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

        if self.logging or self.logger.file is not None:
            self.stop_logging()
        else:
            self.logger.close()

    # ---------------------------------------------------------
    # Logging control
    # ---------------------------------------------------------

    def start_logging(self, experiment_name=None):
        """
        Begin a new CSV logging session.

        Parameters
        ----------
        experiment_name : str or None
            Optional name appended to the timestamped CSV filename. A blank
            name preserves automatic timestamp-only naming.
        """

        if self.logger.file is not None:
            raise RuntimeError(
                "A CSV logging session is already active."
            )

        self.logging_experiment_name = str(
            experiment_name or ""
        ).strip()

        self.first_record = True
        self.logging = True

    def stop_logging(self):
        """
        End the active CSV logging session.
        """

        active_file_path = self.logger.file_path
        had_open_file = self.logger.file is not None

        self.logging = False
        self.logger.close()
        self.first_record = True
        self.logging_experiment_name = ""

        if had_open_file and active_file_path is not None:
            self._add_runtime_event(
                "Data logging stopped",
                f"CSV file: {active_file_path.name}",
            )

    # ---------------------------------------------------------
    # Acquisition
    # ---------------------------------------------------------

    def acquire_once(self):
        """
        Read every enabled sensor and create one record.

        A sensor read is attempted up to three times before the sensor is
        marked failed. A recovered retry is treated as a normal measurement
        and does not create a runtime event.

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
                record[column] = self._read_with_retries(sensor)

            except Exception as error:
                record[column] = None
                state["failed"] = True
                state["last_retry"] = monotonic()

                # Close the failed connection once. Reconnection is then
                # attempted at the normal one-minute interval.
                try:
                    sensor.disconnect()
                except Exception:
                    pass

                self._add_runtime_event(
                    "Sensor communication failed",
                    f"{sensor.NAME}: {error}",
                )

        self.history.add(record)

        if self.logging:

            started_new_file = False

            if self.first_record:

                self.logger.new_file(
                    record,
                    experiment_name=(
                        self.logging_experiment_name
                    ),
                )

                self.first_record = False
                started_new_file = True

            self.logger.write(record)

            if started_new_file:
                self._add_runtime_event(
                    "Data logging started",
                    f"CSV file: {self.logger.file_path.name}",
                )

        return record

    def _read_with_retries(self, sensor):
        """
        Read one sensor, tolerating short communication glitches.

        Returns
        -------
        float
            First valid value returned by the driver.

        Raises
        ------
        RuntimeError
            If every read attempt fails.
        """

        last_error = None

        for attempt in range(1, self.read_attempts + 1):
            try:
                return sensor.read()

            except Exception as error:
                last_error = error

                if attempt < self.read_attempts:
                    sleep(self.read_retry_delay)

        raise RuntimeError(
            f"{sensor.NAME} failed after "
            f"{self.read_attempts} read attempts. "
            f"Last error: {last_error}"
        ) from last_error

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
            value = self._read_with_retries(sensor)

        except Exception:
            try:
                sensor.disconnect()
            except Exception:
                pass

            return None

        state["failed"] = False
        state["last_retry"] = 0.0

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
