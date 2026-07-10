import asyncio
import json
import logging
import os
import sys
import time
import paho.mqtt.client as mqtt
from bleak import BleakScanner

# Konfigurationsverzeichnis ermitteln
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Konfiguration laden
if not os.path.exists(CONFIG_PATH):
    logging.error(f"Konfigurationsdatei nicht gefunden unter {CONFIG_PATH}!")
    logging.error("Bitte erstelle 'config.json' basierend auf 'config.json.example'.")
    sys.exit(1)

try:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
except Exception as e:
    logging.error(f"Fehler beim Lesen der config.json: {e}")
    sys.exit(1)

TARGET_MAC = config.get("target_mac", "").upper()
MQTT_HOST = config.get("mqtt_host")
MQTT_PORT = config.get("mqtt_port", 1883)
MQTT_USER = config.get("mqtt_user")
MQTT_PASSWORD = config.get("mqtt_password")

if not TARGET_MAC or not MQTT_HOST:
    logging.error("Ungültige Konfiguration in config.json! 'target_mac' und 'mqtt_host' müssen gesetzt sein.")
    sys.exit(1)

# Globaler Zustand
motion_detected = None
last_motion_time = 0.0
last_hex = None

# Initialisiere MQTT Client (für Paho MQTT v2)
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
if MQTT_USER and MQTT_PASSWORD:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

def publish_discovery():
    discovery_topic = "homeassistant/binary_sensor/gira_motion/config"
    discovery_payload = {
        "name": "Gira Bewegungsmelder",
        "state_topic": "gira/motion/state",
        "device_class": "motion",
        "unique_id": f"gira_motion_{TARGET_MAC.replace(':', '').lower()}",
        "device": {
            "identifiers": [f"gira_motion_{TARGET_MAC.replace(':', '').lower()}"],
            "name": "Gira Bewegungsmelder 2,2m",
            "model": "System 3000 BT",
            "manufacturer": "Gira"
        }
    }
    mqtt_client.publish(discovery_topic, json.dumps(discovery_payload), retain=True)
    logging.info("MQTT Discovery Konfiguration an Home Assistant gesendet.")

def detection_callback(device, advertising_data):
    global motion_detected, last_motion_time, last_hex
    if device.address.upper() == TARGET_MAC:
        m_data = advertising_data.manufacturer_data.get(1412) # Gira ID
        if m_data:
            current_hex = m_data.hex()
            
            # Logge Signal-Änderungen im systemd-Journal
            if current_hex != last_hex:
                logging.info(f"Signal: {current_hex} (RSSI: {advertising_data.rssi} dBm)")
                last_hex = current_hex
            
            # Bewegung erkannt / Licht AN (Endet auf f8100101)
            if current_hex.endswith("f8100101"):
                last_motion_time = time.time()
                if motion_detected is not True:
                    motion_detected = True
                    logging.info("--- STATUS-UPDATE: BEWEGUNG ERKANNT / LICHT AN ---")
                    mqtt_client.publish("gira/motion/state", "ON", retain=True)
            
            # Keine Bewegung / Licht AUS (Endet auf f8100100)
            elif current_hex.endswith("f8100100"):
                if motion_detected is not False:
                    motion_detected = False
                    logging.info("--- STATUS-UPDATE: KEINE BEWEGUNG / LICHT AUS ---")
                    mqtt_client.publish("gira/motion/state", "OFF", retain=True)

async def monitor_cooldown():
    global motion_detected, last_motion_time
    while True:
        await asyncio.sleep(1.0)
        # Sicherheits-Timeout (60 Sek), falls das OFF-Signal mal verpasst wird
        if motion_detected is True and (time.time() - last_motion_time > 60.0):
            motion_detected = False
            logging.info("Sicherheits-Timeout erreicht: KEINE BEWEGUNG")
            mqtt_client.publish("gira/motion/state", "OFF", retain=True)

async def main():
    logging.info(f"Verbinde zu MQTT Broker unter {MQTT_HOST}:{MQTT_PORT}...")
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    
    await asyncio.sleep(2)
    publish_discovery()
    
    logging.info(f"Starte BLE Scanner für {TARGET_MAC}...")
    scanner = BleakScanner(detection_callback)
    await scanner.start()
    
    await monitor_cooldown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Beende gira-mqtt-bridge.")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
