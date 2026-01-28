import os
import csv
import time
import glob
import logging
from datetime import datetime
from pathlib import Path

# Professional Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

class PowerStationLogger:
    def __init__(self, filename="battery_master_log.csv"):                                                                                      
        self.filename = filename
        self.bat_path = self._discover_battery()
        self.thermal_zone = self._discover_thermal()
        self.last_status = None
        self.fields = [
            "timestamp", "pct", "status", "voltage_v", "current_a", 
            "power_w", "temp_c", "energy_wh", "energy_full_wh", 
            "energy_design_wh", "cycles", "charge_rate_w"
        ]
        self._init_csv()

    def _discover_battery(self):
        paths = glob.glob("/sys/class/power_supply/BAT*")
        if not paths:
            raise RuntimeError("No Battery Hardware Detected.")
        logging.info(f"Connected to: {paths[0]}")
        return Path(paths[0])

    def _discover_thermal(self):
        """Advanced thermal discovery: hunts for battery or package temp."""
        # Priority 1: Battery internal temp
        if (self.bat_path / "temp").exists():
            return self.bat_path / "temp"
        
        # Priority 2: Specific thermal zones
        zones = glob.glob("/sys/class/thermal/thermal_zone*")
        for zone in zones:
            try:
                type_path = Path(zone) / "type"
                z_type = open(type_path).read().strip().lower()
                # Looking for battery-related or generic package temp
                if any(x in z_type for x in ["bat", "pkg", "acpi", "intel"]):
                    logging.info(f"Thermal source: {z_type} ({zone})")
                    return Path(zone) / "temp"
            except: continue
        return None

    def _read_sysfs(self, node, scale=1.0):
        try:
            path = self.bat_path / node
            if path.exists():
                return float(path.read_text().strip()) / scale
        except Exception:
            return 0.0
        return 0.0

    def _init_csv(self):
        if not os.path.exists(self.filename):
            with open(self.filename, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                writer.writeheader()

    def capture_telemetry(self):
        """Reads and calculates advanced metrics."""
        # Basic Units
        volts = self._read_sysfs("voltage_now", 1e6)
        amps = self._read_sysfs("current_now", 1e6)
        
        # Power can be read directly or calculated (P = V * I)
        power = self._read_sysfs("power_now", 1e6)
        if power == 0 and (volts * amps) != 0:
            power = volts * amps

        # Temperature scaling logic
        temp_raw = 0.0
        if self.thermal_zone:
            temp_raw = float(self.thermal_zone.read_text().strip())
            temp_raw = temp_raw / 1000.0 if temp_raw > 1000 else temp_raw / 10.0

        status = (self.bat_path / "status").read_text().strip()
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "pct": int(self._read_sysfs("capacity")),
            "status": status,
            "voltage_v": round(volts, 3),
            "current_a": round(amps, 3),
            "power_w": round(power, 2),
            "temp_c": round(temp_raw, 1),
            "energy_wh": self._read_sysfs("energy_now", 1e6),
            "energy_full_wh": self._read_val_fallback(["energy_full", "charge_full"], 1e6),
            "energy_design_wh": self._read_val_fallback(["energy_full_design", "charge_full_design"], 1e6),
            "cycles": int(self._read_sysfs("cycle_count")),
            "charge_rate_w": round(volts * amps, 2) if status == "Charging" else round(-(volts * amps), 2)
        }
        return data

    def _read_val_fallback(self, nodes, scale):
        """Try multiple nodes because Linux kernels vary naming conventions."""
        for node in nodes:
            val = self._read_sysfs(node, scale)
            if val > 0: return val
        return 0.0

    def run(self):
        logging.info("BMS Logger Engaged. Entering Adaptive Loop...")
        try:
            with open(self.filename, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                
                while True:
                    data = self.capture_telemetry()
                    writer.writerow(data)
                    f.flush() # Ensure data is written to disk

                    # --- Adaptive Sleep Logic ---
                    # Log faster if: Status changed OR High Power Draw (>15W)
                    if data['status'] != self.last_status or abs(data['power_w']) > 15:
                        sleep_time = 2  # High-res mode
                        self.last_status = data['status']
                    else:
                        sleep_time = 10 # Economy mode
                    
                    print(f"\r[Telemetry] {data['pct']}% | {data['power_w']}W | {data['temp_c']}°C | Mode: {'High-Res' if sleep_time==2 else 'Std'}", end="")
                    
                    time.sleep(sleep_time)
        except KeyboardInterrupt:
            logging.info("\nShutdown signal received. Finalizing logs...")

if __name__ == "__main__":
    logger = PowerStationLogger()
    logger.run()