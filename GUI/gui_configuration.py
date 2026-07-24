"""
GUI/gui_configuration.py

Graphical editor for the OpenLabDAQ configuration.

Operation
---------
- Loads the current config.json when the window opens.
- Allows the experimental-system title to be changed.
- Allows configured sensors to be enabled or disabled.
- Allows COM ports to be selected or typed manually.
- Allows an optional display-only nickname for each sensor.
- Allows each sensor plot to use a linear or logarithmic y-axis.
- Provides fixed acquisition-period options.
- Allows selection of the persistent logging directory.
- Save writes the changes to config.json and closes the window.
- Cancel closes without saving.
"""

import sys
from pathlib import Path

# Allow this file to import modules from the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from serial.tools import list_ports

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from config import load_config, save_config


class ConfigurationWindow(QDialog):
    """
    OpenLabDAQ configuration editor.
    """

    ACQUISITION_PERIODS = [
        ("100 ms", 100),
        ("500 ms", 500),
        ("1 second", 1000),
        ("2 seconds", 2000),
        ("5 seconds", 5000),
    ]

    # Display text and corresponding config.json value.
    PLOT_SCALES = [
        ("Linear", "linear"),
        ("Logarithmic", "log"),
    ]

    def __init__(self):
        super().__init__()

        self.config = load_config()

        # Stores controls belonging to each configured sensor.
        self.sensor_controls = {}

        self.setWindowTitle(
            "OpenLabDAQ Configuration"
        )
        self.resize(1050, 600)

        main_layout = QVBoxLayout(self)

        self.create_display_section(main_layout)
        self.create_sensor_section(main_layout)
        self.create_acquisition_section(main_layout)
        self.create_logging_section(main_layout)
        self.create_buttons(main_layout)

    # ---------------------------------------------------------
    # Display configuration
    # ---------------------------------------------------------

    def create_display_section(self, main_layout):
        """
        Create the user-defined system-title field.
        """

        group_box = QGroupBox("Display")
        group_box.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
            }
        """)

        layout = QGridLayout(group_box)

        title_label = QLabel("System title:")

        current_title = self.config.get(
            "display",
            {},
        ).get(
            "title",
            "OpenLabDAQ",
        )

        self.title_edit = QLineEdit(current_title)
        self.title_edit.setMaxLength(80)
        self.title_edit.setToolTip(
            "Title displayed at the top of the main window."
        )

        layout.addWidget(title_label, 0, 0)
        layout.addWidget(self.title_edit, 0, 1)

        main_layout.addWidget(group_box)

    # ---------------------------------------------------------
    # Sensor configuration
    # ---------------------------------------------------------

    def create_sensor_section(self, main_layout):
        """
        Create enable, COM-port, nickname, and plot-scale controls.
        """

        group_box = QGroupBox("Sensors")
        group_box.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
            }
        """)

        sensor_layout = QGridLayout(group_box)

        sensor_header = QLabel("Sensor")
        enabled_header = QLabel("Enabled")
        port_header = QLabel("COM port")
        nickname_header = QLabel("GUI nickname")
        plot_scale_header = QLabel("Plot scale")

        for header in (
            sensor_header,
            enabled_header,
            port_header,
            nickname_header,
            plot_scale_header,
        ):
            header.setStyleSheet(
                "font-weight: bold;"
            )

        sensor_layout.addWidget(
            sensor_header,
            0,
            0,
        )
        sensor_layout.addWidget(
            enabled_header,
            0,
            1,
        )
        sensor_layout.addWidget(
            port_header,
            0,
            2,
        )
        sensor_layout.addWidget(
            nickname_header,
            0,
            3,
        )
        sensor_layout.addWidget(
            plot_scale_header,
            0,
            4,
        )

        detected_ports = self.get_detected_ports()

        for row, (sensor_name, settings) in enumerate(
            self.config["sensors"].items(),
            start=1,
        ):
            sensor_label = QLabel(sensor_name)
            sensor_label.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
            """)

            enabled_checkbox = QCheckBox()
            enabled_checkbox.setChecked(
                settings.get("enabled", False)
            )
            enabled_checkbox.setToolTip(
                f"Enable or disable {sensor_name}."
            )

            port_selector = QComboBox()
            port_selector.setEditable(True)
            port_selector.setMinimumWidth(160)
            port_selector.setToolTip(
                "Select a detected COM port or type one manually."
            )

            saved_port = settings.get("port")

            # Correct accidental strings such as "null".
            if (
                isinstance(saved_port, str)
                and saved_port.strip().lower() == "null"
            ):
                saved_port = None

            available_ports = list(detected_ports)

            # Preserve an unavailable saved port.
            if (
                saved_port
                and saved_port not in available_ports
            ):
                available_ports.insert(
                    0,
                    saved_port,
                )

            port_selector.addItems(
                available_ports
            )

            if saved_port:
                port_selector.setCurrentText(
                    saved_port
                )
            else:
                port_selector.setCurrentText("")

            # Disabled sensors retain their saved port.
            port_selector.setEnabled(
                enabled_checkbox.isChecked()
            )

            enabled_checkbox.toggled.connect(
                port_selector.setEnabled
            )

            nickname_edit = QLineEdit(
                str(
                    settings.get(
                        "nickname",
                        "",
                    )
                    or ""
                )
            )
            nickname_edit.setMaxLength(60)
            nickname_edit.setPlaceholderText(
                "Optional"
            )
            nickname_edit.setMinimumWidth(220)
            nickname_edit.setToolTip(
                "Optional name used only in the sensor panel and plot title. "
                "History and CSV headers keep the official sensor name."
            )

            plot_scale_selector = QComboBox()
            plot_scale_selector.setMinimumWidth(145)
            plot_scale_selector.setToolTip(
                "Choose a linear y-axis or a logarithmic y-axis for this "
                "sensor's plot. Logarithmic plots display only positive values."
            )

            for label, config_value in self.PLOT_SCALES:
                plot_scale_selector.addItem(
                    label,
                    config_value,
                )

            saved_plot_scale = str(
                settings.get(
                    "plot_scale",
                    "linear",
                )
                or "linear"
            ).strip().lower()

            plot_scale_index = (
                plot_scale_selector.findData(
                    saved_plot_scale
                )
            )

            # Older configuration files do not contain plot_scale.
            # Unsupported values safely fall back to linear.
            if plot_scale_index == -1:
                plot_scale_index = (
                    plot_scale_selector.findData(
                        "linear"
                    )
                )

            plot_scale_selector.setCurrentIndex(
                plot_scale_index
            )

            sensor_layout.addWidget(
                sensor_label,
                row,
                0,
            )
            sensor_layout.addWidget(
                enabled_checkbox,
                row,
                1,
            )
            sensor_layout.addWidget(
                port_selector,
                row,
                2,
            )
            sensor_layout.addWidget(
                nickname_edit,
                row,
                3,
            )
            sensor_layout.addWidget(
                plot_scale_selector,
                row,
                4,
            )

            self.sensor_controls[sensor_name] = {
                "enabled": enabled_checkbox,
                "port": port_selector,
                "nickname": nickname_edit,
                "plot_scale": plot_scale_selector,
            }

        main_layout.addWidget(group_box)

    @staticmethod
    def get_detected_ports():
        """
        Return currently detected serial-port names.
        """

        return sorted(
            port.device
            for port in list_ports.comports()
        )

    # ---------------------------------------------------------
    # Acquisition configuration
    # ---------------------------------------------------------

    def create_acquisition_section(self, main_layout):
        """
        Create the fixed acquisition-period selector.
        """

        group_box = QGroupBox("Acquisition")
        group_box.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
            }
        """)

        layout = QHBoxLayout(group_box)

        period_label = QLabel(
            "Acquisition period:"
        )

        self.period_selector = QComboBox()
        self.period_selector.setMinimumWidth(160)
        self.period_selector.setToolTip(
            "Select how often OpenLabDAQ reads the sensors."
        )

        for label, period_ms in self.ACQUISITION_PERIODS:
            self.period_selector.addItem(
                label,
                period_ms,
            )

        current_period = self.config[
            "acquisition"
        ]["period_ms"]

        current_index = (
            self.period_selector.findData(
                current_period
            )
        )

        # Use one second if an unsupported value is found.
        if current_index == -1:
            current_index = (
                self.period_selector.findData(
                    1000
                )
            )

        self.period_selector.setCurrentIndex(
            current_index
        )

        layout.addWidget(period_label)
        layout.addWidget(self.period_selector)
        layout.addStretch()

        main_layout.addWidget(group_box)

    # ---------------------------------------------------------
    # Logging configuration
    # ---------------------------------------------------------

    def create_logging_section(self, main_layout):
        """
        Create the persistent logging-directory selector.
        """

        group_box = QGroupBox("Logging")
        group_box.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
            }
        """)

        layout = QGridLayout(group_box)

        directory_label = QLabel(
            "Saving directory:"
        )

        self.directory_edit = QLineEdit(
            self.config["logging"]["directory"]
        )
        self.directory_edit.setToolTip(
            "Directory where CSV files will be saved."
        )

        browse_button = QPushButton("Browse")
        browse_button.setToolTip(
            "Select the CSV saving directory."
        )
        browse_button.clicked.connect(
            self.browse_directory
        )

        layout.addWidget(
            directory_label,
            0,
            0,
        )
        layout.addWidget(
            self.directory_edit,
            0,
            1,
        )
        layout.addWidget(
            browse_button,
            0,
            2,
        )

        main_layout.addWidget(group_box)

    def browse_directory(self):
        """
        Open a folder-selection dialog.
        """

        current_directory = (
            self.directory_edit.text().strip()
        )

        if not current_directory:
            current_directory = str(PROJECT_ROOT)

        selected_directory = (
            QFileDialog.getExistingDirectory(
                self,
                "Select Logging Directory",
                current_directory,
            )
        )

        if selected_directory:
            self.directory_edit.setText(
                selected_directory
            )

    # ---------------------------------------------------------
    # Save and Cancel
    # ---------------------------------------------------------

    def create_buttons(self, main_layout):
        """
        Create Save and Cancel buttons.
        """

        button_layout = QHBoxLayout()

        save_button = QPushButton("Save")
        save_button.setMinimumHeight(40)
        save_button.setToolTip(
            "Save the configuration and close this window."
        )
        save_button.clicked.connect(
            self.save_configuration
        )

        cancel_button = QPushButton("Cancel")
        cancel_button.setMinimumHeight(40)
        cancel_button.setToolTip(
            "Close without saving changes."
        )
        cancel_button.clicked.connect(
            self.reject
        )

        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)

        main_layout.addStretch()
        main_layout.addLayout(button_layout)

    def save_configuration(self):
        """
        Validate and save the current configuration.
        """

        display_title = self.title_edit.text().strip()

        if not display_title:
            QMessageBox.warning(
                self,
                "Missing System Title",
                "Enter a title for the experimental system.",
            )
            return

        enabled_ports = []
        enabled_display_names = {}

        for sensor_name, controls in (
            self.sensor_controls.items()
        ):
            enabled = (
                controls["enabled"].isChecked()
            )

            port = (
                controls["port"]
                .currentText()
                .strip()
            )

            nickname = (
                controls["nickname"]
                .text()
                .strip()
            )

            plot_scale = (
                controls["plot_scale"]
                .currentData()
                or "linear"
            )

            if enabled and not port:
                QMessageBox.warning(
                    self,
                    "Missing COM Port",
                    (
                        f"{sensor_name} is enabled but "
                        "has no COM port."
                    ),
                )
                return

            if enabled:
                normalized_port = port.upper()

                if normalized_port in enabled_ports:
                    QMessageBox.warning(
                        self,
                        "Duplicate COM Port",
                        (
                            "More than one enabled sensor "
                            f"is using {port}."
                        ),
                    )
                    return

                enabled_ports.append(
                    normalized_port
                )

                display_name = (
                    nickname
                    if nickname
                    else sensor_name
                )

                normalized_display_name = (
                    display_name.casefold()
                )

                if normalized_display_name in enabled_display_names:
                    other_sensor = enabled_display_names[
                        normalized_display_name
                    ]

                    QMessageBox.warning(
                        self,
                        "Duplicate GUI Name",
                        (
                            f"{sensor_name} and {other_sensor} "
                            f"would both be displayed as "
                            f"'{display_name}'."
                        ),
                    )
                    return

                enabled_display_names[
                    normalized_display_name
                ] = sensor_name

            self.config["sensors"][sensor_name][
                "enabled"
            ] = enabled

            # Preserve the selected port when disabled.
            self.config["sensors"][sensor_name][
                "port"
            ] = port if port else None

            self.config["sensors"][sensor_name][
                "nickname"
            ] = nickname

            self.config["sensors"][sensor_name][
                "plot_scale"
            ] = plot_scale

        logging_directory = (
            self.directory_edit.text().strip()
        )

        if not logging_directory:
            QMessageBox.warning(
                self,
                "Missing Logging Directory",
                "Select a directory for CSV files.",
            )
            return

        self.config.setdefault(
            "display",
            {},
        )["title"] = display_title

        self.config["acquisition"]["period_ms"] = (
            self.period_selector.currentData()
        )

        self.config["logging"]["directory"] = (
            logging_directory
        )

        save_config(self.config)

        self.accept()
