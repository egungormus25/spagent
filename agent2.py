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
LEADERBOARD_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/leaderboard"

LOGO_FILE = "splogo.png"
VIDEO_FILE = "background_video.mp4"
BACKGROUND_IMAGE_FILE = "supercar_bg.jpg" 
PIN_CODE = "1923"

NETFLIX_RED = "#E50914"
NETFLIX_BLACK = "#141414"

# --- 📡 NETWORK MOTORU ---
class NetworkWorker(QObject):
    status_updated = Signal(bool, int, str, str)
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
                    
                    u_id = fields.get("userId", {}).get("stringValue", "") 
                    
                    u_name = "YARIŞÇI"
                    
                    if u_id:
                        try:
                            user_url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/users/{u_id}"
                            ur = requests.get(user_url, timeout=3)
                            if ur.status_code == 200:
                                u_fields = ur.json().get("fields", {})
                                u_name = u_fields.get("name", {}).get("stringValue", "YARIŞÇI")
                        except Exception as e:
                            print(f"Kullanıcı adı çekilemedi: {e}")
                    
                    self.status_updated.emit(is_locked, rem_time, u_name, u_id)
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

# --- ⏱️ HAYALET (GHOST) HUD PENCERESİ ---
class MiniPillWindow(QWidget):
    def __init__(self, scale_factor):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool | 
            Qt.WindowDoesNotAcceptFocus | 
            Qt.WindowTransparentForInput | 
            Qt.BypassWindowManagerHint 
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating) 
        
        self.setFixedSize(int(1000 * scale_factor), int(300 * scale_factor))
        self.setStyleSheet("background: transparent;")
        
        self.main_lay = QGridLayout(self)
        self.main_lay.setContentsMargins(15, 15, 15, 15)
        self.main_lay.setSpacing(10)
        
        self.card_track = QFrame()
        self.setup_card(self.card_track, "📍", "PİST BEKLENİYOR", "PİST & ARAÇ", scale_factor, (0,0))
        
        self.card_curr = QFrame()
        self.setup_card(self.card_curr, "⏱️", "--:--.---", "MEVCUT TUR SÜRESİ", scale_factor, (0,1))
        
        self.card_rem = QFrame()
        self.setup_card(self.card_rem, "⏳", "00:00", "KALAN SÜRE", scale_factor, (1,0), NETFLIX_RED)
        
        self.card_best = QFrame()
        self.setup_card(self.card_best, "👑", "--:--.---", "EN İYİ TUR (BEST LAP)", scale_factor, (1,1), "#00FF88")

    def setup_card(self, card, icon_text, value_text, label_text, scale_factor, grid_pos, value_color="white"):
        # 💡 DÜZELTME: Alpha değerini 100'den 30'a çektik. Neredeyse tamamen şeffaf!
        card.setStyleSheet("""
            QFrame {
                background: rgba(0, 0, 0, 30); 
                border-radius: 8px; 
                border: none;
            }
        """)
        card_lay = QHBoxLayout(card); card_lay.setContentsMargins(15, 5, 15, 5)
        
        icon = QLabel(icon_text); icon.setStyleSheet(f"color: {NETFLIX_RED}; font-size: {int(32*scale_factor)}px; font-weight: bold; background: transparent;")
        
        v_lay = QVBoxLayout(); v_lay.setSpacing(0)
        
        value_label = QLabel(value_text)
        value_label.setStyleSheet(f"""
            color: {value_color}; 
            font-size: {int(26*scale_factor)}px; 
            font-weight: 900; 
            background: transparent;
        """)
        
        desc_label = QLabel(label_text)
        desc_label.setStyleSheet(f"color: #DDD; font-size: {int(13*scale_factor)}px; font-weight: bold; background: transparent;")
        
        v_lay.addWidget(value_label); v_lay.addWidget(desc_label)
        card_lay.addWidget(icon); card_lay.addLayout(v_lay)
        self.main_lay.addWidget(card, grid_pos[0], grid_pos[1])
        
        card.value_label = value_label
        card.desc_label = desc_label 

    def update_time_and_user(self, t_str, user_name):
        self.card_rem.value_label.setText(t_str)
        self.card_track.desc_label.setText(f"{user_name[:15]} // PİST & ARAÇ")

    def update_telemetry(self, track, car, curr, best, scale_factor):
        if track:
            track_and_car = f"{track[:10]} // {car[:15]}"
            self.card_track.value_label.setText(track_and_car)
            self.card_curr.value_label.setText(curr if curr and curr != "0" else "--:--.---")
            self.card_best.value_label.setText(best if best and best != "0" else "--:--.---")
        else:
            self.card_track.value_label.setText("PİST BEKLENİYOR")
            self.card_curr.value_label.setText("--:--.---")
            self.card_best.value_label.setText("--:--.---")

