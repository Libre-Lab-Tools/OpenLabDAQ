"""
GUI/help.py

Displays the OpenLabDAQ help documentation.

The user-facing help content is stored separately in help_content.html so
operating instructions can be updated without changing the Python window code.
The current help document covers plot-scale selection, sensor status colors,
runtime sensor recovery, Recent Events, logging, and manual event timestamps.

The local HTML instructions work without an internet connection. External
links open in the user's default web browser when internet access is available.
"""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)


# Local help file stored beside this Python file.
HELP_FILE = Path(__file__).resolve().parent / "help_content.html"


class HelpWindow(QDialog):
    """
    Display the local OpenLabDAQ help documentation.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("OpenLabDAQ Help")
        self.resize(850, 700)

        main_layout = QVBoxLayout(self)

        self.help_browser = QTextBrowser()
        self.help_browser.setOpenExternalLinks(True)

        # Allows the HTML file to find local images or additional
        # documentation stored in the GUI directory.
        self.help_browser.setSearchPaths(
            [str(HELP_FILE.parent)]
        )

        self.load_help()

        close_button = QPushButton("Close")
        close_button.setMinimumHeight(40)
        close_button.setToolTip(
            "Close the help window."
        )
        close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)

        main_layout.addWidget(self.help_browser)
        main_layout.addLayout(button_layout)

    def load_help(self):
        """
        Load the local HTML help document.
        """

        if HELP_FILE.exists():
            self.help_browser.setSource(
                QUrl.fromLocalFile(
                    str(HELP_FILE)
                )
            )

        else:
            self.help_browser.setHtml(
                f"""
                <h1>OpenLabDAQ Help</h1>

                <p>
                    The help document could not be found.
                </p>

                <p>
                    Expected location:
                </p>

                <p>
                    <code>{HELP_FILE}</code>
                </p>
                """
            )
