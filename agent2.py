import sys
import os
import subprocess
import threading
import requests
import time
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtMultimedia import *
from PySide6.QtMultimediaWidgets import *

# --- ⚙️ SİSTEM AYARLARI ---
PROJECT_ID = "speedpoint-928e1"
MACHINE_ID = "PC_01" 
FIRESTORE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/machines/{MACHINE_ID}"
GAMES_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/games"

LOGO_FILE = "splogo.png"
VIDEO_FILE = "background_video.mp4"
BACKGROUND_IMAGE_FILE = "supercar_bg.jpg" 
PIN_CODE = "1923"

NETFLIX_RED = "#E50914"
NETFLIX_BLACK = "#141414"

# --- 📡 NETWORK MOTORU ---
class NetworkWorker(QObject):
    status_updated = Signal(bool, int, str)
    games_loaded = Signal(list)

    def run(self):
        self.fetch_games()
        while True:
            try:
                r = requests.get(FIRESTORE_URL, timeout=5)
                if r.status_code == 200:
                    fields = r.json().get("fields", {})
                    is_locked = fields.get("isLocked", {}).get("booleanValue", True)
                    rem_time = int(fields.get("remainingTime", {}).get("integerValue", "0"))
                    u_name = fields.get("userName", {}).get("stringValue", "Yarışçı")
                    self.status_updated.emit(is_locked, rem_time, u_name)
            except: pass
            time.sleep(3)

    def fetch_games(self):
        try:
            r = requests.get(GAMES_URL, timeout=5)
            if r.status_code == 200:
                docs = r.json().get("documents", [])
                games_list = []
                for doc in docs:
                    f = doc.get("fields", {})
                    games_list.append({
                        "title": f.get("title", {}).get("stringValue", "Oyun").upper(),
                        "imageUrl": f.get("imageUrl", {}).get("stringValue", ""),
                        "localPath": f.get("localPath", {}).get("stringValue", "")
                    })
                self.games_loaded.emit(games_list)
        except: pass

class ImageLoader(QObject):
    done = Signal(QPixmap, QLabel)
    def load(self, url, label, scale_size):
        def _thread():
            try:
                r = requests.get(url, timeout=5)
                pix = QPixmap.fromImage(QImage.fromData(r.content))
                self.done.emit(pix.scaled(scale_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation), label)
            except: pass
        threading.Thread(target=_thread, daemon=True).start()

# --- 🎮 MEGA OYUN KARTI ---
class GameCard(QFrame):
    clicked = Signal(str)
    def __init__(self, title, img_url, local_path, loader, scale_factor, parent=None):
        super().__init__(parent)
        self.local_path = local_path
        self.scale_factor = scale_factor
        base_width, base_height = int(520 * self.scale_factor), int(780 * self.scale_factor)
        self.base_poster_size = QSize(base_width, base_height)
        self.hover_poster_size = QSize(int(base_width * 1.1), int(base_height * 1.1))
        self.card_cell_size = QSize(int(base_width * 1.25), int(base_height * 1.45))
        self.setFixedSize(self.card_cell_size)
        self.main_lay = QVBoxLayout(self); self.main_lay.setContentsMargins(0, 0, 0, 0)
        self.poster_container = QFrame(); self.poster_container.setFixedSize(self.hover_poster_size + QSize(30, 30))
        self.main_lay.addWidget(self.poster_container, 0, Qt.AlignCenter)
        self.poster = QLabel(self.poster_container); self.poster.setFixedSize(self.base_poster_size)
        self.poster.setStyleSheet("background: #1a1a1a; border-radius: 25px; border: 3px solid #333;")
        self.poster.setCursor(Qt.PointingHandCursor); self.center_poster()
        self.title_label = QLabel(title); self.title_label.setStyleSheet(f"color: #AAA; font-size: {int(28 * self.scale_factor)}px; font-weight: bold;")
        self.title_label.setAlignment(Qt.AlignCenter); self.main_lay.addWidget(self.title_label)
        self.anim = QPropertyAnimation(self.poster, b"geometry"); self.anim.setDuration(200); self.anim.setEasingCurve(QEasingCurve.OutQuart)
        self.poster.mousePressEvent = lambda e: self.clicked.emit(self.local_path)
        if img_url: loader.load(img_url, self.poster, self.hover_poster_size)
    def center_poster(self):
        cw, ch = self.poster_container.width(), self.poster_container.height()
        pw, ph = self.poster.width(), self.poster.height()
        self.poster.move((cw - pw) / 2, (ch - ph) / 2)
    def enterEvent(self, event):
        cw, ch = self.poster_container.width(), self.poster_container.height()
        w, h = self.hover_poster_size.width(), self.hover_poster_size.height()
        self.anim.setEndValue(QRect((cw - w) / 2, (ch - h) / 2, w, h)); self.anim.start()
        self.poster.setStyleSheet("background: #1a1a1a; border-radius: 25px; border: 6px solid #E50914;")
    def leaveEvent(self, event):
        cw, ch = self.poster_container.width(), self.poster_container.height()
        w, h = self.base_poster_size.width(), self.base_poster_size.height()
        self.anim.setEndValue(QRect((cw - w) / 2, (ch - h) / 2, w, h)); self.anim.start()
        self.poster.setStyleSheet("background: #1a1a1a; border-radius: 25px; border: 3px solid #333;")

