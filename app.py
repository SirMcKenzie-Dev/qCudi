# scraper_project/app.py
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGridLayout, QWidget, QPushButton, QLabel, QLineEdit, QProgressBar, QMessageBox, QTextEdit, QComboBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from scrapers import ScraperController
from urllib.parse import urlparse
from config.config import ScraperConfig
from typing import Optional
import asyncio
import sys
import os


class ScraperThread(QThread):
    """Modified ScraperThread to work with new controller"""
    progress_signal = pyqtSignal(int, int, str, str)  # current, total, url, status
    completed_signal = pyqtSignal(int, int)  # successful, total
    error_signal = pyqtSignal(str)
    total_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)

    def __init__(self, url, website_type):
        super().__init__()
        self.url = url
        self.website_type = website_type
        self.controller = None  # Will hold ScraperController instance
        self.is_cancelled = False
        # self.total_thumbnails = 0

    def progress_callback(self, current, url, status_code, total=None):
        try:
            if total is not None:
                self.total_thumbnails = total
                self.total_signal.emit(total)
                self.status_signal.emit(f"Found {total} media items to process")
            else:
                status_text = "OK" if status_code == 200 else f"Error ({status_code})"
                self.progress_signal.emit(current, self.total_thumbnails, url, status_text)
                self.status_signal.emit(f"Processing item {current} of {self.total_thumbnails}")
        except Exception as e:
            self.error_signal.emit(f"Progress callback error: {str(e)}")

    def cancel(self):
        self.is_cancelled = True
        self.status_signal.emit("Cancelling operation...")
        if self.controller and self.controller.driver:
            self.controller.driver.quit()

    def run(self):
        try:
            self.controller = ScraperController(
                progress_callback=self.progress_callback
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the scraping process
            total_items, successful_downloads = loop.run_until_complete(
                self.controller.run(self.url)
            )

            loop.close()

            # if self.is_cancelled:
            #     self.status_signal.emit("Operation cancelled")
            #     return

            if not self.is_cancelled:
                self.completed_signal.emit(successful_downloads, total_items)

            # self.completed_signal.emit(successful_downloads, total_items)

        except ValueError as e:  # URL validation error
            self.error_signal.emit(f"Invalid URL {str(e)}")
        except RuntimeError as e:  # Disk space error
            self.error_signal.emit(f"System error: {str(e)}")
        except Exception as e:
            self.error_signal.emit(f"Scraping error: {str(e)}")
        finally:
            self.status_signal.emit("Process completed")


class WebScraperApp(QMainWindow):
    """Main window class with updates for multiple websites"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Web Scraper")
        self.setGeometry(100, 100, 600, 400)

        # Center the window
        screen = QApplication.desktop().screenGeometry()
        window_geometry = self.geometry()
        x = (screen.width() - window_geometry.width()) // 2
        y = (screen.height() - window_geometry.height()) // 2
        self.move(x, y)

        # Setup UI
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        grid_layout = QGridLayout(self.central_widget)

        # Heading (Row 0)
        self.url_label = QLabel("Enter URL to scrape:")
        grid_layout.addWidget(self.url_label, 0, 0, 1, 2)  # Row 0 | Col 0 | Spans 1 row | Spans 2 columns

        # URL Input (Row 1)
        self.url_input = QLineEdit()
        grid_layout.addWidget(self.url_input, 1, 0, 1, 2)  # Row 1 | Col 0 | Spans 1 row | Spans 2 columns

        # Progress Bar (Row 2)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        grid_layout.addWidget(self.progress_bar, 2, 0, 1, 2)  # Row 2 | Col 0 | Spans 1 row | Spans 2 columns

        # Status Label (Row 3)
        self.status_label = QLabel("")
        grid_layout.addWidget(self.status_label, 3, 0, 1, 2)  # Row 3 | Col 0 | Spans 1 row | Spans 2 columns

        # Controls (Row 4 Col 2)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_operation)
        self.cancel_button.setEnabled(False)
        grid_layout.addWidget(self.cancel_button, 4, 2)  # Row 4 | Col 2

        # Controls (Row 4 Col 0)
        self.dropdown = QComboBox()
        self.dropdown.addItems(["Fapello", "Instagram", "Threads"])
        # self.dropdown.addItem("Fapello")
        # self.dropdown.addItem("Instagram")
        # self.dropdown.addItem("Threads")
        grid_layout.addWidget(self.dropdown, 4, 0)  # Row 4 | Col 0

        # Controls (Row 4 Col 1)
        self.submit_button = QPushButton("Start Download")
        self.submit_button.clicked.connect(self.submit_url)
        self.submit_button.setFixedWidth(100)
        grid_layout.addWidget(self.submit_button, 4, 1)  # Row 4 | Col 1

        # Log Text Area (Row 6)
        self.log_text_area = QTextEdit()
        self.log_text_area.setReadOnly(True)
        grid_layout.addWidget(self.log_text_area, 6, 0, 1, 3)  # Row 6 | Col 0 | Spans 1 row | Spans 3 columns

    def submit_url(self):
        """Modified to handle multiple website types"""
        url = self.url_input.text()
        website_type = self.dropdown.currentText()

        if not url:
            QMessageBox.warning(self, "Input Error", "Please enter a valid URL!")
            return

        # URL validation
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                QMessageBox.warning(self, "Input error", "Invalid URL format!")
                return
        except Exception:
            QMessageBox.warning(self, "Input Error", "Invalid URL format!")
            return

        if "Instagram" in website_type:
            QMessageBox.information(self, "Feature Not Available",
                                    "Instagram scraping is coming soon!")
            return

        # Reset UI elements
        self.progress_bar.setValue(0)
        self.status_label.setText("Initializing...")
        self.log_text_area.clear()
        self.submit_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        # Create and start scraper thread
        self.scraper_thread = ScraperThread(url, website_type)
        # ... (connect signals) ...
        self.scraper_thread.error_signal.connect(self.display_error)
        self.scraper_thread.status_signal.connect(self.update_status)  # Connect status signal
        self.scraper_thread.progress_signal.connect(self.update_progress)
        self.scraper_thread.total_signal.connect(self.initialize_progress)
        self.scraper_thread.completed_signal.connect(self.download_complete)
        self.scraper_thread.start()

    def cancel_operation(self):
        if hasattr(self, 'scraper_thread') and self.scraper_thread.isRunning():
            self.scraper_thread.cancel()
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Cancelling...")

    def initialize_progress(self, total):
        self.total_thumbnails = total
        self.status_label.setText(f"Found {total} items to download")
        self.log_text_area.append(f"Starting download of {total} items...")

    def update_progress(self, current_progress, total_progress, url, status):
        try:
            percentage = int((current_progress / total_progress) * 100)
            self.progress_bar.setValue(percentage)
            self.log_text_area.append(f"Item {current_progress}/{total_progress}: {url} - Status: {status}")
            # Ensure log scrolls to bottom
            self.log_text_area.verticalScrollBar().setValue(
                self.log_text_area.verticalScrollBar().maximum()
            )
        except Exception as e:
            self.display_error(f"Error updating progress: {str(e)}")

    def update_status(self, message):
        self.status_label.setText(message)

    def download_complete(self, successful_downloads, total_thumbnails):
        self.status_label.setText("Download complete!")
        self.submit_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        QMessageBox.information(
            self,
            "Success",
            f"Downloaded {successful_downloads} out of {total_thumbnails} items!\n"
            f"Success rate: {(successful_downloads / total_thumbnails) * 100:.0f}%"
        )

    def display_error(self, error_message):
        self.status_label.setText("Error occurred!")
        self.submit_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        QMessageBox.critical(self, "Error", f"An error occurred: {error_message}")


if __name__ == "__main__":
    myapp = QApplication([])
    window = WebScraperApp()
    window.show()
    myapp.exec_()
