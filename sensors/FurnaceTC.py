"""
FurnaceTC.py

OpenLabDAQ driver for the Arduino-based furnace thermocouple.

The driver performs one communication transaction per read. It returns
one valid numerical value or raises RuntimeError. Retry and reconnection
policy belongs to the DAQ.
"""

import math
import time

import serial


class FurnaceTC:
    """Driver for the Arduino-based furnace thermocouple."""

    NAME = "FurnaceTC"
    UNIT = "C"
    BAUDRATE = 9600
    TIMEOUT = 1.0

    def __init__(self, port):
        self.port = port
        self.serial = None

    def connect(self):
        """Open the port and verify the programmed Arduino identity."""

        if self.serial is not None and self.serial.is_open:
            return

        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.BAUDRATE,
                timeout=self.TIMEOUT,
                write_timeout=self.TIMEOUT,
            )

            # Opening the serial port resets most Arduino Nano boards.
            time.sleep(2)

            response = self._exchange(b"ID?\n")

            if response != self.NAME:
                raise RuntimeError(
                    f"Expected {self.NAME}, but received {response!r}."
                )

        except RuntimeError:
            self.disconnect()
            raise

        except (
            serial.SerialException,
            serial.SerialTimeoutException,
        ) as error:
            self.disconnect()
            raise RuntimeError(
                f"{self.NAME} could not open {self.port}: {error}"
            ) from error

    def disconnect(self):
        """Close the serial connection safely."""

        if self.serial is not None:
            try:
                if self.serial.is_open:
                    self.serial.close()
            finally:
                self.serial = None

    def read(self):
        """Return one fresh furnace temperature in degrees Celsius."""

        response = self._exchange(b"READ?\n")

        if response == "ERROR":
            raise RuntimeError(
                f"{self.NAME} reported a sensor error."
            )

        try:
            temperature = float(response)

        except ValueError as error:
            raise RuntimeError(
                f"{self.NAME} returned an invalid value: {response!r}"
            ) from error

        if not math.isfinite(temperature):
            raise RuntimeError(
                f"{self.NAME} returned a non-finite temperature: "
                f"{response!r}"
            )

        return temperature

    def get_status(self):
        """Return the optional Arduino status response."""

        return self._exchange(b"STATUS?\n")

    def _exchange(self, command):
        """Send one command and return one decoded response line."""

        if self.serial is None or not self.serial.is_open:
            raise RuntimeError(f"{self.NAME} is not connected.")

        try:
            self.serial.reset_input_buffer()
            self.serial.write(command)
            self.serial.flush()
            raw_response = self.serial.readline()

        except (
            serial.SerialException,
            serial.SerialTimeoutException,
        ) as error:
            raise RuntimeError(
                f"{self.NAME} serial communication failed on "
                f"{self.port}: {error}"
            ) from error

        if not raw_response:
            raise RuntimeError(
                f"{self.NAME} returned no response."
            )

        try:
            return raw_response.decode("ascii").strip()

        except UnicodeDecodeError as error:
            raise RuntimeError(
                f"{self.NAME} returned non-ASCII data: "
                f"{raw_response!r}"
            ) from error
