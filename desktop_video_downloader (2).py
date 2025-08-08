import sys
import os
from PyQt6.QtCore import QUrl, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QToolBar, QWidget, QVBoxLayout,
    QPushButton, QComboBox, QLabel, QMessageBox, QCheckBox
)
from PyQt6.QtGui import QAction
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
import yt_dlp


class DownloadThread(QThread):
    download_finished = pyqtSignal(str)
    download_error = pyqtSignal(str)
    download_progress = pyqtSignal(dict)

    def __init__(self, url, quality, download_dir):
        super().__init__()
        self.url = url
        self.quality = quality
        self.download_dir = download_dir

    def run(self):
        format_selector = "best"
        if self.quality == "720p":
            format_selector = "best[height<=720]"
        elif self.quality == "480p":
            format_selector = "best[height<=480]"
        elif self.quality == "360p":
            format_selector = "best[height<=360]"
        elif self.quality == "오디오만":
            format_selector = "bestaudio"

        ydl_opts = {
            'format': format_selector,
            'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [self.hook],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.download_finished.emit("다운로드 완료!")
        except Exception as e:
            self.download_error.emit(f"다운로드 실패: {e}")

    def hook(self, d):
        if d['status'] == 'downloading':
            self.download_progress.emit(d)


class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://www.youtube.com"))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.browser)

        # 네비게이션 바
        self.nav_bar = QToolBar("Navigation")
        self.addToolBar(self.nav_bar)

        back_btn = QAction("Back", self)
        back_btn.triggered.connect(self.browser.back)
        self.nav_bar.addAction(back_btn)

        forward_btn = QAction("Forward", self)
        forward_btn.triggered.connect(self.browser.forward)
        self.nav_bar.addAction(forward_btn)

        reload_btn = QAction("Reload", self)
        reload_btn.triggered.connect(self.browser.reload)
        self.nav_bar.addAction(reload_btn)

        home_btn = QAction("Home", self)
        home_btn.triggered.connect(self.navigate_home)
        self.nav_bar.addAction(home_btn)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.nav_bar.addWidget(self.url_bar)
        self.browser.urlChanged.connect(self.update_url_bar)

        # 다운로드 툴바
        self.download_toolbar = QToolBar("Download")
        self.addToolBar(self.download_toolbar)

        self.quality_selector = QComboBox()
        self.quality_selector.addItems(["최고 품질", "720p", "480p", "360p", "오디오만"])
        self.download_toolbar.addWidget(QLabel("품질:"))
        self.download_toolbar.addWidget(self.quality_selector)

        download_btn = QPushButton("현재 페이지 비디오 다운로드")
        download_btn.clicked.connect(self.start_download)
        self.download_toolbar.addWidget(download_btn)

        self.status_label = QLabel("준비 완료")
        self.download_toolbar.addWidget(self.status_label)

        # DNS 암호화 툴바
        self.dns_toolbar = QToolBar("DNS Settings")
        self.addToolBar(self.dns_toolbar)

        self.doh_checkbox = QCheckBox("DNS 암호화 (DoH) 사용")
        self.doh_checkbox.stateChanged.connect(self.toggle_doh)
        self.dns_toolbar.addWidget(self.doh_checkbox)

        self.showMaximized()

    def navigate_home(self):
        self.browser.setUrl(QUrl("https://www.youtube.com"))

    def navigate_to_url(self):
        url = self.url_bar.text()
        if not url.startswith("http"):
            url = "http://" + url
        self.browser.setUrl(QUrl(url))

    def update_url_bar(self, qurl):
        self.url_bar.setText(qurl.toString())

    def toggle_doh(self, state):
        profile = QWebEngineProfile.defaultProfile()
        if bool(state):
            profile.setDnsMode(QWebEngineProfile.DnsMode.DnsOverHttps)
            profile.setDnsOverHttpsServers(["https://dns.google/dns-query"])
            self.status_label.setText("DNS 암호화 (DoH) 활성화됨")
        else:
            profile.setDnsMode(QWebEngineProfile.DnsMode.System)
            profile.setDnsOverHttpsServers([])
            self.status_label.setText("DNS 암호화 (DoH) 비활성화됨")
        self.browser.reload()

    def start_download(self):
        current_url = self.browser.url().toString()
        selected_quality = self.quality_selector.currentText()

        self_dir = os.path.dirname(os.path.abspath(__file__))
        download_dir = os.path.join(self_dir, "downloads")
        os.makedirs(download_dir, exist_ok=True)

        self.status_label.setText("다운로드 시작 중...")
        QApplication.processEvents()

        self.download_thread = DownloadThread(current_url, selected_quality, download_dir)
        self.download_thread.download_finished.connect(self.on_download_finished)
        self.download_thread.download_error.connect(self.on_download_error)
        self.download_thread.download_progress.connect(self.on_download_progress)
        self.download_thread.start()

    def on_download_finished(self, message):
        self.status_label.setText(message)
        QMessageBox.information(self, "다운로드 완료", "비디오 다운로드가 완료되었습니다!")

    def on_download_error(self, message):
        self.status_label.setText(message)
        QMessageBox.critical(self, "다운로드 오류", f"비디오 다운로드 중 오류가 발생했습니다:\n{message}")

    def on_download_progress(self, d):
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded_bytes = d.get('downloaded_bytes')
            if total_bytes and downloaded_bytes:
                percent = downloaded_bytes / total_bytes * 100
                self.status_label.setText(f"다운로드 중: {percent:.1f}% ({d['_eta_str']} 남음)")
            else:
                self.status_label.setText(f"다운로드 중: {d['_percent_str']} ({d['_eta_str']} 남음)")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    QApplication.setApplicationName("비디오 다운로더 브라우저")
    window = Browser()
    sys.exit(app.exec())

