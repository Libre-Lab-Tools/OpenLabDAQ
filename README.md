# OpenLabDAQ

OpenLabDAQ is a modular Python data-acquisition program for laboratory instruments.

It connects multiple sensors, displays live values and plots, keeps recent data in memory, and saves synchronized measurements to CSV files. New instruments are added through independent sensor drivers without redesigning the DAQ, logger, history, or GUI.

## Instrument Support

OpenLabDAQ can work with any laboratory instrument that can communicate with the computer, but each instrument requires a compatible sensor driver.

A sensor driver translates the instrument's communication protocol into the standard OpenLabDAQ commands:

```python
connect()
read()
disconnect()
```

Before creating a new driver, check the `sensors/` directory for an existing compatible driver. Existing drivers may be used directly or adapted for similar instruments.

## Main Features

- Configuration-driven sensor loading
- Live sensor values and one plot per measurement
- Optional display nicknames for sensors
- Per-sensor linear or logarithmic plot scales
- Selectable plot history from 5 minutes to 3 days
- Sensor status indicators for successful, failed, and stopped states
- Runtime sensor-failure isolation and periodic automatic reconnection
- Scrollable Recent Events history for failures, recoveries, and manual events
- CSV logging with synchronized timestamps
- Run metadata and timestamped event logbooks
- Manual event timestamps captured when the Add Event dialog opens
- Export of the currently displayed History range
- GUI and non-GUI operation
- Standard driver interface and acceptance testing

## Quick Start

1. Install the required Python packages.
2. Add and test the required sensor drivers following the
   [Sensor Driver Guide](docs/Sensor_Driver_Guide.md).
3. Configure the enabled sensors, COM ports, optional nicknames, plot scales, acquisition period, and saving directory.
4. Run OpenLabDAQ using either the graphical interface or `auto_mode.py`.

Detailed setup and operating instructions are available in
[Getting Started](docs/Getting_Started.md).

## Runtime Sensor Recovery

A sensor communication failure during acquisition does not stop the complete DAQ. OpenLabDAQ records a blank value for the failed sensor, continues reading the remaining sensors, and attempts to reconnect the failed instrument periodically.

The GUI indicates the current state of each sensor:

- Green: the latest read succeeded
- Red: the latest read failed; the last valid value remains visible
- Gray: acquisition is stopped

Failure and recovery transitions appear in the Recent Events panel. When CSV logging is active, the same events are also written to the matching logbook.

## Plot Scales

Each sensor can be configured with a linear or logarithmic y-axis. Plot-scale selection affects only the GUI. History, CSV logging, and exported files keep the original numerical values.

Logarithmic plots are useful for quantities that span several orders of magnitude, such as high-vacuum pressure. Zero and negative values cannot be displayed on a logarithmic axis and are omitted only from that plot.

## Repository Structure

```text
OpenLabDAQ/
├── assets/                 Application icon and other assets
├── Data/                   Default output directory
├── docs/
│   ├── architecture.md
│   └── Sensor_Driver_Guide.md
├── GUI/
│   ├── event_panel.py      Temporary Recent Events display
│   ├── gui.py
│   ├── gui_configuration.py
│   ├── help.py
│   ├── help_content.html
│   ├── plot_panel.py
│   ├── sensor_panel.py
│   └── styles.py
├── sensors/                Instrument drivers
├── auto_mode.py            Non-GUI operation
├── config.json             User configuration
├── config.py               Configuration loading and saving
├── daq.py                  DAQ backbone
├── history.py              Temporary in-memory records
├── logbook.py              Run metadata and permanent event log
├── logger.py               CSV writer
├── test_sensor.py          Standard driver acceptance test
├── requirements.txt
├── OpenLabDAQ.bat
└── OpenLabDAQ_Debug.bat
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — software structure and data flow
- [`docs/Sensor_Driver_Guide.md`](docs/Sensor_Driver_Guide.md) — requirements for adding instruments
- [`docs/Getting_Started.md`](docs/Getting_Started.md) — installation and operating guide
- `GUI/help_content.html` — user instructions shown inside OpenLabDAQ

## Project Status

The core architecture and user interface are complete. Future development is expected to focus mainly on additional sensor drivers, documentation, and optional integrations such as selected-mass RGA data streams.
