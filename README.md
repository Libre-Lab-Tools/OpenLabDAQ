# OpenLabDAQ Pause and Named Logging Update

Replace the matching files in the OpenLabDAQ repository.

## Changes

- Optional experiment name is appended to timestamped CSV and logbook filenames.
- Blank experiment names preserve timestamp-only automatic naming.
- Logging can be stopped and restarted to create separate files while acquisition continues.
- Automatic `Data logging started` and `Data logging stopped` events are added to Recent Events and the active logbook.
- A `Pause Plots` / `Resume Plots` button freezes only plot redraws. Acquisition, History, logging, live values, and events continue.
- The pause button is blue during live updates and amber while plots are paused.

`logbook.py` does not require a change because it already derives its filename from the CSV path.
