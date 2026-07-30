"""
logger.py

Provides permanent storage of acquisition records.

Responsibilities
----------------
- Create a new CSV file.
- Build a timestamped filename with an optional experiment name.
- Write the CSV header.
- Append acquisition records.
- Expose the path of the CSV file most recently created.

The Logger does not decide when data should be saved.
That responsibility belongs to the DAQ backbone.
"""

import csv
import re
from datetime import datetime
from pathlib import Path


class Logger:
    """
    Write acquisition records to CSV files.
    """

    MAXIMUM_EXPERIMENT_NAME_LENGTH = 60

    def __init__(self, directory):
        """
        Create a Logger object.

        Parameters
        ----------
        directory : str
            Directory where log files will be stored.
        """

        self.directory = Path(directory)
        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.file = None
        self.writer = None

        # Path of the CSV file most recently created by new_file().
        self.file_path = None

    def new_file(self, record, experiment_name=None):
        """
        Create a new CSV file and write its header.

        Parameters
        ----------
        record : dict
            First acquisition record. Its keys define the CSV columns.
        experiment_name : str or None
            Optional name appended to the timestamped filename.
        """

        if self.file is not None:
            raise RuntimeError(
                "A log file is already open."
            )

        filename = self.build_filename(
            experiment_name=experiment_name,
        )

        self.file_path = self._available_file_path(
            filename
        )

        self.file = open(
            self.file_path,
            "w",
            newline="",
            encoding="utf-8",
        )

        self.writer = csv.DictWriter(
            self.file,
            fieldnames=record.keys(),
        )

        self.writer.writeheader()

        # Save the header immediately.
        self.file.flush()

    def write(self, record):
        """
        Append one acquisition record to the current CSV file.

        Parameters
        ----------
        record : dict
            Acquisition record.
        """

        if self.writer is None:
            raise RuntimeError(
                "No log file is currently open."
            )

        self.writer.writerow(record)

        # Immediately save each record to disk.
        self.file.flush()

    def close(self):
        """
        Close the current CSV file.

        file_path is intentionally preserved so other parts of the
        application can still identify the file that was just written.
        """

        if self.file is not None:
            self.file.close()

        self.file = None
        self.writer = None

    def _available_file_path(self, filename):
        """
        Return a non-existing path without overwriting an earlier session.
        """

        candidate = self.directory / filename

        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        counter = 2

        while True:
            candidate = self.directory / (
                f"{stem}_{counter}{suffix}"
            )

            if not candidate.exists():
                return candidate

            counter += 1

    @classmethod
    def build_filename(
        cls,
        experiment_name=None,
        timestamp=None,
    ):
        """
        Return a timestamped CSV filename.

        A blank experiment name preserves the original timestamp-only format.
        """

        if timestamp is None:
            timestamp = datetime.now()

        base_name = timestamp.strftime(
            "%Y-%m-%d_%H-%M-%S"
        )

        clean_name = cls.sanitize_experiment_name(
            experiment_name
        )

        if clean_name:
            base_name = f"{base_name}_{clean_name}"

        return f"{base_name}.csv"

    @classmethod
    def sanitize_experiment_name(cls, experiment_name):
        """
        Convert an optional experiment name into safe filename text.
        """

        text = str(experiment_name or "").strip()

        if not text:
            return ""

        # Replace Windows-invalid filename characters and control characters.
        text = re.sub(
            r'[<>:"/\\|?*\x00-\x1F]',
            "_",
            text,
        )

        # Make names compact and readable in a file list.
        text = re.sub(r"\s+", "_", text)
        text = re.sub(r"_+", "_", text)
        text = text.strip(" ._")

        text = text[
            :cls.MAXIMUM_EXPERIMENT_NAME_LENGTH
        ].rstrip(" ._")

        return text
