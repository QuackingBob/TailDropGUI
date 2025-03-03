import os
import sys
import subprocess
import json
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QPushButton, QComboBox,
                            QFileDialog, QLineEdit, QGroupBox, QListWidget,
                            QMessageBox, QProgressBar, QSystemTrayIcon, QMenu, QAction)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMimeData, QSettings
from PyQt5.QtGui import QIcon, QDragEnterEvent, QDropEvent
from datetime import datetime

class FileTransferWorker(QThread):
    """Worker thread to handle file transfers in the background"""
    progress_update = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, files, destination, is_send=True):
        super().__init__()
        self.files = files
        self.destination = destination
        self.is_send = is_send

    def run(self):
        try:
            if self.is_send:
                # Format files for command
                file_list = " ".join([f'"{f}"' for f in self.files])
                cmd = f'sudo tailscale file cp {file_list} {self.destination}:'
                self.progress_update.emit(f"Sending files to {self.destination}...")
            else:
                # Receive mode
                cmd = f'sudo tailscale file get {self.destination}'
                self.progress_update.emit("Receiving files...")

            # Execute the command
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate()

            if process.returncode == 0:
                if self.is_send:
                    self.finished.emit(True, f"Files sent successfully to {self.destination}")
                else:
                    self.finished.emit(True, f"Files received successfully in {self.destination}")
            else:
                error_msg = stderr if stderr else "Unknown error"
                self.finished.emit(False, f"Error: {error_msg}")

        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")