# --- 🏎️ CANLI TELEMETRİ MOTORU ---
class ACTelemetryWorker(QObject):
    telemetry_updated = Signal(str, str, str, str, str)
    def run(self):
        if sys.platform != "win32": return
        import ctypes; import mmap
        
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        FILE_MAP_READ = 4

        class ACStatic(ctypes.Structure):
            _pack_ = 4
            _fields_ = [("smVersion", ctypes.c_wchar * 15), ("acVersion", ctypes.c_wchar * 15),
                        ("numberOfSessions", ctypes.c_int32), ("numCars", ctypes.c_int32),
                        ("carModel", ctypes.c_wchar * 33), ("track", ctypes.c_wchar * 33)]
        class ACGraphics(ctypes.Structure):
            _pack_ = 4
            _fields_ = [("packetId", ctypes.c_int32), ("status", ctypes.c_int32),
                        ("session", ctypes.c_int32), ("currentTime", ctypes.c_wchar * 15),
                        ("lastTime", ctypes.c_wchar * 15), ("bestTime", ctypes.c_wchar * 15)]
        
        self.total_ms = 0
        self.last_packet_id = -1
        
        while True:
            handle_static = kernel32.OpenFileMappingW(FILE_MAP_READ, False, "Local\\acpmf_static")
            if not handle_static:
                self.telemetry_updated.emit("", "", "", "", "")
                self.total_ms = 0
                self.last_packet_id = -1
                time.sleep(1) 
                continue
            
            kernel32.CloseHandle(handle_static)

            try:
                shm_static = mmap.mmap(-1, ctypes.sizeof(ACStatic), "Local\\acpmf_static", access=mmap.ACCESS_READ)
                shm_graphics = mmap.mmap(-1, ctypes.sizeof(ACGraphics), "Local\\acpmf_graphics", access=mmap.ACCESS_READ)
                
                track_name = ACStatic.from_buffer_copy(shm_static).track
                car_name = ACStatic.from_buffer_copy(shm_static).carModel
                g_data = ACGraphics.from_buffer_copy(shm_graphics)
                
                if g_data.status == 2 and track_name:
                    if self.last_packet_id != -1 and g_data.packetId > self.last_packet_id:
                        self.total_ms += 500
                    self.last_packet_id = g_data.packetId
                    
                    self.telemetry_updated.emit(track_name.upper(), car_name.upper(), g_data.currentTime, g_data.bestTime, self.ms_to_time_string(self.total_ms))
                else: 
                    self.telemetry_updated.emit("", "", "", "", "")
                    self.total_ms = 0
                    self.last_packet_id = -1
                
                shm_static.close()
                shm_graphics.close()
            except Exception: 
                self.telemetry_updated.emit("", "", "", "", "")
                self.total_ms = 0
                self.last_packet_id = -1
            
            time.sleep(0.5)
            
    def ms_to_time_string(self, ms):
        seconds = ms // 1000
        hours = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

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
        self.setFixedSize(QSize(int(base_width * 1.25), int(base_height * 1.45)))
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
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.showFullScreen()
        
        self.main_stacked = QStackedLayout(self)
        self.main_stacked.setStackingMode(QStackedLayout.StackAll)

        self.full_ui = QStackedWidget()
        self.setup_locked_view()     
        self.setup_active_view()     
        self.setup_loading_view()    
        self.main_stacked.addWidget(self.full_ui)

        self.setup_admin_panel()

        self.loader = ImageLoader()
        self.loader.done.connect(lambda pix, lbl: lbl.setPixmap(pix))
        
        self.mini_window = MiniPillWindow(self.scale_factor)
        self.mini_window.hide()
        
        self.remaining_seconds = 0
        self.is_locked = True
        self.last_synced_cloud_time = -1
        self.is_mini_mode = False
        self.current_user_name = "YARIŞÇI"
        self.current_user_id = "" 
        self.current_game_exe = None

        self.session_track = ""
        self.session_car = ""
        self.session_best_time = ""
        self.last_sent_best_time = "" 
        self.session_doc_id = ""      
        self.session_total_time = "" 

        self.worker = NetworkWorker()
        self.worker.status_updated.connect(self.sync_status)
        self.worker.games_loaded.connect(self.render_games)
        threading.Thread(target=self.worker.run, daemon=True).start()

        self.ac_telemetry = ACTelemetryWorker()
        self.ac_telemetry.telemetry_updated.connect(self.handle_telemetry)
        threading.Thread(target=self.ac_telemetry.run, daemon=True).start()

        self.ticker = QTimer(self); self.ticker.timeout.connect(self.local_tick); self.ticker.start(1000)

    def handle_telemetry(self, track, car, curr, best, total):
        if best and best != "0" and best != "--:--.---":
            self.session_track = track
            self.session_car = car
            self.session_best_time = best
            self.session_total_time = total
            
            if self.session_best_time != self.last_sent_best_time:
                self.last_sent_best_time = self.session_best_time
                self.save_session_record() 
                
        self.mini_window.update_telemetry(track, car, curr, best, self.scale_factor)

    def save_session_record(self):
        if self.session_best_time and self.session_best_time != "0" and self.session_doc_id:
            print(f"⚡ CANLI GÜNCELLEME: {self.current_user_name} | YENİ REKOR: {self.session_best_time} | TOPLAM: {self.session_total_time}")
            
            payload = {
                "fields": {
                    "userId": {"stringValue": self.current_user_id},
                    "userName": {"stringValue": self.current_user_name},
                    "carModel": {"stringValue": self.session_car},
                    "track": {"stringValue": self.session_track},
                    "bestTime": {"stringValue": self.session_best_time},
                    "totalRaceTime": {"stringValue": self.session_total_time}
                }
            }
            
            doc_url = f"{LEADERBOARD_URL}/{self.session_doc_id}"
            
            def _patch():
                try: requests.patch(doc_url, json=payload, timeout=5)
                except Exception as e: print(f"Bulut canlı kayıt hatası: {e}")
            
            threading.Thread(target=_patch, daemon=True).start()

    def setup_locked_view(self):
        self.locked_widget = QWidget(); lay = QGridLayout(self.locked_widget); lay.setContentsMargins(0, 0, 0, 0)
        self.v_widget = QVideoWidget(); self.player = QMediaPlayer(); self.audio = QAudioOutput(); self.audio.setVolume(0)
        self.player.setAudioOutput(self.audio); self.player.setVideoOutput(self.v_widget)
        v_path = os.path.join(os.path.dirname(__file__), VIDEO_FILE)
        if os.path.exists(v_path): self.player.setSource(QUrl.fromLocalFile(v_path)); self.player.setLoops(QMediaPlayer.Infinite); self.player.play()
        scrim = QFrame(); scrim.setStyleSheet("background-color: rgba(0, 0, 0, 180);")
        self.lock_text = QLabel("SPEED POINT\nLÜTFEN SÜRE BAŞLATIN"); self.lock_text.setAlignment(Qt.AlignCenter); self.lock_text.setStyleSheet(f"color: white; font-size: {int(110*self.scale_factor)}px; font-weight: 900;")
        lay.addWidget(self.v_widget, 0, 0); lay.addWidget(scrim, 0, 0); lay.addWidget(self.lock_text, 0, 0)
        self.full_ui.addWidget(self.locked_widget)

    def setup_active_view(self):
        self.active_widget = QWidget(); lay = QGridLayout(self.active_widget); lay.setContentsMargins(0, 0, 0, 0)
        self.bg_label = QLabel(); b_path = os.path.join(os.path.dirname(__file__), BACKGROUND_IMAGE_FILE)
        if os.path.exists(b_path):
            self.bg_label.setPixmap(QPixmap(b_path).scaled(QApplication.primaryScreen().size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            blur = QGraphicsBlurEffect(); blur.setBlurRadius(250); self.bg_label.setGraphicsEffect(blur)
        self.scrim_overlay = QFrame(); self.scrim_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 160);")
        ui_frame = QFrame(); ui_frame.setAttribute(Qt.WA_TranslucentBackground); ui_lay = QVBoxLayout(ui_frame); ui_lay.setContentsMargins(120*self.scale_factor, 100*self.scale_factor, 120*self.scale_factor, 100*self.scale_factor)
        header = QHBoxLayout(); self.logo = QLabel(); l_path = os.path.join(os.path.dirname(__file__), LOGO_FILE)
        if os.path.exists(l_path): self.logo.setPixmap(QPixmap(l_path).scaledToHeight(int(140*self.scale_factor), Qt.SmoothTransformation))
        v_header = QVBoxLayout()
        self.welcome_label = QLabel("HOŞ GELDİN"); self.welcome_label.setStyleSheet(f"color: white; font-size: {int(36*self.scale_factor)}px; font-weight: bold;")
        self.timer_label = QLabel("00:00"); self.timer_label.setStyleSheet(f"color: {NETFLIX_RED}; font-size: {int(60*self.scale_factor)}px; font-weight: 900;")
        v_header.addWidget(self.welcome_label); v_header.addWidget(self.timer_label); header.addLayout(v_header); header.addStretch(); header.addWidget(self.logo); ui_lay.addLayout(header)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll_content = QWidget(); self.grid_container = QVBoxLayout(self.scroll_content); self.grid_container.setAlignment(Qt.AlignCenter)
        self.grid = QGridLayout(); self.grid.setSpacing(80 * self.scale_factor); self.grid.setAlignment(Qt.AlignCenter)
        self.grid_container.addLayout(self.grid); self.scroll.setWidget(self.scroll_content); ui_lay.addWidget(self.scroll)
        lay.addWidget(self.bg_label, 0, 0); lay.addWidget(self.scrim_overlay, 0, 0); lay.addWidget(ui_frame, 0, 0)
        self.full_ui.addWidget(self.active_widget)

    def setup_loading_view(self):
        self.loading_widget = QWidget(); self.loading_widget.setStyleSheet(f"background-color: {NETFLIX_BLACK};"); lay = QVBoxLayout(self.loading_widget)
        logo = QLabel(); l_path = os.path.join(os.path.dirname(__file__), LOGO_FILE)
        if os.path.exists(l_path): logo.setPixmap(QPixmap(l_path).scaledToHeight(int(200*self.scale_factor), Qt.SmoothTransformation))
        text = QLabel("OYUN BAŞLATILIYOR...\nLÜTFEN BEKLEYİN"); text.setAlignment(Qt.AlignCenter); text.setStyleSheet(f"color: white; font-size: {int(50*self.scale_factor)}px; font-weight: 900;")
        lay.addStretch(); lay.addWidget(logo, alignment=Qt.AlignCenter); lay.addSpacing(50); lay.addWidget(text, alignment=Qt.AlignCenter); lay.addStretch()
        self.full_ui.addWidget(self.loading_widget)

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

    def switch_to_full(self):
        self.is_mini_mode = False
        self.mini_window.hide()
        self.showNormal()
        self.showFullScreen()
        self.full_ui.setCurrentIndex(1 if not self.is_locked else 0)

    def kill_current_game(self):
        if self.current_game_exe and sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/F", "/IM", self.current_game_exe, "/T"], capture_output=True)
                subprocess.run(["taskkill", "/F", "/IM", "acs.exe", "/T"], capture_output=True)
            except: pass
            self.current_game_exe = None

    def sync_status(self, locked_cloud, time_cloud, user_name, user_id):
        self.current_user_name = user_name.upper()
        self.current_user_id = user_id 
        self.welcome_label.setText(f"HOŞ GELDİN, {self.current_user_name}")
        
        if self.is_locked == True and locked_cloud == False:
            self.is_locked = False; self.remaining_seconds = time_cloud; self.last_synced_cloud_time = time_cloud
            self.switch_to_full(); self.full_ui.setCurrentIndex(1); self.player.stop()
            
        elif self.is_locked == False and locked_cloud == True:
            self.kill_current_game() 
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
            self.mini_window.update_time_and_user(t_str, self.current_user_name) 
            
            if self.remaining_seconds <= 0:
                self.kill_current_game()
                self.sync_status(True, 0, "YARIŞÇI", "") 

    def render_games(self, games):
        while self.grid.count():
            item = self.grid.takeAt(0); item.widget().deleteLater()
        for i, game in enumerate(games):
            card = GameCard(game["title"], game["imageUrl"], game["localPath"], self.loader, self.scale_factor)
            card.clicked.connect(self.launch_game)
            self.grid.addWidget(card, i // 3, i % 3)

    def launch_game(self, path):
        if self.is_locked or not path or self.is_mini_mode: return 
        self.is_mini_mode = True
        
        safe_user = self.current_user_id if self.current_user_id else "USER"
        self.session_doc_id = f"sess_{int(time.time())}_{safe_user}"
        self.last_sent_best_time = ""
        self.session_best_time = ""
        
        clean_path = path.strip('"')
        self.current_game_exe = os.path.basename(clean_path)
        
        self.full_ui.setCurrentIndex(2)
        
        screen_geo = QApplication.primaryScreen().geometry()
        pill_w, pill_h = self.mini_window.width(), self.mini_window.height()
        self.mini_window.move(screen_geo.width() - pill_w - 20, 20)
        self.mini_window.show()

        try:
            game_dir = os.path.dirname(clean_path)
            if sys.platform == "darwin": subprocess.Popen(["open", clean_path])
            elif sys.platform == "win32": subprocess.Popen(f'"{clean_path}"', shell=True, cwd=game_dir)
            else: subprocess.Popen([clean_path], cwd=game_dir)
        except Exception as e:
            self.switch_to_full()
            print(f"❌ Oyun başlatılamadı: {e}")
            return

        QTimer.singleShot(12000, self.hide_shield)

    def hide_shield(self):
        if self.is_mini_mode and not self.is_locked:
            self.hide() 

    def check_pin(self):
        if self.pin_input.text() == PIN_CODE: self.admin_overlay.setVisible(False); self.sync_status(False, 3600, "ADMİN", "ADMIN_001")
        self.pin_input.clear()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_X and (event.modifiers() & Qt.ControlModifier or event.modifiers() & Qt.MetaModifier) and (event.modifiers() & Qt.ShiftModifier):
            QApplication.quit()
        if event.key() == Qt.Key_Escape and self.is_mini_mode:
            self.kill_current_game() 
            self.switch_to_full()
        if event.key() == Qt.Key_M and (event.modifiers() & Qt.ControlModifier or event.modifiers() & Qt.MetaModifier) and (event.modifiers() & Qt.ShiftModifier):
            self.admin_overlay.setGeometry(0, 0, self.width(), self.height()); self.admin_overlay.setVisible(True); self.pin_input.setFocus()

if __name__ == "__main__":
    app = QApplication(sys.argv); window = SpeedPointAgent(); sys.exit(app.exec())