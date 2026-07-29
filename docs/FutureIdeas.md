# OpenLabDAQ - Future Ideas

This document contains ideas that may be useful in future versions of OpenLabDAQ.

The goal is **not** to implement every feature. OpenLabDAQ should remain simple, reliable, and easy to maintain. New features should only be added if they provide clear benefits without significantly increasing software complexity.

---

# High Priority

## Improve Arduino communication robustness

Goal:
Increase long-term reliability of Arduino-based instruments.

Possible improvements:

- Retry sensor reads multiple times before reporting an error.
- Keep reporting the last valid measurement during short communication interruptions.
- Retry serial communication multiple times before declaring the sensor disconnected.
- Standardize this behavior across all Arduino firmware.

---

## Exponential reconnect timing

Current behavior:

- Wait 60 seconds after a communication failure.

Possible improvement:

- Retry after 2 seconds.
- Then 5 seconds.
- Then 15 seconds.
- Then 30 seconds.
- Then every 60 seconds.

This would allow quick recovery from temporary communication glitches while avoiding excessive retries for permanently disconnected instruments.

---

# GUI Improvements

## Plot smoothing

Optional moving average for display only.

Requirements:

- Raw measurements remain unchanged.
- CSV files always contain raw data.
- History always stores raw data.
- Only plotted values are filtered.

Possible options:

- Raw
- Moving average (5 samples)
- Moving average (10 samples)

---

## Adjustable Y axis

Allow users to:

- Auto scale
- Manual minimum
- Manual maximum

Useful for observing small changes without changing acquisition.

---

## Plot zoom and navigation

Possible additions:

- Mouse zoom
- Pan
- Reset zoom
- Zoom to last minute/hour/day

---

## Plot ause

Possible additions:

- pause the plotting to inspect the data
- keep recording in the background

---

## Multiple plot layouts

Examples:

- One plot per sensor
- Combined plots
- Tabbed plots

---

# Sensors

## Multi-output instruments

Support instruments returning multiple measurements.

Examples:

- Residual Gas Analyzer (RGA)
- Weather stations
- Environmental sensors
- Power analyzers

Requirements:

- Multiple plots
- Multiple logged variables
- Single driver

---

## Alarm outputs

Future support for:

- Audible alarms
- Visual alarms
- Digital outputs
- Relay control


---

# Reliability

## Communication statistics

Display:

- Successful reads
- Failed reads
- Reconnect attempts
- Last reconnect time

Useful for long experiments.

---

## Better reconnect diagnostics

Instead of only reporting "Disconnected", indicate:

- Read timeout
- Invalid response
- Device not found
- Port unavailable
- Checksum failure (future)

---

# Arduino Framework

Possible future library:

OpenLabDAQArduino

Responsibilities:

- Standard serial protocol
- Communication retries
- Last valid measurement
- Error handling
- Standard command parser
- Watchdog support

Each firmware would only implement:

- setupSensor()
- readSensor()

Everything else would be shared.

---

# Configuration

Possible future additions:

- Relative logging paths
- Configuration profiles
- Multiple saved configurations
- Recently used configurations

---

