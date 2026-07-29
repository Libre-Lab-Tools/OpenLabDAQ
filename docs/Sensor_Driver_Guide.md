# Sensor Driver Guide

## Purpose

A sensor driver translates one instrument's communication protocol into the standard OpenLabDAQ interface.

The protocol may be Arduino serial, RS-232, RS-485, Modbus, USB, or another command format. OpenLabDAQ does not need to know those details.

## Naming

The following names must match exactly:

- Python filename
- Python class name
- `NAME`
- Sensor key in `config.json`

Example:

```text
sensors/FurnaceTC.py
class FurnaceTC
NAME = "FurnaceTC"
"FurnaceTC" in config.json
```

A physical label should use the same official name when practical. Experiment-specific descriptions belong in the optional GUI nickname.

## Required Interface

```python
sensor = Sensor(port)
sensor.connect()
value = sensor.read()
sensor.disconnect()
```

### Constructor

```python
def __init__(self, port):
```

The constructor stores settings only. It must not open the instrument connection.

### `connect()`

Opens communication and verifies that the expected instrument responds.

Verification depends on the instrument:

- Arduino: request the programmed identity
- Addressed RS-485 device: verify the expected address responds
- Instrument with serial-number query: optionally verify the serial number
- Other instruments: validate a protocol-specific response

Opening a COM port alone is not sufficient verification.

Repeated calls may safely return when already connected.

### `read()`

Performs one communication transaction and returns one fresh measurement already converted to engineering units.

```python
return 523.0
```

`read()` must:

- Require an existing connection
- Never reconnect automatically
- Perform only one driver-level transaction
- Validate the response
- Return a numerical value
- Raise `RuntimeError` on every operational failure

The driver must not retry a failed read. OpenLabDAQ performs short read retries centrally so every instrument receives the same behavior.

### `disconnect()`

Closes communication safely and sets the connection object to `None`.

After disconnection, `read()` must fail clearly.

## Required Constants

```python
NAME = "FurnaceTC"
UNIT = "°C"
```

Drivers may define additional constants such as baud rate, Modbus address, timeout, or register address.

## Driver Responsibilities

A driver shall:

- Connect to one physical instrument
- Verify communication
- Read one fresh measurement
- Convert the value to engineering units
- Validate framing, checksum, CRC, address, and response format when applicable
- Translate library, serial, decoding, protocol, and instrument errors into descriptive `RuntimeError` exceptions

A driver shall not:

- Save files
- Generate timestamps
- Plot data
- Read `config.json`
- Access History, Logger, or the GUI
- Retry failed reads
- Automatically reopen a disconnected port
- Return the previous measurement after a failed read
- Return `None` for communication failures
- Print routine status messages during GUI operation

## Error Contract

The complete public result of `read()` is:

```text
valid number
or
RuntimeError
```

Examples of failures that should become `RuntimeError`:

- Port closed or unavailable
- Serial timeout
- No response
- Non-ASCII response when ASCII is required
- Invalid number
- Incomplete frame
- Wrong address
- CRC or checksum mismatch
- Instrument-reported error

Example:

```python
try:
    raw_response = self.serial.readline()
except serial.SerialException as error:
    raise RuntimeError(
        f"{self.NAME} serial communication failed: {error}"
    ) from error
```

When opening fails, close any partially opened connection before raising the final error.

## DAQ Error Handling

The driver does not decide whether a failure is temporary or persistent.

OpenLabDAQ currently:

1. Calls `read()`.
2. Retries short failures up to three total attempts.
3. Treats a recovered retry as a normal measurement without creating an event.
4. Records `None` and creates one communication-failure event if all attempts fail.
5. Continues acquiring other sensors.
6. Attempts to reconnect the failed sensor approximately once per minute.
7. Creates one recovery event after communication is restored.

## Optional Methods

Drivers may include instrument-specific methods such as:

```python
get_status()
read_serial_number()
set_zero()
```

The DAQ backbone calls only:

```python
connect()
read()
disconnect()
```

## Acceptance Test

Every driver must pass `test_sensor.py` without changing the test logic.

The expected lifecycle is:

1. Construct the driver.
2. Connect.
3. Read a valid value.
4. Disconnect.
5. Confirm that another `read()` raises `RuntimeError`.

A driver that retries, reconnects, returns `None`, or substitutes an older value inside `read()` does not comply with the OpenLabDAQ interface.
