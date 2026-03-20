import requests
import json

URL = "https://firestore.googleapis.com/v1/projects/speedpoint-928e1/databases/(default)/documents/machines/PC_01"

print("📡 Veri sorgulanıyor...")
try:
    r = requests.get(URL, timeout=5)
    data = r.json()
    if "fields" in data:
        print("✅ Döküman Bulundu!")
        print("--- GELEN HAM VERİ ---")
        print(json.dumps(data["fields"], indent=2)) # Ham veriyi gör kanka
        
        fields = data["fields"]
        is_locked = fields.get("isLocked", {}).get("booleanValue", "BULUNAMADI")
        print(f"\n👉 isLocked Değeri: {is_locked}")
    else:
        print(f"❌ Döküman içeriği boş veya hatalı! Response: {data}")
except Exception as e:
    print(f"💥 Bağlantı Hatası: {e}")