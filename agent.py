import tkinter as tk
from PIL import Image, ImageTk, ImageSequence
import os
import requests
import time

# --- AYARLAR ---
PROJECT_ID = "speedpoint-928e1"
MACHINE_ID = "PC_01"  # Diğer masalar için PC_02, PC_03 yapabilirsin
FIRESTORE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/machines/{MACHINE_ID}"

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

    def load_assets_and_start(self):
        if os.path.exists("background.gif"):
            try:
                gif_obj = Image.open("background.gif")
                sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
                self.bg_frames = []
                for i, frame in enumerate(ImageSequence.Iterator(gif_obj)):
                    if i % 10 == 0: 
                        resized = frame.copy().convert('RGBA').resize((sw, sh), Image.Resampling.NEAREST)
                        self.bg_frames.append(ImageTk.PhotoImage(resized))
            except: pass

        self.loading_label.destroy()
        self.setup_ui(lock_mode=True)
        
        self.poll_firebase()
        self.local_countdown()

    def setup_ui(self, lock_mode=True):
        self.is_locked_state = lock_mode
        self.timer_label = None 
        self.bg_label = None
        self.status_light = None

        for widget in self.root.winfo_children():
            widget.destroy()

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

            tk.Label(self.root, text="FORZA HORIZON 5\nSPEED POINT", fg="#FFD700", bg="black", font=("Arial", 60, "bold")).place(relx=0.5, rely=0.5, anchor="center")
            
            self.status_light = tk.Label(self.root, text="●", font=("Arial", 24), bg="black", bd=0)
            self.status_light.place(relx=0.98, rely=0.98, anchor="se")
        else:
            # --- HUD (AÇIK) MODU ---
            self.root.overrideredirect(True)
            self.root.attributes("-fullscreen", False)
            self.root.geometry("250x70+30+30") # HUD pozisyonu
            self.root.attributes("-alpha", 0.9)
            self.root.config(bg="#0F0F0F")
            
            self.timer_label = tk.Label(self.root, text="Süre: --:--", fg="#FFD700", bg="#0F0F0F", font=("Arial", 22, "bold"))
            self.timer_label.place(relx=0.4, rely=0.5, anchor="center")
            
            self.status_light = tk.Label(self.root, text="●", font=("Arial", 18), bg="#0F0F0F", bd=0)
            self.status_light.place(relx=0.9, rely=0.5, anchor="center")

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
            try:
                self.bg_label.configure(image=self.bg_frames[counter])
                self.root.after(60, self.animate_background, (counter + 1) % len(self.bg_frames))
            except: pass

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
            for widget in self.admin_frame.winfo_children(): widget.destroy()
            tk.Label(self.admin_frame, text="Masa Aç (Offline)", fg="#43B581", bg="#2C2F33", font=("Arial", 16, "bold")).pack(pady=10)
            
            times = [(15, "15 Dakika"), (30, "30 Dakika"), (60, "1 Saat"), (120, "2 Saat")]
            for mins, text in times:
                tk.Button(self.admin_frame, text=text, width=20, bg="#7289DA", fg="white", font=("Arial", 12), command=lambda m=mins: self.start_offline_session(m)).pack(pady=5)
            tk.Button(self.admin_frame, text="Vazgeç", command=self.close_admin_panel).pack(pady=10)
        else:
            tk.Label(self.admin_frame, text="Hatalı Şifre!", fg="#F04747", bg="#2C2F33").pack()
            self.root.after(1000, self.close_admin_panel)

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

    # --- 1. MOTOR: İNTERNETTEN KOMUT BEKLEYİCİ ---
    def poll_firebase(self):
        try:
            response = requests.get(FIRESTORE_URL, timeout=3)
            if response.status_code == 200:
                self.set_online_status(True)
                data = response.json()
                fields = data.get("fields", {})
                is_locked_db = fields.get("isLocked", {}).get("booleanValue", True)
                rem_time_db = int(fields.get("remainingTime", {}).get("integerValue", "0"))

                # DURUM: Kapalıyken Buluttan 'AÇ' Emri Gelirse
                if is_locked_db == False and self.is_locked_state == True:
                    self.local_remaining_time = rem_time_db 
                    self.setup_ui(lock_mode=False)
                
                # DURUM: Açıkken Buluttan 'KİLİTLE' Emri Gelirse (İptal Durumu)
                elif is_locked_db == True and self.is_locked_state == False:
                    if not self.manual_override: # Manuel açılmadıysa kilitle
                        self.local_remaining_time = 0
                        self.setup_ui(lock_mode=True)
            else:
                self.set_online_status(False)
        except:
            self.set_online_status(False)

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
                print("Süre doldu! Kilitleniyor...")
                self.setup_ui(lock_mode=True)
                self.sync_to_firebase(is_locked=True, remaining_time=0)

        if self.root: self.root.after(1000, self.local_countdown)

    # --- 3. MOTOR: VERİTABANINA YAZMA ---
    def sync_to_firebase(self, is_locked, remaining_time):
        patch_url = f"{FIRESTORE_URL}?updateMask.fieldPaths=isLocked&updateMask.fieldPaths=remainingTime"
        payload = {
            "fields": {
                "isLocked": {"booleanValue": is_locked},
                "remainingTime": {"integerValue": str(remaining_time)}
            }
        }
        try:
            response = requests.patch(patch_url, json=payload, timeout=3)
            if response.status_code == 200:
                self.set_online_status(True)
                if not is_locked: self.manual_override = False 
            else:
                self.set_online_status(False)
        except:
            self.set_online_status(False)

if __name__ == "__main__":
    agent = SpeedPointAgent()
    agent.start_app()