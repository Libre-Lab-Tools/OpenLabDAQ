"""
logbook.py

Creates a human-readable logbook paired with an OpenLabDAQ CSV file.

Responsibilities
----------------
- Create a logbook using the active CSV filename.
- Write optional run information at the beginning of the file.
- Append timestamped manual and automatic events while logging is active.
- Accept an explicit event timestamp so manual events can use the time at
  which the user first opened the Add Event dialog.
- Record when the logging session ends.

This file is independent from logger.py. It does not read or write
measurement data.
"""

from datetime import datetime
from pathlib import Path


class Logbook:
    """
    Write run information and timestamped events to a text file.
    """

    def __init__(self):
        self.file = None
        self.file_path = None
        self.csv_path = None

    @property
    def is_active(self):
        """
        Return True while a logbook file is open.
        """
        return self.file is not None and not self.file.closed

    def start(self, csv_path, run_information):
        """
        Create a logbook paired with an active CSV file.

        Parameters
        ----------
        csv_path : str or Path
            Path of the CSV file created by Logger.
        run_information : dict
            Optional experiment, sample, gas, operator, and notes fields.
        """
        if self.is_active:
            raise RuntimeError(
                "A logbook is already open."
            )

        self.csv_path = Path(csv_path)

        self.file_path = self.csv_path.with_name(
            f"{self.csv_path.stem}_logbook.txt"
        )

        self.file = open(
            self.file_path,
            "w",
            encoding="utf-8",
        )

        start_time = datetime.now()

        self.file.write("OpenLabDAQ Logbook\n")
        self.file.write("=" * 60 + "\n\n")

        self.file.write(
            f"Start time: {self._format_timestamp(start_time)}\n"
        )
        self.file.write(
            f"Data file: {self.csv_path.name}\n"
        )
        self.file.write(
            f"Experiment: {self._display_value(run_information.get('experiment'))}\n"
        )
        self.file.write(
            f"Sample: {self._display_value(run_information.get('sample'))}\n"
        )
        self.file.write(
            f"Gas: {self._display_value(run_information.get('gas'))}\n"
        )
        self.file.write(
            f"Operator: {self._display_value(run_information.get('operator'))}\n"
        )

        notes = str(
            run_information.get(
                "notes",
                "",
            )
            or ""
        ).strip()

        self.file.write("\nGeneral notes\n")
        self.file.write("-" * 60 + "\n")
        self.file.write(
            f"{notes if notes else '(none)'}\n"
        )

        self.file.write("\nEvents\n")
        self.file.write("-" * 60 + "\n")

        self.file.flush()

    def add_event(
        self,
        event,
        comment="",
        timestamp=None,
    ):
        """
        Append one timestamped event.

        Parameters
        ----------
        event : str
            Short description of what happened.
        comment : str
            Optional additional details.
        timestamp : datetime or None
            Time to associate with the event. When omitted, the event is
            timestamped when it is written.
        """
        if not self.is_active:
            raise RuntimeError(
                "No logbook is currently open."
            )

        event_text = str(event or "").strip()

        if not event_text:
            raise ValueError(
                "The event description cannot be empty."
            )

        comment_text = str(comment or "").strip()

        if timestamp is None:
            event_time = datetime.now()
        elif isinstance(timestamp, datetime):
            event_time = timestamp
        else:
            raise TypeError(
                "Event timestamp must be a datetime object or None."
            )

        self.file.write(
            f"\n[{self._format_timestamp(event_time)}]\n"
        )
        self.file.write(
            f"Event: {event_text}\n"
        )
        self.file.write(
            f"Comment: {comment_text if comment_text else '(none)'}\n"
        )

        self.file.flush()

    def stop(self):
        """
        Record the end time and close the current logbook.
        """
        if not self.is_active:
            self.file = None
            return

        self.file.write("\n")
        self.file.write("-" * 60 + "\n")
        self.file.write(
            f"End time: {self._format_timestamp(datetime.now())}\n"
        )
        self.file.flush()
        self.file.close()

        self.file = None

    @staticmethod
    def _display_value(value):
        """
        Return readable text for an optional metadata field.
        """
        text = str(value or "").strip()
        return text if text else "(not provided)"

    @staticmethod
    def _format_timestamp(timestamp):
        """
        Format timestamps with milliseconds.
        """
        return timestamp.strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]
