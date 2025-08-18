#!/usr/bin/env python3
"""
sensor.py - Tracks perf events for system and cgroup using libpfm4
"""

import ctypes
import os
import time
import json

# Paths & defaults
LIBPFM4_PATH = "/usr/lib/libpfm.so.4"   # Adjust if needed
OUTPUT_FILE = "/usr/local/bin/powerdaemon/measurement.json"

# Cgroup path (to be read from config.yaml)
CGROUP_PATH = "/sys/fs/cgroup/sensor"

class PerfSensor:
    """
    PerfSensor: Tracks system and cgroup counters in parallel.
    """
    def __init__(self, interval_sec=1.0, cgroup_path=CGROUP_PATH, output_file=OUTPUT_FILE):
        self.interval = interval_sec
        self.cgroup_path = cgroup_path
        self.output_file = output_file
        self.lib = ctypes.CDLL(LIBPFM4_PATH)

        # Initialize libpfm4
        if self.lib.pfm_initialize() != 0:
            raise RuntimeError("libpfm4 initialization failed")

        # Define minimal pfm_event_info structure
        class pfm_event_info(ctypes.Structure):
            _fields_ = [
                ("name", ctypes.c_char_p),
                ("desc", ctypes.c_char_p),
                ("pme_type", ctypes.c_uint)
            ]
        self.pfm_event_info = pfm_event_info

        # Prepare system and cgroup event lists
        self.system_events = []
        self.cgroup_events = []

        self._collect_events()

    def _collect_events(self):
        """
        Collect events via libpfm4 and assign system and cgroup lists.
        """
        count = self.lib.pfm_get_event_count()
        info = self.pfm_event_info()

        for idx in range(count):
            if self.lib.pfm_get_event_info(ctypes.c_int(idx), ctypes.byref(info)) != 0:
                continue
            name = info.name.decode() if info.name else f"event_{idx}"
            event_type = "cpu_core" if info.pme_type == 0 else f"pmu_type_{info.pme_type}"
            key = f"{event_type}/{name}/"
            # Add all events to both system and cgroup lists for now
            self.system_events.append(key)
            self.cgroup_events.append(key)

        print(f"[*] Collected {len(self.system_events)} events for system and cgroup")

    def _open_counter(self, event_name, pid=-1, cgroup_fd=-1):
        """
        Placeholder for opening perf_event via perf_event_open.
        Currently this is a stub: you can later implement using ctypes
        and perf_event_attr struct to read the counters.
        """
        # For simplicity, we won't implement perf_event_open directly now
        # Instead, you can use libpfm4 to get encoding and perf counters via subprocess if needed
        return event_name  # just a placeholder

    def read_counters(self):
        """
        Reads system and cgroup counters at each interval.
        """
        results = []

        # Example loop for tracking
        while True:
            timestamp = time.time()
            system_values = {}
            cgroup_values = {}

            # Fake reading values for demonstration
            for ev in self.system_events:
                system_values[ev] = 0  # replace with actual counter read
            for ev in self.cgroup_events:
                cgroup_values[ev] = 0  # replace with actual counter read

            results.append({
                "timestamp": timestamp,
                "system": system_values,
                "cgroup": cgroup_values
            })

            # Write incremental JSON output
            with open(self.output_file, "w") as f:
                json.dump(results, f, indent=2)

            time.sleep(self.interval)

    def stop(self):
        """
        Cleanup if needed.
        """
        self.lib.pfm_terminate()
