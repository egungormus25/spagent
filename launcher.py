import requests
import os
import subprocess
import sys
import time
import re

# --- AYARLAR ---
# GitHub Gist veya kendi sunucundaki "Raw" dosya linki
UPDATE_URL = "https://raw.githubusercontent.com/kullanici_adin/repo_adin/main/agent.py"
LOCAL_FILE = "agent.py"
VERSION_FILE = "version.txt" # Not: Bu dosya şu anki yapıda kullanılmıyor.

def get_remote_version():
    """İnternetteki kodun içindeki versiyonu kontrol eder."""
    try:
        response = requests.get(UPDATE_URL, timeout=10)
        response.raise_for_status()  # 4xx veya 5xx gibi hatalı durum kodlarında exception fırlatır.
        content = response.text
        # Versiyonu bulmak için daha güvenilir bir yöntem olan regex kullanılıyor.
        match = re.search(r'VERSION\s*=\s*["\'](.*?)["\']', content)
        if match:
            return match.group(1), content
    except requests.exceptions.RequestException as e:
        print(f"Güncelleme sunucusuna ulaşılamadı: {e}")
    return None, None

def get_local_version():
    """Bilgisayardaki mevcut kodun versiyonunu okur."""
    if not os.path.exists(LOCAL_FILE):
        return "0.0.0"
    try:
        with open(LOCAL_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            # Versiyonu bulmak için daha güvenilir bir yöntem olan regex kullanılıyor.
            match = re.search(r'VERSION\s*=\s*["\'](.*?)["\']', content)
            if match:
                return match.group(1)
    except IOError as e:
        print(f"Lokal agent dosyası okunamadı: {e}")
    return "0.0.0"

def update_and_launch():
    print("--- SpeedPoint Launcher Başlatıldı ---")
    
    print("Versiyon kontrol ediliyor...")
    local_v = get_local_version()
    remote_v, remote_code = get_remote_version()
    
    if remote_v:
        print(f"Lokal Versiyon: {local_v}, Uzak Versiyon: {remote_v}")
        if remote_v != local_v:
            print(f"Yeni versiyon bulundu: {remote_v}")
            print("Güncelleniyor...")
            try:
                with open(LOCAL_FILE, "w", encoding="utf-8") as f:
                    f.write(remote_code)
                print("Güncelleme başarılı!")
                local_v = remote_v # Lokal versiyon bilgisini de güncelleyelim.
            except IOError as e:
                print(f"Güncelleme hatası: Dosya yazılamadı. {e}")
                print("Mevcut versiyon ile devam ediliyor.")
        else:
            print("Sistem güncel.")
    else:
        print("Uzak versiyon kontrol edilemedi. Mevcut versiyon ile devam ediliyor.")

    if not os.path.exists(LOCAL_FILE):
        print(f"HATA: {LOCAL_FILE} dosyası bulunamadı. Başlatma işlemi iptal edildi.")
        return

    print(f"Versiyon {local_v} başlatılıyor...")
    try:
        # check=True, agent script'i hata ile kapanırsa bir exception fırlatır.
        subprocess.run([sys.executable, LOCAL_FILE], check=True)
    except FileNotFoundError:
        print(f"Hata: Python yorumlayıcısı ({sys.executable}) veya agent dosyası ({LOCAL_FILE}) bulunamadı.")
    except subprocess.CalledProcessError as e:
        print(f"Agent işlemi bir hata ile sonlandı (çıkış kodu {e.returncode}).")
    except Exception as e:
        print(f"Agent başlatılırken beklenmedik bir hata oluştu: {e}")

if __name__ == "__main__":
    while True:
        update_and_launch()
        print("Agent işlemi durdu. 5 saniye sonra yeniden başlatılacak...")
        time.sleep(5)