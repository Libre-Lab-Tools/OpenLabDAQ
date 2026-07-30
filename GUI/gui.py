"""
GUI/gui.py

Main graphical interface for OpenLabDAQ.

Operation
---------
- The application name remains OpenLabDAQ.
- The large system title is loaded from config.json.
- Saving the configuration updates the title, sensor nicknames, and plot scales.
- RUN connects the DAQ and starts continuous acquisition.
- STOP disconnects the DAQ.
- LOAD asks for optional run information and starts CSV logging.
- An optional experiment name is appended to the timestamped filenames.
- LOGGING stops CSV logging and closes the matching logbook.
- ADD EVENT captures the event time when the dialog first opens.
- Automatic logging, sensor failure, and recovery events remain visible in Recent Events
  even when CSV logging is not active.
- All displayed measurements are read only from History.
- Sensor nicknames and plot scales affect only the GUI.
"""

import ctypes
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QIcon

# Allow this file to import modules from the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

ICON_FILE = PROJECT_ROOT / "assets" / "OpenLabDAQ.ico"
APP_ID = "OpenLab.OpenLabDAQ.1.0"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import load_config
from daq import DAQ
from logbook import Logbook
from GUI.event_panel import EventPanel
from GUI.gui_configuration import ConfigurationWindow
from GUI.help import HelpWindow
from GUI.plot_panel import PlotPanel
from GUI.sensor_panel import SensorPanel