# --- 🏎️ ANA AGENT ---
class SpeedPointAgent(QWidget):
    def __init__(self):
        super().__init__()
        screen_size = QApplication.primaryScreen().size()
        self.scale_factor = screen_size.width() / 3840.0 
        if self.scale_factor < 0.6: self.scale_factor = 0.6
        
        # 💡 Always On Top ayarı burada kritik kanka
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.showFullScreen()
        
        self.main_stacked = QStackedLayout(self)
        self.main_stacked.setStackingMode(QStackedLayout.StackAll)

        # 1. TAM EKRAN UI
        self.full_ui = QStackedWidget()
        self.setup_locked_view()
        self.setup_active_view()
        self.main_stacked.addWidget(self.full_ui)

        # 2. MINI OVERLAY (PILL) - Başlangıçta gizli
        self.mini_pill = QFrame()
        self.setup_mini_pill()
        self.main_stacked.addWidget(self.mini_pill)

        self.setup_admin_panel()

        self.loader = ImageLoader()
        self.loader.done.connect(lambda pix, lbl: lbl.setPixmap(pix))
        
        self.remaining_seconds = 0
        self.is_locked = True
        self.last_synced_cloud_time = -1
        self.is_mini_mode = False

        self.worker = NetworkWorker()
        self.worker.status_updated.connect(self.sync_status)
        self.worker.games_loaded.connect(self.render_games)
        threading.Thread(target=self.worker.run, daemon=True).start()

        self.ticker = QTimer(self); self.ticker.timeout.connect(self.local_tick); self.ticker.start(1000)

    def setup_mini_pill(self):
        self.mini_pill.setFixedSize(int(400*self.scale_factor), int(100*self.scale_factor))
        self.mini_pill.setStyleSheet("background: rgba(20, 20, 20, 220); border-radius: 50px; border: 2px solid #E50914;")
        self.mini_pill.setVisible(False)
        
        pill_lay = QHBoxLayout(self.mini_pill)
        self.mini_timer = QLabel("00:00")
        self.mini_timer.setStyleSheet(f"color: white; font-size: {int(36*self.scale_factor)}px; font-weight: 900;")
        pill_lay.addStretch()
        pill_lay.addWidget(self.mini_timer)
        pill_lay.addStretch()

    def setup_locked_view(self):
        self.locked_widget = QWidget()
        lay = QGridLayout(self.locked_widget); lay.setContentsMargins(0, 0, 0, 0)
        self.v_widget = QVideoWidget()
        self.player = QMediaPlayer(); self.audio = QAudioOutput(); self.audio.setVolume(0)
        self.player.setAudioOutput(self.audio); self.player.setVideoOutput(self.v_widget)
        v_path = os.path.join(os.path.dirname(__file__), VIDEO_FILE)
        if os.path.exists(v_path):
            self.player.setSource(QUrl.fromLocalFile(v_path))
            self.player.setLoops(QMediaPlayer.Infinite); self.player.play()
        scrim = QFrame(); scrim.setStyleSheet("background-color: rgba(0, 0, 0, 180);")
        self.lock_text = QLabel("SPEED POINT\nLÜTFEN SÜRE BAŞLATIN")
        self.lock_text.setAlignment(Qt.AlignCenter); self.lock_text.setStyleSheet(f"color: white; font-size: {int(110*self.scale_factor)}px; font-weight: 900;")
        lay.addWidget(self.v_widget, 0, 0); lay.addWidget(scrim, 0, 0); lay.addWidget(self.lock_text, 0, 0)
        self.full_ui.addWidget(self.locked_widget)

    def setup_active_view(self):
        self.active_widget = QWidget()
        lay = QGridLayout(self.active_widget); lay.setContentsMargins(0, 0, 0, 0)
        self.bg_label = QLabel()
        b_path = os.path.join(os.path.dirname(__file__), BACKGROUND_IMAGE_FILE)
        if os.path.exists(b_path):
            pix = QPixmap(b_path)
            self.bg_label.setPixmap(pix.scaled(QApplication.primaryScreen().size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            blur = QGraphicsBlurEffect(); blur.setBlurRadius(250); self.bg_label.setGraphicsEffect(blur)
        self.scrim_overlay = QFrame(); self.scrim_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 160);")
        ui_frame = QFrame(); ui_frame.setAttribute(Qt.WA_TranslucentBackground)
        ui_lay = QVBoxLayout(ui_frame); ui_lay.setContentsMargins(120*self.scale_factor, 100*self.scale_factor, 120*self.scale_factor, 100*self.scale_factor)
        header = QHBoxLayout()
        self.logo = QLabel()
        l_path = os.path.join(os.path.dirname(__file__), LOGO_FILE)
        if os.path.exists(l_path): self.logo.setPixmap(QPixmap(l_path).scaledToHeight(int(140*self.scale_factor), Qt.SmoothTransformation))
        v_header = QVBoxLayout()
        self.welcome_label = QLabel("HOŞ GELDİN"); self.welcome_label.setStyleSheet(f"color: white; font-size: {int(36*self.scale_factor)}px; font-weight: bold;")
        self.timer_label = QLabel("00:00"); self.timer_label.setStyleSheet(f"color: {NETFLIX_RED}; font-size: {int(60*self.scale_factor)}px; font-weight: 900;")
        v_header.addWidget(self.welcome_label); v_header.addWidget(self.timer_label)
        header.addLayout(v_header); header.addStretch(); header.addWidget(self.logo)
        ui_lay.addLayout(header)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll_content = QWidget(); self.grid_container = QVBoxLayout(self.scroll_content); self.grid_container.setAlignment(Qt.AlignCenter)
        self.grid = QGridLayout(); self.grid.setSpacing(80 * self.scale_factor); self.grid.setAlignment(Qt.AlignCenter)
        self.grid_container.addLayout(self.grid); self.scroll.setWidget(self.scroll_content); ui_lay.addWidget(self.scroll)
        lay.addWidget(self.bg_label, 0, 0); lay.addWidget(self.scrim_overlay, 0, 0); lay.addWidget(ui_frame, 0, 0)
        self.full_ui.addWidget(self.active_widget)

    def setup_admin_panel(self):
        self.admin_overlay = QFrame(self); self.admin_overlay.setStyleSheet("background: rgba(0,0,0,230);"); self.admin_overlay.setVisible(False)
        lay = QVBoxLayout(self.admin_overlay); box = QFrame(); box.setFixedSize(int(600*self.scale_factor), int(400*self.scale_factor))
        box.setStyleSheet(f"background: #222; border-radius: 30px; border: 3px solid {NETFLIX_RED};"); b_lay = QVBoxLayout(box)
        self.pin_input = QLineEdit(); self.pin_input.setEchoMode(QLineEdit.Password); self.pin_input.setAlignment(Qt.AlignCenter)
        self.pin_input.setStyleSheet(f"background: #111; color: white; font-size: {int(60*self.scale_factor)}px; border-radius: 15px;")
        btn = QPushButton("ONAYLA"); btn.setStyleSheet(f"background: {NETFLIX_RED}; color: white; font-weight: bold; height: {int(100*self.scale_factor)}px; border-radius: 15px;")
        btn.clicked.connect(self.check_pin); self.pin_input.returnPressed.connect(self.check_pin)
        b_lay.addWidget(QLabel("ADMIN PIN", styleSheet="color: white; font-weight: bold;")); b_lay.addWidget(self.pin_input); b_lay.addWidget(btn)
        lay.addWidget(box, 0, Qt.AlignCenter)

    def switch_to_mini(self):
        # 💡 Oyun açıldığında ekranı küçültüp sağ üste atıyoruz kanka
        self.is_mini_mode = True
        self.full_ui.setVisible(False)
        self.mini_pill.setVisible(True)
        
        # Ekranın sağ üst köşesine taşı kanka
        screen_geo = QApplication.primaryScreen().geometry()
        pill_w, pill_h = self.mini_pill.width(), self.mini_pill.height()
        self.setGeometry(screen_geo.width() - pill_w - 50, 50, pill_w, pill_h)

    def switch_to_full(self):
        self.is_mini_mode = False
        self.mini_pill.setVisible(False)
        self.full_ui.setVisible(True)
        self.showFullScreen()

    def sync_status(self, locked_cloud, time_cloud, user_name):
        self.welcome_label.setText(f"HOŞ GELDİN, {user_name.upper()}")
        if self.is_locked == True and locked_cloud == False:
            self.is_locked = False; self.remaining_seconds = time_cloud; self.last_synced_cloud_time = time_cloud
            self.switch_to_full(); self.full_ui.setCurrentIndex(1); self.player.stop()
        elif self.is_locked == False and locked_cloud == True:
            self.is_locked = True; self.remaining_seconds = 0; self.last_synced_cloud_time = -1
            self.switch_to_full(); self.full_ui.setCurrentIndex(0); self.player.play()
        elif not self.is_locked:
            if time_cloud != self.last_synced_cloud_time:
                self.remaining_seconds = time_cloud; self.last_synced_cloud_time = time_cloud

    def local_tick(self):
        if not self.is_locked and self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            mins, secs = divmod(self.remaining_seconds, 60)
            t_str = f"{mins:02d}:{secs:02d}"
            self.timer_label.setText(t_str)
            self.mini_timer.setText(t_str)
            if self.remaining_seconds <= 0: self.sync_status(True, 0, "YARIŞÇI")

    def render_games(self, games):
        while self.grid.count():
            item = self.grid.takeAt(0); item.widget().deleteLater()
        for i, game in enumerate(games):
            card = GameCard(game["title"], game["imageUrl"], game["localPath"], self.loader, self.scale_factor)
            card.clicked.connect(self.launch_game)
            self.grid.addWidget(card, i // 3, i % 3)

    def launch_game(self, path):
        if not self.is_locked and path:
            print(f"🚀 Oyun Başlatıldı, Mini Moda Geçiliyor...")
            self.switch_to_mini() # 💡 Kapsül moduna geç
            subprocess.Popen(["open", path] if sys.platform == "darwin" else path)

    def check_pin(self):
        if self.pin_input.text() == PIN_CODE: self.admin_overlay.setVisible(False); self.sync_status(False, 3600, "ADMİN")
        self.pin_input.clear()

    def keyPressEvent(self, event):
        # 💡 Admin girişi veya Full ekrana geri dönüş (Geliştirme için kanka)
        if event.key() == Qt.Key_Escape and self.is_mini_mode:
            self.switch_to_full()
        if event.key() == Qt.Key_M and (event.modifiers() & Qt.ControlModifier or event.modifiers() & Qt.MetaModifier) and (event.modifiers() & Qt.ShiftModifier):
            self.admin_overlay.setGeometry(0, 0, self.width(), self.height()); self.admin_overlay.setVisible(True); self.pin_input.setFocus()

if __name__ == "__main__":
    app = QApplication(sys.argv); window = SpeedPointAgent(); sys.exit(app.exec())