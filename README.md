# Gira System 3000 Bluetooth to MQTT / Home Assistant Bridge 🚀

Dieses Repository enthält Skripte und Konfigurationen, um den **Gira System 3000 Bluetooth Bewegungsmelder (2,20 m Komfort BT, System 55)** per Protokoll-Analyse in Home Assistant einzubinden.

## 📖 Protokoll- und Signal-Analyse
Da Gira das Bluetooth-Protokoll des System 3000 nicht offenlegt, basiert diese Lösung auf der passiven Analyse (Sniffing) der Bluetooth Low Energy (BLE) Advertisements, die das Modul aussendet.

*   **Hersteller-ID:** `1412` (Gira Giersiepen GmbH & Co. KG / `0x0584` in hex)
*   **Idle-Heartbeat:** Der Bewegungsmelder wechselt im Normalzustand (mains-powered 230V) im Sekundentakt zwischen zwei Signal-Paketen:
    *   `...f3100100`
    *   `...f8100100` (wichtig ist das letzte Byte: `00` steht für **AUS / Keine Bewegung**)
*   **Aktiv-Signal:** Sobald Bewegung erkannt wird (und ggf. das Licht schaltet), wechselt das Signal auf:
    *   `...f8100101` (wichtig ist das letzte Byte: `01` steht für **AN / Bewegung erkannt**)

Da der Melder den Zustand aktiv und verzögerungsfrei über die BLE-Pakete sendet, kann der Status in nahezu Echtzeit (1–2 Sekunden) erfasst werden.

---

## 🛠️ Lösung A: Raspberry Pi / Linux Gateway (Python & MQTT)

Diese Lösung führt einen Python-Hintergrunddienst auf einem Linux-System (z. B. Raspberry Pi 4) aus, der die BLE-Pakete scannt und den Status über MQTT an Home Assistant weitergibt.

### 1. Installation auf dem Pi
Installiere die benötigten Systempakete:
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv bluez
```

Erstelle eine virtuelle Umgebung und installiere die Python-Bibliotheken:
```bash
mkdir -p ~/gira_ble_bridge
cd ~/gira_ble_bridge
python3 -m venv venv
./venv/bin/pip install bleak paho-mqtt
```

### 2. Konfiguration
Kopiere [gira_mqtt_bridge.py](gira_mqtt_bridge.py) und [config.json.example](config.json.example) in das Verzeichnis.
Benenne die Konfigurationsdatei um:
```bash
mv config.json.example config.json
```
Trage deine Zugangsdaten und die MAC-Adresse deines Gira-Bewegungsmelders in die `config.json` ein.

### 3. Autostart einrichten (systemd)
Kopiere die [gira-bridge.service](gira-bridge.service) nach `/etc/systemd/system/` (passe ggf. deinen Benutzernamen im Pfad an) und starte den Dienst:
```bash
sudo cp gira-bridge.service /etc/systemd/system/gira-bridge.service
sudo systemctl daemon-reload
sudo systemctl enable gira-bridge.service
sudo systemctl start gira-bridge.service
```

Die Entität wird in Home Assistant automatisch via **MQTT Auto-Discovery** als `binary_sensor.gira_bewegungsmelder` angelegt.

---

## 🔌 Lösung B: ESP32 / ESPHome Gateway (Die stromsparende Alternative)

Wenn der Raspberry Pi 4 zu groß oder zu stromhungrig für diese einfache Aufgabe ist, kannst du einen günstigen **ESP32** (z. B. NodeMCU, ESP32-C3 oder ESP32-S3) verwenden. Dank ESPHome erfolgt die Integration direkt über die Home Assistant API, ganz ohne MQTT-Umweg.

1.  Füge in deinem ESPHome-Dashboard ein neues Gerät hinzu.
2.  Nutze die Konfigurationsvorlage aus [esphome_gira.yaml](esphome_gira.yaml).
3.  Ersetze `DEIN_WLAN_NAME`, `DEIN_WLAN_PASSWORT` sowie die `mac_address` deines Gira-Aufsatzes (wichtig: in ESPHome in **Kleinbuchstaben** schreiben).
4.  Flashe den ESP32. Das Gerät wird direkt in Home Assistant als Integration erkannt und stellt den Binärsensor zur Verfügung.

---

## 🔒 Sicherheitshinweis & gitignore
In diesem Repository sind **keine echten Passwörter, IP-Adressen oder MAC-Adressen** hinterlegt. 

Damit dir das auch nicht versehentlich passiert, ist die `config.json` bereits in der `.gitignore` eingetragen. Achte bei der ESPHome-Konfiguration darauf, deine echten WLAN-Daten vor einem Push zu entfernen.
