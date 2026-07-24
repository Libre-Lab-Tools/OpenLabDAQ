"""
GUI/event_panel.py

Displays a short in-memory history of events during the current DAQ
session.

Operation
---------
- Shows automatic sensor failure and recovery events.
- Shows manually entered events after they are added to the logbook.
- Works even when CSV logging is not active.
- Keeps only the most recent events to prevent unlimited GUI growth.
- Uses a compact scrollable view so live sensor values and plots remain
  the visual priority.
- Clears when a new acquisition session begins.
- Does not write files; permanent event storage remains the responsibility
  of logbook.py.
"""

from collections import deque
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class EventPanel(QWidget):
    """
    Display recent DAQ and user events in a scrollable panel.
    """

    MAX_EVENTS = 20

    def __init__(self):
        super().__init__()

        # Each entry stores a timestamp, event description, and optional
        # comment. deque automatically removes the oldest entry after the
        # configured limit is reached.
        self.events = deque(maxlen=self.MAX_EVENTS)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        title_label = QLabel("Recent Events")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
        """)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # Keep the event history compact. Approximately two short events
        # remain immediately visible, while older entries can be reached
        # with the vertical scroll bar.
        self.scroll_area.setFixedHeight(110)
        self.scroll_area.setToolTip(
            "Shows recent sensor communication events and manually added "
            "events from the current acquisition session."
        )

        self.event_container = QWidget()
        self.event_layout = QVBoxLayout(self.event_container)
        self.event_layout.setContentsMargins(8, 8, 8, 8)
        self.event_layout.setSpacing(8)
        self.event_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.event_container)

        main_layout.addWidget(title_label)
        main_layout.addWidget(self.scroll_area)

        self.refresh_display()

    # ---------------------------------------------------------

    def add_event(self, timestamp, event, comment=""):
        """
        Add one event to the in-memory recent-event history.

        Parameters
        ----------
        timestamp : datetime
            Time associated with the event.
        event : str
            Short description of what happened.
        comment : str
            Optional additional details.
        """

        if not isinstance(timestamp, datetime):
            timestamp = datetime.now()

        event_text = str(event or "").strip()
        comment_text = str(comment or "").strip()

        if not event_text:
            return

        self.events.append(
            {
                "timestamp": timestamp,
                "event": event_text,
                "comment": comment_text,
            }
        )

        self.refresh_display()

    # ---------------------------------------------------------

    def clear_events(self):
        """
        Clear the recent-event history for a new acquisition session.
        """

        self.events.clear()
        self.refresh_display()

    # ---------------------------------------------------------

    def refresh_display(self):
        """
        Rebuild the visible event list with the newest event first.
        """

        self.clear_layout()

        if not self.events:
            empty_label = QLabel("No events in this session")
            empty_label.setWordWrap(True)
            empty_label.setStyleSheet("""
                color: #666666;
                font-size: 15px;
                padding: 6px;
            """)

            self.event_layout.addWidget(empty_label)
            self.event_layout.addStretch()
            return

        for event_information in reversed(self.events):
            self.event_layout.addWidget(
                self.create_event_widget(event_information)
            )

        self.event_layout.addStretch()

        # New events are inserted at the top, so keep the panel positioned
        # at the newest entry after every update.
        self.scroll_area.verticalScrollBar().setValue(0)

    # ---------------------------------------------------------

    def create_event_widget(self, event_information):
        """
        Create one formatted event entry.
        """

        timestamp = event_information["timestamp"]
        event_text = event_information["event"]
        comment_text = event_information["comment"]

        container = QWidget()
        container.setObjectName("eventEntry")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(7, 6, 7, 6)
        layout.setSpacing(3)

        heading = QLabel(
            f"{timestamp:%H:%M:%S}  {event_text}"
        )
        heading.setWordWrap(True)
        heading.setToolTip(
            timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        )

        event_lower = event_text.casefold()

        if "failed" in event_lower or "error" in event_lower:
            heading_color = "#b94a48"
        elif "restored" in event_lower or "recovered" in event_lower:
            heading_color = "#3c9a5f"
        else:
            heading_color = "#234f72"

        heading.setStyleSheet(
            f"""
            color: {heading_color};
            font-size: 15px;
            font-weight: bold;
            """
        )

        layout.addWidget(heading)

        if comment_text:
            comment_label = QLabel(comment_text)
            comment_label.setWordWrap(True)
            comment_label.setStyleSheet("""
                color: #444444;
                font-size: 13px;
            """)
            layout.addWidget(comment_label)

        container.setStyleSheet("""
            QWidget#eventEntry {
                border-bottom: 1px solid #d0d0d0;
            }
        """)

        return container

    # ---------------------------------------------------------

    def clear_layout(self):
        """
        Remove all visible event widgets before rebuilding the list.
        """

        while self.event_layout.count():
            item = self.event_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
