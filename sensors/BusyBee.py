"""
BusyBee.py

OpenLabDAQ driver for the Arduino-based Busy Bee pressure interface.

Purpose
-------
The BusyBee driver translates the Arduino serial communication
protocol into the standard interface used by OpenLabDAQ.

Responsibilities
----------------
- Connect to the configured serial port.
- Verify the connected instrument.
- Read the current pressure as a floating-point value.
- Disconnect from the instrument.

The driver does not perform voltage conversion, pressure calibration,
logging, plotting, timestamp generation, or experiment control.
Voltage conversion and pressure calibration are performed by the
matching BusyBee Arduino firmware.
"""

import math
import time

import serial


class BusyBee:
    """
    Driver for the Arduino-based Busy Bee pressure interface.
    """

    NAME = "BusyBee"
    UNIT = "Torr"
    BAUDRATE = 9600

    def __init__(self, port):
        """
        Create a BusyBee object.

        Parameters
        ----------
        port : str
            Communication port assigned by OpenLabDAQ.
        """

        self.port = port
        self.serial = None

    def connect(self):
        """
        Connect to the instrument and verify its identity.

        Raises
        ------
        RuntimeError
            If the connected device does not identify itself as
            BusyBee.
        """

        self.serial = serial.Serial(
            self.port,
            self.BAUDRATE,
            timeout=1,
        )

        # Opening the serial port resets most Arduino Nano boards.
        time.sleep(2)

        self.serial.reset_input_buffer()

        self.serial.write(b"ID?\n")
        self.serial.flush()

        response = (
            self.serial.readline()
            .decode()
            .strip()
        )

        if response != self.NAME:
            self.disconnect()

            raise RuntimeError(
                f"Expected {self.NAME}, "
                f"but received {response!r}."
            )

    def disconnect(self):
        """
        Close the serial connection.
        """

        if self.serial is not None:
            self.serial.close()
            self.serial = None

    def read(self):
        """
        Read the current Busy Bee pressure.

        Returns
        -------
        float
            Current corrected pressure in Torr.

        Raises
        ------
        RuntimeError
            If the interface is disconnected, returns no response,
            reports an error, or returns an invalid pressure.
        """

        if self.serial is None:
            raise RuntimeError(
                f"{self.NAME} is not connected."
            )

        # Remove any unread serial data before requesting a new value.
        self.serial.reset_input_buffer()

        self.serial.write(b"READ?\n")
        self.serial.flush()

        response = (
            self.serial.readline()
            .decode()
            .strip()
        )

        if response == "":
            raise RuntimeError(
                f"{self.NAME} returned no response."
            )

        if response == "ERROR":
            raise RuntimeError(
                f"{self.NAME} reported a sensor error."
            )

        try:
            pressure = float(response)

        except ValueError as error:
            raise RuntimeError(
                f"{self.NAME} returned an invalid value: "
                f"{response!r}"
            ) from error

        if not math.isfinite(pressure):
            raise RuntimeError(
                f"{self.NAME} returned a non-finite pressure: "
                f"{response!r}"
            )

        if pressure < 0:
            raise RuntimeError(
                f"{self.NAME} returned a negative pressure: "
                f"{response!r}"
            )

        # Do not round. Preserve the pressure supplied by the Arduino.
        return pressure

    def get_status(self):
        """
        Return the current instrument status.

        This optional driver-specific method is not used by the
        OpenLabDAQ backbone.
        """

        if self.serial is None:
            raise RuntimeError(
                f"{self.NAME} is not connected."
            )

        self.serial.reset_input_buffer()

        self.serial.write(b"STATUS?\n")
        self.serial.flush()

        return (
            self.serial.readline()
            .decode()
            .strip()
        )
