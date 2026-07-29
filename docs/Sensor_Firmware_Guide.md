# Sensor Firmware Guide

## Purpose

This guide defines the standard firmware behavior for Arduino-based OpenLabDAQ instruments.

Firmware should expose the attached hardware through a small, predictable serial protocol. It should measure the hardware and report the result, while Python handles communication retries, disconnection, reconnection, logging, and user notifications.

## Standard Serial Protocol

The recommended commands are:

```text
ID?      -> SensorName
READ?    -> numerical value or ERROR
STATUS?  -> OK or ERROR
```

Each response must end with a newline.

Do not print startup messages, debug text, labels, units, or other unsolicited serial output. Extra text can be mistaken for a sensor response.

## Required Behavior

### `ID?`

Return the exact official sensor name used by the Python driver and `config.json`.

Example:

```text
FurnaceTC
```

### `READ?`

Perform one new hardware measurement.

Return either:

```text
523.25
```

or:

```text
ERROR
```

The numerical response must be readable by Python's `float()` function. Ordinary decimal and scientific notation are acceptable.

### `STATUS?`

Return:

```text
OK
```

when a new hardware check succeeds, otherwise:

```text
ERROR
```

`STATUS?` is optional for the DAQ backbone but useful for testing.

## Firmware Responsibilities

Firmware shall:

- Initialize the attached hardware
- Perform one fresh measurement for each `READ?`
- Apply hardware-specific conversion or calibration when the Arduino is the measurement interface
- Validate obvious hardware failures such as `NaN`, missing ADC, or invalid raw values
- Return a numerical value or the exact text `ERROR`
- Remain responsive to later commands after an error

Firmware shall not:

- Return the previous valid measurement after a failed read
- Count failures across multiple DAQ requests
- Decide when an instrument is disconnected
- Retry serial communication
- Open or close the computer's COM port
- Reconnect the USB connection
- Generate timestamps
- Log data
- Send unsolicited serial text

## Division of Responsibility

```text
Firmware
    fresh hardware value or ERROR

Python driver
    numerical value or RuntimeError

DAQ
    short read retries, failure events, None values,
    continued acquisition, and periodic reconnection
```

This separation keeps every firmware and driver simple while giving all instruments the same recovery behavior.

## Hardware Recovery Inside One Read

A firmware function may perform the minimum hardware action required to complete the requested measurement. For example, if an ADS1115 was previously unavailable, the next `READ?` may make one new initialization attempt before returning `ERROR`.

This is not DAQ communication retry logic. It is part of attempting one hardware measurement.

Avoid long loops that block indefinitely. A failed hardware read should return `ERROR` promptly so Python can decide what happens next.

## Recommended Structure

```cpp
void setup()
{
    Serial.begin(9600);
    initializeSensor();
}

void loop()
{
    handleSerial();
}

bool readSensor(float& value)
{
    // Perform one new hardware measurement.
    // Return true on success and false on failure.
}

void handleSerial()
{
    if (!Serial.available())
    {
        return;
    }

    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "ID?")
    {
        Serial.println("SensorName");
    }
    else if (command == "READ?")
    {
        float value;

        if (readSensor(value))
        {
            Serial.println(value, 3);
        }
        else
        {
            Serial.println("ERROR");
        }
    }
    else if (command == "STATUS?")
    {
        float value;
        Serial.println(readSensor(value) ? "OK" : "ERROR");
    }
}
```

## Numerical Output

Use a stable numerical format:

```text
25.340
1.234567e-04
```

Do not include units or labels:

```text
25.340 C        incorrect
Pressure=1.2    incorrect
```

The unit belongs in the Python driver's `UNIT` constant.

## Timing

A `READ?` response should complete as quickly as the hardware reasonably permits.

Do not add long delays to hide failures. The DAQ may issue another `READ?` shortly after an error as part of its short-glitch recovery.

## Error Examples

Return `ERROR` when:

- A thermocouple library returns `NaN`
- An ADC is not detected
- A raw single-ended ADC value is invalid
- A calculated value is non-finite
- The attached sensor reports a hardware fault

After returning `ERROR`, continue running normally and answer future commands.

## Acceptance Test

Before connecting the firmware to OpenLabDAQ, verify with a serial terminal or `test_sensor.py`:

1. `ID?` returns the exact sensor name.
2. `READ?` repeatedly returns a valid number under normal conditions.
3. A simulated hardware problem returns `ERROR` rather than old data.
4. Removing and restoring the sensor hardware does not freeze the Arduino.
5. No unsolicited startup or debug text appears.
6. The Arduino continues responding after an `ERROR` response.