class RunInformationDialog(QDialog):
    """
    Collect optional information before CSV logging begins.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(
            "Start Logging"
        )
        self.resize(500, 430)

        main_layout = QVBoxLayout(self)

        introduction = QLabel(
            "Enter optional information for this logging session. "
            "If an experiment name is provided, it will be appended "
            "to the timestamp in both saved filenames."
        )
        introduction.setWordWrap(True)

        form_layout = QFormLayout()

        self.experiment_edit = QLineEdit()
        self.experiment_edit.setPlaceholderText(
            "Example: Heating mystery powder"
        )
        self.experiment_edit.setToolTip(
            "Optional. This name is appended to the timestamped "
            "CSV and logbook filenames."
        )

        self.sample_edit = QLineEdit()
        self.sample_edit.setPlaceholderText(
            "Example: Mystery powder batch 7"
        )

        self.gas_edit = QLineEdit()
        self.gas_edit.setPlaceholderText(
            "Example: N2"
        )

        self.operator_edit = QLineEdit()
        self.operator_edit.setPlaceholderText(
            "Your Name Here"
        )

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(
            "General notes for this run"
        )
        self.notes_edit.setMinimumHeight(120)

        form_layout.addRow(
            "Experiment name:",
            self.experiment_edit,
        )
        form_layout.addRow(
            "Sample:",
            self.sample_edit,
        )
        form_layout.addRow(
            "Gas:",
            self.gas_edit,
        )
        form_layout.addRow(
            "Operator:",
            self.operator_edit,
        )
        form_layout.addRow(
            "Notes:",
            self.notes_edit,
        )

        buttons = QDialogButtonBox()

        start_button = buttons.addButton(
            "Start Logging",
            QDialogButtonBox.AcceptRole,
        )
        start_button.setDefault(True)

        buttons.addButton(
            "Cancel",
            QDialogButtonBox.RejectRole,
        )

        buttons.accepted.connect(
            self.accept
        )
        buttons.rejected.connect(
            self.reject
        )

        main_layout.addWidget(
            introduction
        )
        main_layout.addLayout(
            form_layout
        )
        main_layout.addWidget(
            buttons
        )

    def get_run_information(self):
        """
        Return the entered information as a dictionary.
        """
        return {
            "experiment": self.experiment_edit.text().strip(),
            "sample": self.sample_edit.text().strip(),
            "gas": self.gas_edit.text().strip(),
            "operator": self.operator_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
        }


class EventDialog(QDialog):
    """
    Collect a timestamped event description and optional comment.
    """

    def __init__(self, event_time, parent=None):
        super().__init__(parent)

        # Capture the event time before the user begins typing details.
        self.event_time = event_time

        self.setWindowTitle(
            "Add Event"
        )
        self.resize(500, 300)

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        event_time_label = QLabel(
            self.event_time.strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]
        )
        event_time_label.setToolTip(
            "This timestamp was captured when ADD EVENT was clicked."
        )

        self.event_edit = QLineEdit()
        self.event_edit.setPlaceholderText(
            "Example: Gas changed"
        )

        self.comment_edit = QTextEdit()
        self.comment_edit.setPlaceholderText(
            "Example: Switched from nitrogen to argon at 20 sccm"
        )
        self.comment_edit.setMinimumHeight(120)

        form_layout.addRow(
            "Event time:",
            event_time_label,
        )
        form_layout.addRow(
            "Event:",
            self.event_edit,
        )
        form_layout.addRow(
            "Comment:",
            self.comment_edit,
        )

        buttons = QDialogButtonBox()

        add_button = buttons.addButton(
            "Add Event",
            QDialogButtonBox.AcceptRole,
        )
        add_button.setDefault(True)

        buttons.addButton(
            "Cancel",
            QDialogButtonBox.RejectRole,
        )

        buttons.accepted.connect(
            self.validate_and_accept
        )
        buttons.rejected.connect(
            self.reject
        )

        main_layout.addLayout(
            form_layout
        )
        main_layout.addWidget(
            buttons
        )

    def validate_and_accept(self):
        """
        Require a short event description.
        """
        if not self.event_edit.text().strip():
            QMessageBox.warning(
                self,
                "Missing Event",
                "Enter a short description of the event.",
            )
            return

        self.accept()

    def get_event_information(self):
        """
        Return the entered event and comment.
        """
        return {
            "timestamp": self.event_time,
            "event": self.event_edit.text().strip(),
            "comment": self.comment_edit.toPlainText().strip(),
        }


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # Initial GUI states.
        self.daq = None
        self.running = False
        self.logging_active = False

        self.configuration_window = None
        self.help_window = None

        # Separate human-readable logbook paired with the CSV logger.
        self.logbook = Logbook()
        self.pending_run_information = None

        # Timer responsible for continuous acquisition.
        self.acquisition_timer = QTimer(self)
        self.acquisition_timer.timeout.connect(
            self.acquire_data
        )

        # The application identity always remains OpenLabDAQ.
        self.setWindowTitle("OpenLabDAQ")
        self.resize(1600, 900)

        central_widget = QWidget()
        self.setCentralWidget(
            central_widget
        )

        self.main_layout = QVBoxLayout(
            central_widget
        )

        self.create_header()
        self.create_body()

    # ---------------------------------------------------------
    # Layout
    # ---------------------------------------------------------

    def create_header(self):

        header_layout = QHBoxLayout()

        # User-defined title for the experimental system.
        self.title_label = QLabel(
            self.get_display_title()
        )
        self.title_label.setStyleSheet("""
            font-size: 30px;
            font-weight: bold;
        """)

        self.configuration_button = QPushButton(
            "Configuration"
        )
        self.configuration_button.setMinimumHeight(45)
        self.configuration_button.setStyleSheet("""
            font-size: 16px;
        """)
        self.configuration_button.setToolTip(
            "Open the DAQ configuration."
        )
        self.configuration_button.clicked.connect(
            self.configuration_pressed
        )

        self.help_button = QPushButton("Help")
        self.help_button.setMinimumHeight(45)
        self.help_button.setStyleSheet("""
            font-size: 16px;
        """)
        self.help_button.setToolTip(
            "Click to view instructions."
        )
        self.help_button.clicked.connect(
            self.help_pressed
        )

        header_layout.addStretch()
        header_layout.addWidget(
            self.title_label
        )
        header_layout.addStretch()
        header_layout.addWidget(
            self.configuration_button
        )
        header_layout.addWidget(
            self.help_button
        )

        self.main_layout.addLayout(
            header_layout
        )

    def create_body(self):

        body_layout = QHBoxLayout()

        left_panel = QWidget()
        left_panel.setFixedWidth(350)

        left_layout = QVBoxLayout(
            left_panel
        )

        # Initial DAQ state.
        self.run_button = QPushButton(
            "STOPPED"
        )
        self.run_button.setMinimumHeight(70)
        self.run_button.setStyleSheet(
            self.stopped_style()
        )
        self.run_button.setToolTip(
            "Click to start acquisition."
        )
        self.run_button.clicked.connect(
            self.run_pressed
        )

        # Initial logging state.
        self.logging_button = QPushButton(
            "LOAD"
        )
        self.logging_button.setMinimumHeight(70)
        self.logging_button.setStyleSheet(
            self.load_style()
        )
        self.logging_button.setToolTip(
            "Start acquisition before saving data."
        )
        self.logging_button.clicked.connect(
            self.logging_pressed
        )

        # Events are available only while a matching logbook is open.
        self.event_button = QPushButton(
            "ADD EVENT"
        )
        self.event_button.setMinimumHeight(55)
        self.event_button.setEnabled(False)
        self.event_button.setStyleSheet(
            self.event_disabled_style()
        )
        self.event_button.setToolTip(
            "Start logging before adding an event."
        )
        self.event_button.clicked.connect(
            self.event_pressed
        )

        sensor_nicknames = (
            self.get_sensor_nicknames()
        )
        sensor_plot_scales = (
            self.get_sensor_plot_scales()
        )

        self.sensor_panel = SensorPanel(
            sensor_nicknames
        )
        self.event_panel = EventPanel()
        self.plot_panel = PlotPanel(
            sensor_nicknames,
            sensor_plot_scales,
        )

        left_layout.addWidget(
            self.run_button
        )
        left_layout.addWidget(
            self.logging_button
        )
        left_layout.addWidget(
            self.event_button
        )
        left_layout.addSpacing(30)
        # Live values receive the remaining vertical space. The compact
        # Recent Events panel keeps a fixed height and does not compete with
        # the primary sensor display.
        left_layout.addWidget(
            self.sensor_panel,
            1,
        )
        left_layout.addSpacing(12)
        left_layout.addWidget(
            self.event_panel,
        )

        body_layout.addWidget(
            left_panel
        )
        body_layout.addWidget(
            self.plot_panel
        )

        self.main_layout.addLayout(
            body_layout
        )

    # ---------------------------------------------------------
    # Display configuration
    # ---------------------------------------------------------

    @staticmethod
    def get_display_title():
        """
        Read the user-defined system title from config.json.
        """

        config = load_config()

        return config.get(
            "display",
            {},
        ).get(
            "title",
            "OpenLabDAQ",
        )

    @staticmethod
    def get_sensor_nicknames():
        """
        Read optional display-only sensor nicknames.
        """

        config = load_config()

        return {
            sensor_name: str(
                settings.get(
                    "nickname",
                    "",
                )
                or ""
            ).strip()
            for sensor_name, settings in config.get(
                "sensors",
                {},
            ).items()
        }

    @staticmethod
    def get_sensor_plot_scales():
        """
        Read the configured linear or logarithmic plot scale per sensor.
        """

        config = load_config()

        return {
            sensor_name: str(
                settings.get(
                    "plot_scale",
                    "linear",
                )
                or "linear"
            ).strip().lower()
            for sensor_name, settings in config.get(
                "sensors",
                {},
            ).items()
        }

    def reload_display_configuration(self):
        """
        Reload the title, sensor nicknames, and plot scales after Save.
        """

        self.title_label.setText(
            self.get_display_title()
        )

        sensor_nicknames = (
            self.get_sensor_nicknames()
        )

        self.sensor_panel.set_sensor_nicknames(
            sensor_nicknames
        )
        self.plot_panel.set_sensor_nicknames(
            sensor_nicknames
        )

        self.plot_panel.set_sensor_plot_scales(
            self.get_sensor_plot_scales()
        )

    # ---------------------------------------------------------
    # DAQ control
    # ---------------------------------------------------------

    def run_pressed(self):

        if self.running:
            self.stop_daq()
        else:
            self.start_daq()

    def start_daq(self):
        """
        Display the connection message before beginning the
        blocking sensor connection process.
        """

        # Reload nicknames in case config.json was edited externally.
        self.reload_display_configuration()

        self.sensor_panel.set_connecting()

        self.run_button.setEnabled(False)
        self.run_button.setToolTip(
            "Connecting sensors..."
        )

        # Allow Qt to repaint before sensor connection begins.
        QTimer.singleShot(
            50,
            self.connect_daq,
        )

    def connect_daq(self):
        """
        Create and connect the DAQ.
        """

        try:
            self.daq = DAQ()

            # GUI logging begins disabled.
            self.daq.stop_logging()

            self.daq.connect()

        except Exception as error:

            self.cleanup_failed_start()

            self.run_button.setEnabled(True)
            self.run_button.setText(
                "STOPPED"
            )
            self.run_button.setStyleSheet(
                self.stopped_style()
            )
            self.run_button.setToolTip(
                "Click to start acquisition."
            )

            self.configuration_button.setEnabled(
                True
            )
            self.configuration_button.setToolTip(
                "Open the DAQ configuration."
            )

            self.sensor_panel.set_stopped()

            QMessageBox.critical(
                self,
                "DAQ Connection Error",
                str(error),
            )

            return

        self.running = True

        # A successful connection begins a new acquisition session. Clear
        # events from the previous session immediately before the first read.
        self.event_panel.clear_events()

        self.run_button.setEnabled(True)
        self.run_button.setText(
            "RUNNING"
        )
        self.run_button.setStyleSheet(
            self.running_style()
        )
        self.run_button.setToolTip(
            "Click to stop acquisition."
        )

        self.logging_button.setToolTip(
            "Click to start saving data."
        )

        # Configuration cannot change while the DAQ is active.
        self.configuration_button.setEnabled(False)
        self.configuration_button.setToolTip(
            "Stop acquisition before changing the configuration."
        )

        # Acquire immediately before starting the timer.
        self.acquire_data()

        if not self.running:
            return

        period_ms = max(
            1,
            round(self.daq.period * 1000),
        )

        self.acquisition_timer.start(
            period_ms
        )

    def acquire_data(self):
        """
        Perform one acquisition and update the GUI from History.
        """

        if not self.running or self.daq is None:
            return

        try:
            self.daq.acquire_once()

        except Exception as error:

            self.stop_daq()

            QMessageBox.critical(
                self,
                "Acquisition Error",
                str(error),
            )

            return

        # CSV creation occurs during the first logged acquisition.
        # Once its exact path exists, create the paired logbook.
        if (
            self.logging_active
            and not self.logbook.is_active
            and self.pending_run_information is not None
        ):
            self.start_logbook_if_ready()

        # Display automatic sensor failure and recovery events. The same
        # events are also written to the logbook when logging is active.
        self.record_daq_events()

        # Display components read only from History.
        self.sensor_panel.update_from_history(
            self.daq.history
        )

        self.plot_panel.update_from_history(
            self.daq.history
        )

    def stop_daq(self):
        """
        Stop acquisition, logging, and all sensor connections.
        """

        self.acquisition_timer.stop()

        if (
            self.logging_active
            or self.logbook.is_active
        ):
            self.stop_logging_session(
                show_errors=False
            )

        if self.daq is not None:

            try:
                self.daq.disconnect()

            except Exception as error:

                QMessageBox.warning(
                    self,
                    "DAQ Disconnection Error",
                    str(error),
                )

        self.daq = None
        self.running = False
        self.logging_active = False
        self.pending_run_information = None

        self.run_button.setEnabled(True)
        self.run_button.setText(
            "STOPPED\n(Click to Run)"
        )
        self.run_button.setStyleSheet(
            self.stopped_style()
        )
        self.run_button.setToolTip(
            "Click to start acquisition."
        )

        self.reset_logging_controls(
            acquisition_running=False
        )

        self.configuration_button.setEnabled(True)
        self.configuration_button.setToolTip(
            "Open the DAQ configuration."
        )

        # Keep the last values visible with gray status dots.
        self.sensor_panel.set_stopped()

    def cleanup_failed_start(self):
        """
        Clean up after an unsuccessful DAQ connection.
        """

        self.acquisition_timer.stop()

        if self.logbook.is_active:
            try:
                self.logbook.stop()
            except OSError:
                pass

        if self.daq is not None:

            try:
                self.daq.disconnect()

            except Exception:
                pass

        self.daq = None
        self.running = False
        self.logging_active = False
        self.pending_run_information = None

        self.reset_logging_controls(
            acquisition_running=False
        )

    def record_daq_events(self):
        """
        Display queued DAQ sensor events and write them to an active logbook.

        Events remain visible in the Recent Events panel even when permanent
        CSV logging is not active. When a logbook is open, the same event is
        also written to the experiment logbook.
        """

        if self.daq is None:
            return

        pop_events = getattr(
            self.daq,
            "pop_runtime_events",
            None,
        )

        if pop_events is None:
            return

        events = pop_events()
        logbook_error = None

        for event_information in events:
            event_time = datetime.now()
            event_text = event_information["event"]
            comment_text = event_information.get(
                "comment",
                "",
            )

            self.event_panel.add_event(
                event_time,
                event_text,
                comment_text,
            )

            if (
                self.logbook.is_active
                and logbook_error is None
            ):
                try:
                    self.logbook.add_event(
                        event_text,
                        comment_text,
                        timestamp=event_time,
                    )

                except (OSError, RuntimeError, ValueError, TypeError) as error:
                    logbook_error = error

        if logbook_error is not None:
            QMessageBox.warning(
                self,
                "Automatic Event Error",
                str(logbook_error),
            )

    # ---------------------------------------------------------
    # Logging and logbook control
    # ---------------------------------------------------------

    def logging_pressed(self):
        """
        Start or stop CSV logging and its matching logbook.
        """

        if not self.running or self.daq is None:
            return

        if self.logging_active:
            self.stop_logging_session()
        else:
            self.start_logging_session()

    def start_logging_session(self):
        """
        Ask for optional run information and begin CSV logging.
        """

        dialog = RunInformationDialog(
            self
        )

        if dialog.exec() != QDialog.Accepted:
            return

        self.pending_run_information = (
            dialog.get_run_information()
        )

        try:
            self.daq.start_logging(
                experiment_name=(
                    self.pending_run_information.get(
                        "experiment",
                        "",
                    )
                )
            )

        except Exception as error:
            self.pending_run_information = None

            QMessageBox.critical(
                self,
                "Logging Error",
                str(error),
            )
            return

        self.logging_active = True

        self.logging_button.setText(
            "LOGGING"
        )
        self.logging_button.setStyleSheet(
            self.logging_style()
        )
        self.logging_button.setToolTip(
            "Click to stop saving data and close the logbook."
        )

        self.event_button.setEnabled(False)
        self.event_button.setStyleSheet(
            self.event_disabled_style()
        )
        self.event_button.setToolTip(
            "Waiting for the first logged record."
        )

        # Create the first logged record immediately. This creates the CSV,
        # after which acquire_data() creates the matching logbook.
        self.acquire_data()

    def start_logbook_if_ready(self):
        """
        Create the paired logbook after Logger creates the CSV file.
        """

        if self.daq is None:
            return

        logger = getattr(
            self.daq,
            "logger",
            None,
        )

        if logger is None:
            self.handle_logbook_start_error(
                "The DAQ does not expose its Logger object."
            )
            return

        if not hasattr(
            logger,
            "file_path",
        ):
            self.handle_logbook_start_error(
                "logger.py does not provide file_path. "
                "Install the updated logger.py before using logbooks."
            )
            return

        # The logger may retain the previous path after closing, so also
        # require that a CSV file is currently open.
        if (
            logger.file_path is None
            or getattr(logger, "file", None) is None
        ):
            return

        try:
            self.logbook.start(
                logger.file_path,
                self.pending_run_information,
            )

        except (OSError, RuntimeError, ValueError) as error:
            self.handle_logbook_start_error(
                str(error)
            )
            return

        self.pending_run_information = None

        self.event_button.setEnabled(True)
        self.event_button.setStyleSheet(
            self.event_active_style()
        )
        self.event_button.setToolTip(
            "Add a timestamped event to the active logbook."
        )

    def handle_logbook_start_error(self, message):
        """
        Stop CSV logging if its paired logbook cannot be created.
        """

        try:
            if self.daq is not None:
                self.daq.stop_logging()
        except Exception:
            pass

        self.logging_active = False
        self.pending_run_information = None

        self.reset_logging_controls(
            acquisition_running=self.running
        )

        QMessageBox.critical(
            self,
            "Logbook Error",
            (
                "CSV logging was stopped because the matching "
                f"logbook could not be created.\n\n{message}"
            ),
        )

    def stop_logging_session(self, show_errors=True):
        """
        Stop CSV logging and close the matching logbook.
        """

        errors = []

        if self.daq is not None:
            try:
                self.daq.stop_logging()

                # The DAQ creates the automatic stop event. Process it
                # before closing the logbook so it is saved permanently.
                self.record_daq_events()

            except Exception as error:
                errors.append(
                    f"CSV logger: {error}"
                )

        try:
            self.logbook.stop()

        except OSError as error:
            errors.append(
                f"Logbook: {error}"
            )

        self.logging_active = False
        self.pending_run_information = None

        self.reset_logging_controls(
            acquisition_running=self.running
        )

        if errors and show_errors:
            QMessageBox.warning(
                self,
                "Logging Stop Error",
                "\n".join(errors),
            )

    def reset_logging_controls(
        self,
        acquisition_running,
    ):
        """
        Return the logging and event buttons to their inactive states.
        """

        self.logging_button.setText(
            "LOAD"
        )
        self.logging_button.setStyleSheet(
            self.load_style()
        )

        if acquisition_running:
            self.logging_button.setToolTip(
                "Click to start saving data."
            )
        else:
            self.logging_button.setToolTip(
                "Start acquisition before saving data."
            )

        self.event_button.setEnabled(False)
        self.event_button.setStyleSheet(
            self.event_disabled_style()
        )
        self.event_button.setToolTip(
            "Start logging before adding an event."
        )

    def event_pressed(self):
        """
        Append one timestamped manual event to the active logbook.

        The timestamp is captured when the user first clicks ADD EVENT, not
        when the user finishes typing the event details.
        """

        if (
            not self.logging_active
            or not self.logbook.is_active
        ):
            return

        event_time = datetime.now()

        dialog = EventDialog(
            event_time,
            self,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        event_information = (
            dialog.get_event_information()
        )

        # The in-memory event history is updated first so the event remains
        # visible even if the permanent logbook write reports an error.
        self.event_panel.add_event(
            event_information["timestamp"],
            event_information["event"],
            event_information["comment"],
        )

        try:
            self.logbook.add_event(
                event_information["event"],
                event_information["comment"],
                timestamp=event_information["timestamp"],
            )

        except (OSError, RuntimeError, ValueError, TypeError) as error:
            QMessageBox.critical(
                self,
                "Event Error",
                str(error),
            )

    # ---------------------------------------------------------
    # Other controls
    # ---------------------------------------------------------

    def configuration_pressed(self):
        """
        Open the configuration window.

        Display labels are refreshed when the user clicks Save.
        """

        self.configuration_window = (
            ConfigurationWindow()
        )

        self.configuration_window.accepted.connect(
            self.reload_display_configuration
        )

        self.configuration_window.show()

    def help_pressed(self):

        self.help_window = HelpWindow()
        self.help_window.show()

    # ---------------------------------------------------------
    # Styles
    # ---------------------------------------------------------

    @staticmethod
    def stopped_style():

        return """
            font-size: 20px;
            font-weight: bold;
            background-color: #b94a48;
            color: white;
        """

    @staticmethod
    def running_style():

        return """
            font-size: 20px;
            font-weight: bold;
            background-color: #3c9a5f;
            color: white;
        """

    @staticmethod
    def load_style():

        return """
            font-size: 20px;
            font-weight: bold;
            background-color: #b94a48;
            color: white;
        """

    @staticmethod
    def logging_style():

        return """
            font-size: 20px;
            font-weight: bold;
            background-color: #3c9a5f;
            color: white;
        """

    @staticmethod
    def event_active_style():

        return """
            font-size: 18px;
            font-weight: bold;
            background-color: #4f6d9a;
            color: white;
        """

    @staticmethod
    def event_disabled_style():

        return """
            font-size: 18px;
            font-weight: bold;
            background-color: #8a8a8a;
            color: white;
        """

    # ---------------------------------------------------------
    # Safe shutdown
    # ---------------------------------------------------------

    def closeEvent(self, event):

        if self.running:
            self.stop_daq()
        elif self.logbook.is_active:
            try:
                self.logbook.stop()
            except OSError:
                pass

        event.accept()


def main():

    # Tell Windows this is OpenLabDAQ, not the Python interpreter.
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_ID
        )

    app = QApplication(sys.argv)

    icon = QIcon(
        str(ICON_FILE)
    )

    app.setWindowIcon(
        icon
    )

    window = MainWindow()
    window.setWindowIcon(
        icon
    )
    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
