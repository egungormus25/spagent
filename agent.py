import tkinter as tk
from PIL import Image, ImageTk, ImageSequence
import os
import requests
import time
import threading
import queue
import logging
import sys
import subprocess # 🚨 YENİ: Oyunları .exe'den başlatmak için eklendi

# --- AYARLAR ---
VERSION = "1.0.6"  # Kiosk Modu Güncellemesi
PROJECT_ID = "speedpoint-928e1"
MACHINE_ID = "PC_01"
FIRESTORE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/machines/{MACHINE_ID}"

# 🚨 YENİ: DÜKKANDAKİ OYUNLARIN LİSTESİ
# Resim yollarını (image_path) dükkandaki PC'ye göre ayarlayabilirsin. Resim yoksa sadece isim yazar.
GAMES = [
    {
        "name": "Assetto Corsa",
        "image_path": "images/assetto.png", 
        "exe_path": r"C:\Windows\System32\notepad.exe" # TEST İÇİN NOT DEFTERİ (Gerçek oyun yolunu buraya yaz)
    },
    {
        "name": "F1 24",
        "image_path": "images/f1.png",
        "exe_path": r"C:\Windows\System32\calc.exe" # TEST İÇİN HESAP MAKİNESİ (Gerçek oyun yolunu buraya yaz)
    },
    {
        "name": "Forza Horizon 5",
        "image_path": "images/forza.png",
        "exe_path": r"C:\Windows\explorer.exe" # TEST İÇİN KLASÖR
    }
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])

