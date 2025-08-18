#!/usr/bin/env python3
"""
daemon.py - Main PowerDaemon process
Watches a cgroup and starts/stops the sensor automatically
"""

import signal
import time
import yaml
import os
from threading import Thread

from watch_cgroup import CgroupWatcher
from sensor import PerfSensor
from init import PerfInitializer  # your class from init.py

# Globals for clean shutdown
running = True
sensor_thread = None
sensor_instance = None

def load_config(config_file="config.yaml"):
    """
    Loads YAML configuration for the daemon
    """
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"{config_file} not found")

    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Defaults
    cgroup = config.get("cgroup", "/sys/fs/cgroup/sensor")
    interval = config.get("interval", 1.0)
    output_file = config.get("output_file", "/usr/local/bin/powerdaemon/measurement.json")

    return cgroup, interval, output_file

def start_sensor(interval, output_file):
    """
    Starts the PerfSensor in a separate thread
    """
    global sensor_instance
    sensor_instance = PerfSensor(interval_sec=interval, output_file=output_file)

    def run_sensor():
        sensor_instance.read_counters()

    t = Thread(target=run_sensor, daemon=True)
    t.start()
    return t

def stop_sensor():
    """
    Stops the PerfSensor if running
    """
    global sensor_instance
    if sensor_instance:
        sensor_instance.stop()
        sensor_instance = None

def signal_handler(sig, frame):
    """
    Catch signals to cleanly shutdown daemon
    """
    global running
    running = False
    print("[*] Shutting down daemon...")
    stop_sensor()
    exit(0)

def main():
    global running, sensor_thread

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Load config
    cgroup_path, interval, output_file = load_config()

    # Check for pc_info.json, run init if missing
    if not os.path.exists("pc_info.json"):
        print("[*] pc_info.json not found, running init...")
        init_obj = PerfInitializer()
        init_obj.run()  # or whatever method populates pc_info.json

    print(f"[*] Monitoring cgroup: {cgroup_path} with interval {interval}s")

    watcher = CgroupWatcher(cgroup_path)
    sensor_active = False

    while running:
        events = watcher.check_events(timeout=1)
        cgroup_empty = watcher.is_empty()

        if not cgroup_empty and not sensor_active:
            print("[*] PID detected, starting sensor...")
            sensor_thread = start_sensor(interval, output_file)
            sensor_active = True
        elif cgroup_empty and sensor_active:
            print("[*] Cgroup empty, stopping sensor...")
            stop_sensor()
            sensor_active = False

        time.sleep(0.1)

if __name__ == "__main__":
    main()
