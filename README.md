# OpenLabDAQ Communication Reliability Update

Copy each file to the matching location in the OpenLabDAQ repository.

Included changes:

- `daq.py`: three total read attempts before a sensor is marked failed; recovered glitches create no event; failed sensors reconnect every 60 seconds.
- `sensors/BusyBee.py`: standardized value-or-`RuntimeError` driver behavior.
- `sensors/FurnaceTC.py`: standardized value-or-`RuntimeError` behavior and preserved floating-point temperature.
- Arduino firmware: each `READ?` performs one fresh measurement and returns a value or `ERROR`; no last-value or multi-failure state.
- Updated driver guide.
- New firmware guide.
- Updated GUI help for immediate retries, Recent Events, blank values, and one-minute reconnection.
