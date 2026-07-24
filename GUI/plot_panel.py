"""
GUI/plot_panel.py

Displays real-time plots using acquisition records from History.

Operation
---------
- Creates one plot automatically for each measurement column.
- Provides selectable history windows from 5 minutes to 3 days.
- Uses clock time on the x-axis.
- Applies a configurable linear or logarithmic y-axis per sensor.
- Excludes zero and negative values only from logarithmic plots.
- Automatically rescales each y-axis using only visible data.
- Allows plots to be pinned to the top of the scrollable panel.
- Uses optional sensor nicknames only for plot titles.
- Exports all records in the currently displayed history window to CSV.
"""

import csv
import math
from datetime import timedelta

import pyqtgraph as pg

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class PlotPanel(QWidget):

    # Text displayed to the user and corresponding minutes.
    TIME_WINDOWS = {
        "5 minutes": 5,
        "20 minutes": 20,
        "2 hours": 120,
        "6 hours": 360,
        "1 day": 1440,
        "3 days": 4320,
    }

    def __init__(
        self,
        sensor_nicknames=None,
        sensor_plot_scales=None,
    ):
        super().__init__()

        # Maps official sensor names to optional GUI nicknames.
        self.sensor_nicknames = dict(sensor_nicknames or {})

        # Maps official sensor names to "linear" or "log". Missing or
        # unsupported values safely default to linear.
        self.sensor_plot_scales = self.normalize_plot_scales(
            sensor_plot_scales
        )

        self.plot_widgets = {}
        self.plot_curves = {}
        self.plot_containers = {}
        self.pin_buttons = {}
        self.title_labels = {}

        # Stores pinned plots in the order they were pinned.
        self.pinned_columns = []

        # Default visible history window.
        self.window_minutes = 20

        # Stores the current History object so changing the
        # selector refreshes the plots immediately.
        self.history = None

        main_layout = QVBoxLayout(self)

        self.create_history_controls(main_layout)
        self.create_scroll_area(main_layout)

    # ---------------------------------------------------------
    # Nicknames
    # ---------------------------------------------------------

    def set_sensor_nicknames(self, sensor_nicknames):
        """
        Replace the nickname mapping and refresh existing titles.
        """

        self.sensor_nicknames = dict(sensor_nicknames or {})

        for column, title_label in self.title_labels.items():
            self.update_title_label(
                title_label,
                column,
            )

    def set_sensor_plot_scales(self, sensor_plot_scales):
        """
        Replace the sensor plot-scale mapping and refresh existing plots.
        """

        self.sensor_plot_scales = self.normalize_plot_scales(
            sensor_plot_scales
        )

        for column, plot_widget in self.plot_widgets.items():
            plot_widget.setLogMode(
                x=False,
                y=self.is_log_scale(column),
            )

        if self.history is not None:
            self.update_from_history(
                self.history
            )

    @staticmethod
    def normalize_plot_scales(sensor_plot_scales):
        """
        Return a clean sensor-to-scale mapping.

        Older configuration files may not contain plot_scale. Any missing or
        unsupported value is treated as linear.
        """

        normalized = {}

        for sensor_name, scale in dict(
            sensor_plot_scales or {}
        ).items():
            scale_text = str(
                scale or "linear"
            ).strip().lower()

            normalized[sensor_name] = (
                "log"
                if scale_text == "log"
                else "linear"
            )

        return normalized

    # ---------------------------------------------------------
    # Layout
    # ---------------------------------------------------------

    def create_history_controls(self, main_layout):
        """
        Create the history-window selector.
        """

        controls_layout = QHBoxLayout()

        history_label = QLabel("History:")
        history_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
        """)

        self.window_selector = QComboBox()
        self.window_selector.setMinimumWidth(150)
        self.window_selector.setStyleSheet("""
            font-size: 16px;
            padding: 5px;
        """)
        self.window_selector.setToolTip(
            "Select how much recent history is displayed."
        )

        for label, minutes in self.TIME_WINDOWS.items():
            self.window_selector.addItem(
                label,
                minutes,
            )

        # Begin with the 20-minute window selected.
        default_index = self.window_selector.findData(
            self.window_minutes
        )
        self.window_selector.setCurrentIndex(
            default_index
        )

        self.window_selector.currentIndexChanged.connect(
            self.window_changed
        )

        self.export_button = QPushButton("Export Data")
        self.export_button.setMinimumHeight(36)
        self.export_button.setStyleSheet("""
            font-size: 16px;
            padding: 5px 12px;
        """)
        self.export_button.setToolTip(
            "Save all data currently displayed in the selected "
            "history window to a CSV file."
        )
        self.export_button.clicked.connect(
            self.export_displayed_data
        )

        controls_layout.addWidget(history_label)
        controls_layout.addWidget(self.window_selector)
        controls_layout.addWidget(self.export_button)
        controls_layout.addStretch()

        main_layout.addLayout(controls_layout)

    def create_scroll_area(self, main_layout):
        """
        Create the vertically scrollable plot area.
        """

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.plot_container = QWidget()

        self.plot_layout = QVBoxLayout(
            self.plot_container
        )
        self.plot_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        self.plot_layout.setSpacing(10)
        self.plot_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(
            self.plot_container
        )

        main_layout.addWidget(self.scroll_area)

    # ---------------------------------------------------------
    # History window
    # ---------------------------------------------------------

    def window_changed(self, _index=None):
        """
        Change the visible history window and refresh the plots.
        """

        selected_minutes = (
            self.window_selector.currentData()
        )

        if selected_minutes is None:
            return

        self.window_minutes = int(
            selected_minutes
        )

        if self.history is not None:
            self.update_from_history(
                self.history
            )

    # ---------------------------------------------------------
    # Data export
    # ---------------------------------------------------------

    def export_displayed_data(self):
        """
        Export all records in the currently displayed time window.

        The exported CSV uses the official History column names.
        Sensor nicknames remain display-only.
        """

        visible_records = self.get_visible_records()

        if not visible_records:
            QMessageBox.warning(
                self,
                "No Data to Export",
                "There is no data in the currently displayed range.",
            )
            return

        first_timestamp = visible_records[0]["Timestamp"]
        last_timestamp = visible_records[-1]["Timestamp"]

        default_filename = (
            "OpenLabDAQ_"
            f"{first_timestamp:%Y%m%d_%H%M%S}_to_"
            f"{last_timestamp:%Y%m%d_%H%M%S}.csv"
        )

        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Displayed Data",
            default_filename,
            "CSV files (*.csv)",
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"

        fieldnames = ["Timestamp"]

        # Preserve the first-seen order of all measurement columns.
        for record in visible_records:
            for column in record:
                if (
                    column != "Timestamp"
                    and column not in fieldnames
                ):
                    fieldnames.append(column)

        try:
            with open(
                file_path,
                "w",
                newline="",
                encoding="utf-8",
            ) as csv_file:

                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=fieldnames,
                )
                writer.writeheader()

                for record in visible_records:

                    export_row = {
                        column: record.get(column, "")
                        for column in fieldnames
                    }

                    timestamp = export_row["Timestamp"]

                    if hasattr(timestamp, "isoformat"):
                        export_row["Timestamp"] = timestamp.isoformat(
                            sep=" ",
                            timespec="milliseconds",
                        )

                    writer.writerow(export_row)

        except (OSError, PermissionError) as error:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Could not save the CSV file:\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "Export Complete",
            (
                f"Exported {len(visible_records)} records to:\n"
                f"{file_path}"
            ),
        )

    def get_visible_records(self):
        """
        Return the same History records represented by the plots.
        """

        if self.history is None:
            return []

        records = self.history.get_records()

        if not records:
            return []

        latest_timestamp = records[-1]["Timestamp"]

        cutoff_timestamp = (
            latest_timestamp
            - timedelta(
                minutes=self.window_minutes
            )
        )

        return [
            record
            for record in records
            if (
                "Timestamp" in record
                and cutoff_timestamp
                <= record["Timestamp"]
                <= latest_timestamp
            )
        ]

    # ---------------------------------------------------------
    # History update
    # ---------------------------------------------------------

    def update_from_history(self, history):
        """
        Update every plot using records stored in History.
        """

        self.history = history

        records = history.get_records()

        if not records:
            return

        latest_record = records[-1]

        measurement_columns = [
            column
            for column in latest_record
            if column != "Timestamp"
        ]

        # Rebuild only if available measurements change.
        if set(measurement_columns) != set(
            self.plot_widgets
        ):
            self.build_plots(
                measurement_columns
            )

        latest_timestamp = latest_record[
            "Timestamp"
        ]

        cutoff_timestamp = (
            latest_timestamp
            - timedelta(
                minutes=self.window_minutes
            )
        )

        visible_records = [
            record
            for record in records
            if record["Timestamp"] >= cutoff_timestamp
        ]

        for column in measurement_columns:

            times, values = self.get_plot_data(
                visible_records,
                column,
            )

            self.plot_curves[column].setData(
                times,
                values,
            )

            self.update_plot_range(
                column,
                cutoff_timestamp.timestamp(),
                latest_timestamp.timestamp(),
                values,
            )

    # ---------------------------------------------------------
    # Plot creation
    # ---------------------------------------------------------

    def build_plots(self, columns):
        """
        Create one plot for every measurement column.
        """

        self.clear_layout()

        self.plot_widgets = {}
        self.plot_curves = {}
        self.plot_containers = {}
        self.pin_buttons = {}
        self.title_labels = {}

        # Remove pins belonging to measurements no longer present.
        self.pinned_columns = [
            column
            for column in self.pinned_columns
            if column in columns
        ]

        ordered_columns = self.get_ordered_columns(
            columns
        )

        for column in ordered_columns:
            self.create_plot(column)

    def create_plot(self, column):
        """
        Create the title, pin button, and graph for one measurement.
        """

        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        container_layout = QVBoxLayout(
            container
        )
        container_layout.setContentsMargins(
            0,
            0,
            0,
            15,
        )
        container_layout.setSpacing(2)

        title_layout = QHBoxLayout()

        is_pinned = (
            column in self.pinned_columns
        )

        pin_button = QPushButton(
            "★" if is_pinned else "☆"
        )
        pin_button.setFixedSize(45, 40)
        pin_button.setStyleSheet("""
            font-size: 24px;
        """)
        pin_button.setToolTip(
            "Click to unpin this plot."
            if is_pinned
            else "Click to pin this plot."
        )

        pin_button.clicked.connect(
            lambda checked=False, name=column:
            self.toggle_pin(name)
        )

        title_label = QLabel()
        title_label.setStyleSheet("""
            font-size: 26px;
            font-weight: bold;
        """)

        self.update_title_label(
            title_label,
            column,
        )

        title_layout.addWidget(pin_button)
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # Display Unix timestamps as local clock time.
        time_axis = pg.DateAxisItem(
            orientation="bottom"
        )

        plot_widget = pg.PlotWidget(
            axisItems={
                "bottom": time_axis
            }
        )

        plot_widget.setFixedHeight(400)
        plot_widget.setBackground("white")

        plot_widget.showGrid(
            x=True,
            y=True,
            alpha=0.2,
        )

        plot_widget.setLabel(
            "bottom",
            "Time",
        )

        # PyQtGraph performs the logarithmic transformation only for the
        # displayed plot. History and CSV values remain unchanged.
        plot_widget.setLogMode(
            x=False,
            y=self.is_log_scale(column),
        )

        # Hide PyQtGraph's automatic-range button.
        plot_widget.getPlotItem().hideButtons()

        # Use dark axes and labels on the white background.
        bottom_axis = plot_widget.getAxis(
            "bottom"
        )
        left_axis = plot_widget.getAxis(
            "left"
        )

        bottom_axis.setPen("black")
        bottom_axis.setTextPen("black")

        left_axis.setPen("black")
        left_axis.setTextPen("black")

        curve = plot_widget.plot(
            pen=pg.mkPen(
                color=(40, 110, 170),
                width=3,
            )
        )

        container_layout.addLayout(
            title_layout
        )
        container_layout.addWidget(
            plot_widget
        )

        self.plot_layout.addWidget(
            container
        )

        self.plot_containers[column] = container
        self.plot_widgets[column] = plot_widget
        self.plot_curves[column] = curve
        self.pin_buttons[column] = pin_button
        self.title_labels[column] = title_label

    # ---------------------------------------------------------
    # Display names
    # ---------------------------------------------------------

    def update_title_label(self, label, column):
        """
        Apply the GUI nickname while preserving the unit suffix.
        """

        display_name = self.get_display_column_name(column)

        label.setText(display_name)

        if display_name != column:
            label.setToolTip(
                f"History and CSV name: {column}"
            )
        else:
            label.setToolTip("")

    def get_display_column_name(self, column):
        """
        Replace an official sensor name with its optional nickname.

        Example
        -------
        OmegaTC_1 (°C) -> Chamber Temperature (°C)
        """

        sensor_names = sorted(
            self.sensor_nicknames,
            key=len,
            reverse=True,
        )

        for sensor_name in sensor_names:

            is_exact_name = column == sensor_name
            has_unit_suffix = column.startswith(
                f"{sensor_name} ("
            )

            if not is_exact_name and not has_unit_suffix:
                continue

            nickname = str(
                self.sensor_nicknames.get(
                    sensor_name,
                    "",
                )
                or ""
            ).strip()

            if not nickname:
                return column

            suffix = column[len(sensor_name):]

            return f"{nickname}{suffix}"

        return column

    # ---------------------------------------------------------
    # Plot-scale selection
    # ---------------------------------------------------------

    def get_sensor_name_for_column(self, column):
        """
        Return the configured sensor name represented by a History column.
        """

        sensor_names = sorted(
            set(self.sensor_plot_scales)
            | set(self.sensor_nicknames),
            key=len,
            reverse=True,
        )

        for sensor_name in sensor_names:
            if (
                column == sensor_name
                or column.startswith(
                    f"{sensor_name} ("
                )
            ):
                return sensor_name

        return None

    def is_log_scale(self, column):
        """
        Return True when the column's sensor is configured for log plotting.
        """

        sensor_name = self.get_sensor_name_for_column(
            column
        )

        if sensor_name is None:
            return False

        return (
            self.sensor_plot_scales.get(
                sensor_name,
                "linear",
            )
            == "log"
        )

    # ---------------------------------------------------------
    # Plot data
    # ---------------------------------------------------------

    def get_plot_data(self, records, column):
        """
        Extract timestamps and valid numerical values.

        Logarithmic plots display only strictly positive values. Linear plots
        continue to display zero and negative values normally.
        """

        times = []
        values = []

        use_log_scale = self.is_log_scale(
            column
        )

        for record in records:

            if column not in record:
                continue

            value = record[column]

            try:
                numeric_value = float(value)

            except (TypeError, ValueError):
                continue

            if not math.isfinite(numeric_value):
                continue

            if use_log_scale and numeric_value <= 0:
                continue

            times.append(
                record["Timestamp"].timestamp()
            )

            values.append(
                numeric_value
            )

        return times, values

    def update_plot_range(
        self,
        column,
        start_time,
        end_time,
        values,
    ):
        """
        Set the visible time range and automatically scale y.

        PyQtGraph stores the visible y-range in logarithmic coordinates when
        log mode is active, so log plots use log10(values) only for range
        calculation. The curve still receives the original pressure values.
        """

        plot_widget = self.plot_widgets[
            column
        ]

        plot_widget.setXRange(
            start_time,
            end_time,
            padding=0,
        )

        if not values:
            return

        if self.is_log_scale(column):
            transformed_values = [
                math.log10(value)
                for value in values
                if value > 0
            ]

            if not transformed_values:
                return

            minimum = min(transformed_values)
            maximum = max(transformed_values)

            if minimum == maximum:
                padding = 0.10
            else:
                padding = max(
                    (maximum - minimum) * 0.10,
                    0.05,
                )

            plot_widget.setYRange(
                minimum - padding,
                maximum + padding,
                padding=0,
            )
            return

        minimum = min(values)
        maximum = max(values)

        if minimum == maximum:

            padding = max(
                abs(minimum) * 0.05,
                1e-9,
            )

        else:

            padding = (
                maximum - minimum
            ) * 0.10

        plot_widget.setYRange(
            minimum - padding,
            maximum + padding,
            padding=0,
        )

    # ---------------------------------------------------------
    # Plot pinning
    # ---------------------------------------------------------

    def toggle_pin(self, column):
        """
        Pin or unpin a plot and reorder the panel.
        """

        if column in self.pinned_columns:

            self.pinned_columns.remove(column)

            self.pin_buttons[column].setText(
                "☆"
            )
            self.pin_buttons[column].setToolTip(
                "Click to pin this plot."
            )

        else:

            self.pinned_columns.append(column)

            self.pin_buttons[column].setText(
                "★"
            )
            self.pin_buttons[column].setToolTip(
                "Click to unpin this plot."
            )

        self.reorder_plots()

    def reorder_plots(self):
        """
        Reorder existing plot widgets without rebuilding them.
        """

        while self.plot_layout.count():
            self.plot_layout.takeAt(0)

        ordered_columns = self.get_ordered_columns(
            list(self.plot_containers)
        )

        for column in ordered_columns:

            self.plot_layout.addWidget(
                self.plot_containers[column]
            )

    def get_ordered_columns(self, columns):
        """
        Return pinned plots first, followed by unpinned plots.
        """

        pinned = [
            column
            for column in self.pinned_columns
            if column in columns
        ]

        unpinned = [
            column
            for column in columns
            if column not in pinned
        ]

        return pinned + unpinned

    # ---------------------------------------------------------
    # Layout cleanup
    # ---------------------------------------------------------

    def clear_layout(self):
        """
        Remove and delete all current plot containers.
        """

        while self.plot_layout.count():

            item = self.plot_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