class SpeedPointAgent:
    def __init__(self):
        self.root = None
        self.bg_frames = []
        self.timer_label = None
        self.bg_label = None
        self.is_locked_state = True 
        self.local_remaining_time = 0 
        
        self.manual_override = False 
        self.admin_frame = None 
        self.PIN_CODE = "1923" 
        self.is_online = False 
        self.status_light = None
        
        self.game_images = [] # Resimlerin çöpe gitmemesi (Garbage Collection) için referans listesi

        self.request_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.network_thread = None

    def start_app(self):
        self.root = tk.Tk()
        self.root.title("SpeedPoint Agent")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.config(bg="black")
        
        self.loading_label = tk.Label(self.root, text="Sistem Hazırlanıyor...\nLütfen Bekleyin", fg="#FFD700", bg="black", font=("Arial", 24, "bold"))
        self.loading_label.pack(expand=True)
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        self.root.bind('<Control-Shift-KeyPress-M>', self.show_admin_panel)
        self.root.bind('<Command-Shift-KeyPress-M>', self.show_admin_panel)

        self.root.after(500, self.load_assets_and_start)
        self.root.mainloop()

    # --- NETWORK VE THREAD KODLARI (SENİN KUSURSUZ ALTYAPIN - DOKUNULMADI) ---
    def start_network_thread(self):
        if self.network_thread is None or not self.network_thread.is_alive():
            self.network_thread = threading.Thread(target=self.network_worker, daemon=True)
            self.network_thread.start()
            logging.info("Network thread başlatıldı.")

    def network_worker(self):
        while True:
            try:
                request_type, url, payload, original_data = self.request_queue.get()
                if request_type == "GET":
                    response = requests.get(url, timeout=5)
                elif request_type == "PATCH":
                    response = requests.patch(url, json=payload, timeout=5)
                else:
                    continue
                response.raise_for_status()
                response_data = response.json() if response.content else None
                self.response_queue.put(("success", request_type, response_data, original_data))
            except Exception as e:
                self.response_queue.put(("error", request_type, e, original_data))
            finally:
                self.request_queue.task_done()

    def process_network_responses(self):
        try:
            while not self.response_queue.empty():
                status, request_type, data, original_data = self.response_queue.get_nowait()
                if status == "success":
                    self.set_online_status(True)
                    if request_type == "GET": self.handle_firebase_poll_response(data)
                    elif request_type == "PATCH": self.handle_firebase_sync_response(original_data)
                else:
                    logging.error(f"Ağ isteği başarısız ({request_type}): {data}")
                    self.set_online_status(False)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_network_responses)

    def handle_firebase_poll_response(self, data):
        fields = data.get("fields", {})
        is_locked_db = fields.get("isLocked", {}).get("booleanValue", True)
        rem_time_db = int(fields.get("remainingTime", {}).get("integerValue", "0"))

        if is_locked_db is False and self.is_locked_state is True:
            logging.info("Sunucudan KİLİT AÇMA komutu alındı.")
            self.local_remaining_time = rem_time_db
            self.setup_ui(lock_mode=False)
        elif is_locked_db is True and self.is_locked_state is False and not self.manual_override:
            logging.info("Sunucudan KİLİTLEME komutu alındı.")
            self.local_remaining_time = 0
            self.setup_ui(lock_mode=True)

    def handle_firebase_sync_response(self, original_data):
        logging.info("Firebase senkronizasyonu başarılı.")
        if original_data and not original_data.get('is_locked'):
            logging.info("Manuel override bayrağı sıfırlandı.")
            self.manual_override = False

    def load_assets_and_start(self):
        if os.path.exists("background.gif"):
            try:
                with Image.open("background.gif") as gif_obj:
                    sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
                    self.bg_frames = []
                    for i, frame in enumerate(ImageSequence.Iterator(gif_obj)):
                        if i % 10 == 0: 
                            resized = frame.copy().convert('RGBA').resize((sw, sh), Image.Resampling.LANCZOS)
                            self.bg_frames.append(ImageTk.PhotoImage(resized))
            except Exception as e:
                logging.error(f"background.gif yüklenemedi: {e}")
                self.bg_frames = []
        self.loading_label.destroy()
        self.setup_ui(lock_mode=True)
        self.start_network_thread()
        self.process_network_responses()
        self.poll_firebase()
        self.local_countdown()

    # --- 🚨 YENİ: ARAYÜZ (KİOSK VE KİLİT EKRANI) KURULUMU ---
    def setup_ui(self, lock_mode=True):
        if self.is_locked_state == lock_mode and self.root.winfo_children():
            return

        self.is_locked_state = lock_mode
        self.game_images.clear() # Önceki resim referanslarını temizle

        for widget in self.root.winfo_children():
            widget.destroy()

        if lock_mode:
            # 🔴 KİLİTLİ MOD (Eski Sistemin Aynısı)
            self.root.attributes("-fullscreen", True)
            self.root.attributes("-topmost", True) # Kimse kaçamasın
            self.root.overrideredirect(True)
            self.root.config(bg="black")

            if self.bg_frames:
                self.bg_label = tk.Label(self.root, bd=0)
                self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                self.animate_background(0)
            else:
                self.bg_label = None

            tk.Label(self.root, text="SPEED POINT\nLÜTFEN SÜRE BAŞLATIN", fg="#00E676", bg="black", font=("Arial", 60, "bold")).place(relx=0.5, rely=0.5, anchor="center")
            
            # Statüs Işığı Pozisyonu (Kilitliyken sağ alt)
            status_light_font, status_light_relx, status_light_rely, status_light_anchor, status_light_bg = (("Arial", 24), 0.98, 0.98, "se", "black")

        else:
            # 🟢 AÇIK MOD (YENİ KİOSK/MENÜ EKRANI)
            self.root.attributes("-fullscreen", True) # Masaüstünü kapatmaya devam et
            self.root.attributes("-topmost", False)   # 🚨 ÇOK KRİTİK: Oyunun ekrana gelebilmesi için topmost kapalı olmalı!
            self.root.overrideredirect(True)
            self.root.config(bg="#0A0A0A")
            
            # Üst Bar (Süre ve Logo)
            top_frame = tk.Frame(self.root, bg="#121212", height=80)
            top_frame.pack(side="top", fill="x")
            
            tk.Label(top_frame, text="SPEED POINT YARIŞ MERKEZİ", fg="#FFF", bg="#121212", font=("Arial", 24, "bold")).pack(side="left", padx=30, pady=20)
            self.timer_label = tk.Label(top_frame, text="Süre: --:--", fg="#00E676", bg="#121212", font=("Arial", 28, "bold"))
            self.timer_label.pack(side="right", padx=50, pady=20)

            # Oyun Başlığı
            tk.Label(self.root, text="OYNAMAK İSTEDİĞİNİZ OYUNU SEÇİN", fg="#888", bg="#0A0A0A", font=("Arial", 18)).pack(pady=(60, 20))

            # Oyunları Dizeceğimiz Kutu
            games_frame = tk.Frame(self.root, bg="#0A0A0A")
            games_frame.pack(expand=True)

            # Oyun Butonlarını Yarat
            for game in GAMES:
                btn_image = None
                if os.path.exists(game.get("image_path", "")):
                    try:
                        img = Image.open(game["image_path"]).resize((250, 350), Image.Resampling.LANCZOS)
                        btn_image = ImageTk.PhotoImage(img)
                        self.game_images.append(btn_image) # Çöpe gitmesini engelle
                    except Exception:
                        pass
                
                # Resim varsa resimli, yoksa yazılı buton yap
                if btn_image:
                    btn = tk.Button(games_frame, image=btn_image, bg="#1A1A1A", bd=0, activebackground="#00E676", cursor="hand2", command=lambda p=game["exe_path"]: self.launch_game(p))
                else:
                    btn = tk.Button(games_frame, text=game["name"], font=("Arial", 20, "bold"), fg="#FFF", bg="#1A1A1A", width=15, height=8, bd=2, relief="groove", activebackground="#00E676", cursor="hand2", command=lambda p=game["exe_path"]: self.launch_game(p))
                
                btn.pack(side="left", padx=20)

            # Statüs Işığı Pozisyonu (Açıkken sağ alt köşe)
            status_light_font, status_light_relx, status_light_rely, status_light_anchor, status_light_bg = (("Arial", 18), 0.98, 0.98, "se", "#0A0A0A")

        self.status_light = tk.Label(self.root, text="●", font=status_light_font, bg=status_light_bg, bd=0)
        self.status_light.place(relx=status_light_relx, rely=status_light_rely, anchor=status_light_anchor)
        self.refresh_light_color()

    # 🚨 YENİ: OYUNU BAŞLATAN FONKSİYON
    def launch_game(self, exe_path):
        logging.info(f"Oyun başlatılıyor: {exe_path}")
        try:
            # subprocess ile oyunu arkada başlat (Arayüzümüz donmaz)
            subprocess.Popen(exe_path)
        except Exception as e:
            logging.error(f"Oyun başlatılamadı: {e}")

    # --- GERİ KALAN FONKSİYONLAR AYNI ---
    def set_online_status(self, is_online_now):
        if self.is_online != is_online_now:
            self.is_online = is_online_now
            self.refresh_light_color()

    def refresh_light_color(self):
        if self.status_light and self.status_light.winfo_exists():
            color = "#43B581" if self.is_online else "#F04747"
            self.status_light.config(fg=color)

    def animate_background(self, counter):
        if self.is_locked_state and self.bg_frames and self.bg_label and self.bg_label.winfo_exists():
            try:
                self.bg_label.configure(image=self.bg_frames[counter])
                self.root.after(60, self.animate_background, (counter + 1) % len(self.bg_frames))
            except (tk.TclError, IndexError) as e:
                logging.warning(f"Arka plan animasyonu durdu: {e}")

    def show_admin_panel(self, event=None):
        if self.admin_frame: return 
        self.admin_frame = tk.Frame(self.root, bg="#2C2F33", bd=5, relief="ridge", padx=20, pady=20)
        self.admin_frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(self.admin_frame, text="YÖNETİCİ GİRİŞİ", fg="#FFD700", bg="#2C2F33", font=("Arial", 16, "bold")).pack(pady=10)
        
        self.pin_entry = tk.Entry(self.admin_frame, show="*", font=("Arial", 20), justify="center", width=10)
        self.pin_entry.pack(pady=10)
        self.pin_entry.focus()
        self.pin_entry.bind('<Return>', lambda e: self.check_pin())
        
        tk.Button(self.admin_frame, text="ONAYLA", bg="#7289DA", fg="white", font=("Arial", 12, "bold"), command=self.check_pin).pack(pady=5)
        tk.Button(self.admin_frame, text="İPTAL", bg="#99AAB5", font=("Arial", 10), command=self.close_admin_panel).pack()

    def check_pin(self):
        if self.pin_entry.get() == self.PIN_CODE:
            self.close_admin_panel()
            self.show_admin_time_selection()
        else:
            if hasattr(self, 'pin_error_label') and self.pin_error_label.winfo_exists(): return
            self.pin_error_label = tk.Label(self.admin_frame, text="Hatalı Şifre!", fg="#F04747", bg="#2C2F33")
            self.pin_error_label.pack()
            self.pin_entry.delete(0, tk.END)
            self.pin_error_label.after(2000, self.pin_error_label.destroy)

    def show_admin_time_selection(self):
        self.admin_frame = tk.Frame(self.root, bg="#2C2F33", bd=5, relief="ridge", padx=20, pady=20)
        self.admin_frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(self.admin_frame, text="Masa Aç (Offline)", fg="#43B581", bg="#2C2F33", font=("Arial", 16, "bold")).pack(pady=10)
        
        times = [(15, "15 Dakika"), (30, "30 Dakika"), (60, "1 Saat"), (120, "2 Saat")]
        for mins, text in times:
            tk.Button(self.admin_frame, text=text, width=20, bg="#7289DA", fg="white", font=("Arial", 12), command=lambda m=mins: self.start_offline_session(m)).pack(pady=5)
        tk.Button(self.admin_frame, text="Vazgeç", command=self.close_admin_panel).pack(pady=10)

    def start_offline_session(self, minutes):
        self.local_remaining_time = minutes * 60
        self.manual_override = True 
        self.close_admin_panel()
        self.setup_ui(lock_mode=False)
        self.sync_to_firebase(is_locked=False, remaining_time=self.local_remaining_time)

    def close_admin_panel(self):
        if self.admin_frame:
            self.admin_frame.destroy()
            self.admin_frame = None

    def poll_firebase(self):
        if all(item[0] != "GET" for item in self.request_queue.queue):
            self.request_queue.put(("GET", FIRESTORE_URL, None, None))
        if self.root: self.root.after(3000, self.poll_firebase)

    def local_countdown(self):
        if not self.is_locked_state and self.local_remaining_time > 0:
            self.local_remaining_time -= 1
            
            if self.timer_label and self.timer_label.winfo_exists():
                mins, secs = divmod(self.local_remaining_time, 60)
                self.timer_label.config(text=f"Süre: {mins:02d}:{secs:02d}")
            
            if self.local_remaining_time % 10 == 0 and self.local_remaining_time > 0:
                self.sync_to_firebase(is_locked=False, remaining_time=self.local_remaining_time)
            
            if self.local_remaining_time <= 0:
                logging.info("Süre doldu! Ekran kilitleniyor.")
                self.setup_ui(lock_mode=True)
                self.sync_to_firebase(is_locked=True, remaining_time=0)

        if self.root: self.root.after(1000, self.local_countdown)

    def sync_to_firebase(self, is_locked, remaining_time):
        patch_url = f"{FIRESTORE_URL}?updateMask.fieldPaths=isLocked&updateMask.fieldPaths=remainingTime"
        payload = {"fields": {"isLocked": {"booleanValue": is_locked}, "remainingTime": {"integerValue": str(int(remaining_time))}}}
        original_data = {'is_locked': is_locked}
        self.request_queue.put(("PATCH", patch_url, payload, original_data))

if __name__ == "__main__":
    agent = SpeedPointAgent()
    agent.start_app()