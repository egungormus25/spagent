import sys
import os
import time
import threading
import queue
import logging
import requests

try:
    import tkinter as tk
    from PIL import Image, ImageTk, ImageSequence
except ImportError as e:
    print(f"\nKRİTİK HATA: Gerekli modüller yüklenemedi: {e}")
    print("Eğer '_tkinter' hatası alıyorsanız:")
    print("  macOS: 'brew install tcl-tk' yapıp pyenv sürümünü yeniden yükleyin.")
    print("Eğer 'PIL' hatası alıyorsanız: 'pip install Pillow' komutunu çalıştırın.\n")
    sys.exit(1)

# --- AYARLAR ---
VERSION = "1.0.1"  # Launcher bu versiyonu kontrol eder.
PROJECT_ID = "speedpoint-928e1"
MACHINE_ID = "PC_01"  # Diğer masalar için PC_02, PC_03 yapabilirsin
FIRESTORE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/machines/{MACHINE_ID}"

# Hataları ve önemli olayları loglamak için temel bir yapı
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)

class SpeedPointAgent:
    def __init__(self):
        self.root = None
        self.bg_frames = []
        self.timer_label = None
        self.bg_label = None
        self.is_locked_state = True 
        self.local_remaining_time = 0 
        
        # 🚨 ACİL DURUM VE AĞ DEĞİŞKENLERİ
        self.manual_override = False 
        self.admin_frame = None 
        self.PIN_CODE = "1923" 
        self.is_online = False 
        self.status_light = None

        # Ağ isteklerini UI'ı dondurmadan işlemek için thread ve queue yapısı
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

    def start_network_thread(self):
        """Ağ isteklerini yönetecek olan arka plan thread'ini başlatır."""
        if self.network_thread is None:
            self.network_thread = threading.Thread(target=self.network_worker, daemon=True)
            self.network_thread.start()
            logging.info("Network thread başlatıldı.")

    def network_worker(self):
        """Network thread'inin ana döngüsü. Kuyruktan istekleri alıp işler."""
        while True:
            request_type, url, payload, original_data = self.request_queue.get()
            try:
                if request_type == "GET":
                    response = requests.get(url, timeout=5)
                elif request_type == "PATCH":
                    response = requests.patch(url, json=payload, timeout=5)
                
                response.raise_for_status()
                response_data = response.json() if request_type == "GET" and response.content else None
                self.response_queue.put(("success", request_type, response_data, original_data))

            except requests.exceptions.RequestException as e:
                self.response_queue.put(("error", request_type, e, original_data))
            except Exception as e: # JSON decode hatası gibi diğer hatalar için
                self.response_queue.put(("error", request_type, e, original_data))
            finally:
                self.request_queue.task_done()

    def process_network_responses(self):
        """Cevap kuyruğunu kontrol eder ve sonuçları ana UI thread'inde işler."""
        try:
            while not self.response_queue.empty():
                status, request_type, data, original_data = self.response_queue.get_nowait()

                if status == "success":
                    self.set_online_status(True)
                    if request_type == "GET":
                        self.handle_firebase_poll_response(data)
                    elif request_type == "PATCH":
                        self.handle_firebase_sync_response(original_data)
                else: # status == "error"
                    logging.error(f"Ağ isteği başarısız ({request_type}): {data}")
                    self.set_online_status(False)

        except queue.Empty:
            pass
        finally:
            self.root.after(200, self.process_network_responses) # Kuyruğu periyodik olarak kontrol et

    def handle_firebase_poll_response(self, data):
        """Firebase'den gelen başarılı bir GET cevabını işler."""
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
        """Firebase'e gönderilen başarılı bir PATCH cevabını işler."""
        logging.info("Firebase senkronizasyonu başarılı.")
        # Eğer bu başarılı istek bir "unlock" isteği ise, manuel override bayrağını sıfırla.
        if original_data and not original_data.get('is_locked'):
            logging.info("Manuel override bayrağı sıfırlandı.")
            self.manual_override = False

    def load_assets_and_start(self):
        if os.path.exists("background.gif"):
            try:
                gif_obj = Image.open("background.gif")
                sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
                self.bg_frames = []
                for i, frame in enumerate(ImageSequence.Iterator(gif_obj)):
                    # Optimizasyon: Her 10 kareden birini alarak hafıza kullanımını azalt
                    if i % 10 == 0: 
                        # Daha kaliteli büyütme/küçültme için LANCZOS kullanıldı
                        resized = frame.copy().convert('RGBA').resize((sw, sh), Image.Resampling.LANCZOS)
                        self.bg_frames.append(ImageTk.PhotoImage(resized))
            except Exception as e:
                logging.error(f"background.gif yüklenemedi: {e}")
                self.bg_frames = [] # Hata durumunda listenin boş olduğundan emin ol

        self.loading_label.destroy()
        self.setup_ui(lock_mode=True)
        
        # Arka plan thread'ini ve ana döngüleri başlat
        self.start_network_thread()
        self.process_network_responses()
        self.poll_firebase()
        self.local_countdown()

    def setup_ui(self, lock_mode=True):
        # Eğer durum zaten aynıysa ve arayüz çizilmişse, gereksiz yere yeniden çizmeyi önle
        if self.is_locked_state == lock_mode and self.root.winfo_children():
            return

        self.is_locked_state = lock_mode

        for widget in self.root.winfo_children():
            widget.destroy()

        status_light_bg = "black"

        if lock_mode:
            # --- KİLİTLİ MOD (SİYAH EKRAN) ---
            self.root.attributes("-fullscreen", True)
            self.root.attributes("-topmost", True)
            self.root.overrideredirect(True)
            self.root.config(bg="black")

            if self.bg_frames:
                self.bg_label = tk.Label(self.root, bd=0)
                self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                self.animate_background(0)
            else:
                self.bg_label = None

            tk.Label(self.root, text="FORZA HORIZON 5\nSPEED POINT", fg="#FFD700", bg="black", font=("Arial", 60, "bold")).place(relx=0.5, rely=0.5, anchor="center")
            status_light_font, status_light_relx, status_light_rely, status_light_anchor = (("Arial", 24), 0.98, 0.98, "se")
        else:
            # --- HUD (AÇIK) MODU ---
            self.root.overrideredirect(True)
            self.root.attributes("-fullscreen", False)
            self.root.geometry("250x70+30+30") # HUD pozisyonu
            self.root.attributes("-alpha", 0.9)
            status_light_bg = "#0F0F0F"
            self.root.config(bg=status_light_bg)
            self.timer_label = tk.Label(self.root, text="Süre: --:--", fg="#FFD700", bg=status_light_bg, font=("Arial", 22, "bold"))
            self.timer_label.place(relx=0.4, rely=0.5, anchor="center")
            status_light_font, status_light_relx, status_light_rely, status_light_anchor = (("Arial", 18), 0.9, 0.5, "center")
            self.bg_label = None # HUD modunda animasyonlu arkaplan yok

        # Ortak olan status_light elemanını burada oluştur
        self.status_light = tk.Label(self.root, text="●", font=status_light_font, bg=status_light_bg, bd=0)
        self.status_light.place(relx=status_light_relx, rely=status_light_rely, anchor=status_light_anchor)
        self.refresh_light_color()

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
            try: # Pencere kapatılırsa veya resim yoksa oluşabilecek hataları yakala
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
            self.close_admin_panel() # Önce eski paneli kapat
            self.show_admin_time_selection() # Yeni paneli aç
        else:
            # Hatalı şifre durumunda paneli kapatmak yerine geçici bir uyarı göster
            if hasattr(self, 'pin_error_label') and self.pin_error_label.winfo_exists():
                return # Zaten bir hata mesajı gösteriliyor
            self.pin_error_label = tk.Label(self.admin_frame, text="Hatalı Şifre!", fg="#F04747", bg="#2C2F33")
            self.pin_error_label.pack()
            self.pin_entry.delete(0, tk.END)
            self.pin_error_label.after(2000, self.pin_error_label.destroy)

    def show_admin_time_selection(self):
        """Yönetici şifresi doğru girildikten sonra süre seçme panelini gösterir."""
        self.admin_frame = tk.Frame(self.root, bg="#2C2F33", bd=5, relief="ridge", padx=20, pady=20)
        self.admin_frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(self.admin_frame, text="Masa Aç (Offline)", fg="#43B581", bg="#2C2F33", font=("Arial", 16, "bold")).pack(pady=10)
        
        times = [(15, "15 Dakika"), (30, "30 Dakika"), (60, "1 Saat"), (120, "2 Saat")]
        for mins, text in times:
            tk.Button(self.admin_frame, text=text, width=20, bg="#7289DA", fg="white", font=("Arial", 12), command=lambda m=mins: self.start_offline_session(m)).pack(pady=5)
        tk.Button(self.admin_frame, text="Vazgeç", command=self.close_admin_panel).pack(pady=10)

    def start_offline_session(self, minutes):
        logging.info(f"Offline oturum başlatılıyor: {minutes} dakika.")
        self.local_remaining_time = minutes * 60
        self.manual_override = True 
        self.close_admin_panel()
        self.setup_ui(lock_mode=False)
        self.sync_to_firebase(is_locked=False, remaining_time=self.local_remaining_time)

    def close_admin_panel(self):
        if self.admin_frame:
            self.admin_frame.destroy()
            self.admin_frame = None

    # --- 1. MOTOR: İNTERNETTEN KOMUT BEKLEYİCİ ---
    def poll_firebase(self):
        # Kuyruğa birden fazla anlamsız sorgu eklemeyi önle
        if self.request_queue.empty():
            logging.info("Firebase sorgusu kuyruğa eklendi.")
            # GET isteğini kuyruğa koy
            self.request_queue.put(("GET", FIRESTORE_URL, None, None))

        # Periyodik olarak bu fonksiyonu tekrar çağır
        if self.root: self.root.after(3000, self.poll_firebase)

    # --- 2. MOTOR: LOKAL KRONOMETRE & OTOMATİK KİLİTLEME ---
    def local_countdown(self):
        if not self.is_locked_state and self.local_remaining_time > 0:
            self.local_remaining_time -= 1
            
            # HUD Güncelleme
            if self.timer_label and self.timer_label.winfo_exists():
                mins, secs = divmod(self.local_remaining_time, 60)
                self.timer_label.config(text=f"Süre: {mins:02d}:{secs:02d}")
            
            # 🕒 Akıllı Senkronizasyon (10 Saniyede Bir)
            if self.local_remaining_time % 10 == 0 and self.local_remaining_time > 0:
                self.sync_to_firebase(is_locked=False, remaining_time=self.local_remaining_time)
            
            # 🚨 SÜRE BİTTİ (KİLİTLEME)
            if self.local_remaining_time <= 0:
                logging.info("Süre doldu! Ekran kilitleniyor.")
                self.setup_ui(lock_mode=True)
                self.sync_to_firebase(is_locked=True, remaining_time=0)

        if self.root: self.root.after(1000, self.local_countdown)

    # --- 3. MOTOR: VERİTABANINA YAZMA ---
    def sync_to_firebase(self, is_locked, remaining_time):
        logging.info(f"Firebase senkronizasyon isteği kuyruğa eklendi: is_locked={is_locked}, time={remaining_time}")
        patch_url = f"{FIRESTORE_URL}?updateMask.fieldPaths=isLocked&updateMask.fieldPaths=remainingTime"
        payload = {
            "fields": {
                "isLocked": {"booleanValue": is_locked},
                "remainingTime": {"integerValue": str(remaining_time)}
            }
        }
        # `manual_override` bayrağını doğru yönetebilmek için orijinal isteğin bilgisini de gönderiyoruz.
        original_data = {'is_locked': is_locked}
        # PATCH isteğini kuyruğa koy
        self.request_queue.put(("PATCH", patch_url, payload, original_data))

if __name__ == "__main__":
    agent = SpeedPointAgent()
    agent.start_app()