class DropArea(QWidget):
    """Custom widget that accepts file drops"""
    file_dropped = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        layout = QVBoxLayout()
        self.label = QLabel("Drag and drop files here")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.setMinimumHeight(100)
        self.setStyleSheet("""
            QWidget {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f0f0f0;
            }
            QLabel {
                color: #666;
                font-size: 14px;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QWidget {
                    border: 2px dashed #3daee9;
                    border-radius: 5px;
                    background-color: #e6f5ff;
                }
                QLabel {
                    color: #3daee9;
                    font-size: 14px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QWidget {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f0f0f0;
            }
            QLabel {
                color: #666;
                font-size: 14px;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            files.append(url.toLocalFile())
        self.file_dropped.emit(files)
        self.setStyleSheet("""
            QWidget {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f0f0f0;
            }
            QLabel {
                color: #666;
                font-size: 14px;
            }
        """)

class TailscaleFileTransferGUI(QMainWindow):
    def __init__(self, script_directory=None):
        super().__init__()
        self.settings = QSettings("TailscaleGUI", "FileTransfer")
        if script_directory:
            self.icon_path = os.path.join(script_directory, "assets/folder-transfer-svgrepo-com.png")
            self.tray_icon_path = os.path.join(script_directory, "assets/transfer-download-svgrepo-com.png")
            self.custom_icon = QIcon(self.icon_path)
            self.custom_tray_icon = QIcon(self.tray_icon_path)
        else:
            self.custom_icon = QIcon.fromTheme("folder-transfer")
            self.custom_tray_icon = QIcon.fromTheme("network-transmit-receive")

        self.init_ui()
        self.load_devices()
        self.selected_files = []
        self.worker = None

        # Set up system tray
        self.tray_icon = QSystemTrayIcon(self)
        # self.tray_icon.setIcon(QIcon.fromTheme("network-transmit-receive"))
        self.tray_icon.setIcon(self.custom_tray_icon)
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(app.quit)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def init_ui(self):
        self.setWindowTitle("Tailscale File Transfer")
        self.setGeometry(300, 300, 600, 500)
        self.setWindowIcon(self.custom_icon)

        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # Send files section
        send_group = QGroupBox("Send Files")
        send_layout = QVBoxLayout()

        # Drop area
        self.drop_area = DropArea()
        self.drop_area.file_dropped.connect(self.add_dropped_files)
        send_layout.addWidget(self.drop_area)

        # File selection
        file_layout = QHBoxLayout()
        self.file_list = QListWidget()
        file_layout.addWidget(self.file_list)

        file_buttons_layout = QVBoxLayout()
        self.select_file_btn = QPushButton("Select Files")
        self.select_file_btn.clicked.connect(self.select_files)
        self.clear_files_btn = QPushButton("Clear")
        self.clear_files_btn.clicked.connect(self.clear_files)
        file_buttons_layout.addWidget(self.select_file_btn)
        file_buttons_layout.addWidget(self.clear_files_btn)
        file_buttons_layout.addStretch()
        file_layout.addLayout(file_buttons_layout)

        send_layout.addLayout(file_layout)

        # Device selection
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Destination Device:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(200)
        device_layout.addWidget(self.device_combo)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_devices)
        device_layout.addWidget(self.refresh_btn)
        device_layout.addStretch()
        send_layout.addLayout(device_layout)

        # Send button
        send_btn_layout = QHBoxLayout()
        self.send_btn = QPushButton("Send Files")
        self.send_btn.clicked.connect(self.send_files)
        send_btn_layout.addStretch()
        send_btn_layout.addWidget(self.send_btn)
        send_layout.addLayout(send_btn_layout)

        send_group.setLayout(send_layout)
        main_layout.addWidget(send_group)

        # Receive files section
        receive_group = QGroupBox("Receive Files")
        receive_layout = QVBoxLayout()

        save_dir_layout = QHBoxLayout()
        save_dir_layout.addWidget(QLabel("Save Directory:"))
        self.save_dir_edit = QLineEdit()
        save_dir_layout.addWidget(self.save_dir_edit)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.select_save_dir)
        save_dir_layout.addWidget(self.browse_btn)
        receive_layout.addLayout(save_dir_layout)

        # Load saved directory if exists
        saved_dir = self.settings.value("save_directory")
        if saved_dir:
            self.save_dir_edit.setText(saved_dir)
        else:
            # Default to home directory
            self.save_dir_edit.setText(str(Path.home()))

        # Receive button
        receive_btn_layout = QHBoxLayout()
        self.receive_btn = QPushButton("Receive Files")
        self.receive_btn.clicked.connect(self.receive_files)
        receive_btn_layout.addStretch()
        receive_btn_layout.addWidget(self.receive_btn)
        receive_layout.addLayout(receive_btn_layout)

        receive_group.setLayout(receive_layout)
        main_layout.addWidget(receive_group)

        # Status area
        status_layout = QVBoxLayout()
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.hide()
        status_layout.addWidget(self.progress_bar)

        main_layout.addLayout(status_layout)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def load_devices(self):
        try:
            self.status_label.setText("Loading devices...")
            self.device_combo.clear()

            # Run tailscale status command in JSON format
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise Exception(f"Failed to get device list: {result.stderr}")

            data = json.loads(result.stdout)
            peers = data.get("Peer", {})

            # Add devices to combo box
            for device_id, info in peers.items():
                host_name = info.get("HostName", "Unknown")
                tailnet_ip = info.get("TailscaleIPs", "Unknown")[0]
                online = info.get("Online", False)
                if online:
                    # print(tailnet_ip, device_id)
                    if tailnet_ip == "Unknown":
                        self.status_label.setText(f"Error: Tailscale IPs not found for device {host_name}")
                        QMessageBox.warning(self, "Error", f"Could not get tailnet IP for host: {host_name}")
                    self.device_combo.addItem(host_name, tailnet_ip)
                else:
                    print(f"Device {host_name} is offline")

            self.status_label.setText(f"Found {self.device_combo.count()} devices")

        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            QMessageBox.warning(self, "Error", f"Could not load devices: {str(e)}")

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Files to Send", str(Path.home())
        )
        self.add_files(files)

    def add_dropped_files(self, files):
        self.add_files(files)

    def add_files(self, files):
        if not files:
            return

        # Add to list widget
        for file_path in files:
            # Check if file is already in the list
            items = self.file_list.findItems(file_path, Qt.MatchExactly)
            if not items:
                self.file_list.addItem(file_path)
                self.selected_files.append(file_path)

        self.status_label.setText(f"Added {len(files)} file(s). Total: {self.file_list.count()}")

    def clear_files(self):
        self.file_list.clear()
        self.selected_files = []
        self.status_label.setText("File list cleared")

    def select_save_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_dir_edit.text()
        )
        if dir_path:
            self.save_dir_edit.setText(dir_path)
            # Save the directory preference
            self.settings.setValue("save_directory", dir_path)

    def send_files(self):
        if not self.selected_files:
            QMessageBox.warning(self, "Warning", "No files selected")
            return

        if self.device_combo.count() == 0:
            QMessageBox.warning(self, "Warning", "No destination device selected")
            return

        destination = self.device_combo.currentText()
        # print(destination)

        # Disable buttons during transfer
        self.toggle_ui_elements(False)
        self.progress_bar.show()

        # Start worker thread
        self.worker = FileTransferWorker(self.selected_files, destination, is_send=True)
        self.worker.progress_update.connect(self.update_status)
        self.worker.finished.connect(self.on_transfer_complete)
        self.worker.start()

    def receive_files(self):
        save_dir = self.save_dir_edit.text()
        if not save_dir:
            QMessageBox.warning(self, "Warning", "No save directory specified")
            return

        if not os.path.isdir(save_dir):
            QMessageBox.warning(self, "Warning", "Invalid directory path")
            return

        # Disable buttons during transfer
        self.toggle_ui_elements(False)
        self.progress_bar.show()

        # Start worker thread
        self.worker = FileTransferWorker([], save_dir, is_send=False)
        self.worker.progress_update.connect(self.update_status)
        self.worker.finished.connect(self.on_transfer_complete)
        self.worker.start()

    def toggle_ui_elements(self, enabled):
        self.send_btn.setEnabled(enabled)
        self.receive_btn.setEnabled(enabled)
        self.select_file_btn.setEnabled(enabled)
        self.clear_files_btn.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)

    def update_status(self, message):
        self.status_label.setText(message)

    def on_transfer_complete(self, success, message):
        self.progress_bar.hide()
        self.toggle_ui_elements(True)
        self.status_label.setText(message)

        if success:
            QMessageBox.information(self, "Success", message)
            # Show notification
            self.tray_icon.showMessage("Tailscale File Transfer", message, QSystemTrayIcon.Information)
            # Clear file list after successful send
            if "sent" in message:
                self.clear_files()
        else:
            QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        # Minimize to tray instead of closing
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()

if __name__ == "__main__":
    script_directory = os.path.dirname(os.path.abspath(sys.argv[0])) 
    print(script_directory)
    app = QApplication(sys.argv)
    window = TailscaleFileTransferGUI(script_directory)
    window.show()
    print(f"Opened on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        sys.exit(app.exec_())
    finally:
        print(f"Exiting on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
