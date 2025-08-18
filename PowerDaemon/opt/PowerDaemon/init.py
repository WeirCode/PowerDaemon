#!/usr/bin/env python3
"""
init.py - Initializes PowerDaemon by collecting available perf events
using libpfm4 (Performance Monitoring library) via ctypes instead of subprocess.
"""

import ctypes
import json
import os
import sys

# Default JSON output
PC_INFO_FILE = "/usr/local/bin/powerdaemon/pc_info.json"

# Path to libpfm4 shared library (adjust if needed)
LIBPFM4_PATH = "/usr/lib/libpfm.so.4"

# Constants from libpfm4
PFM_PMU_TYPE_NONE = 0

class PerfInitializer:
    """
    Initializes perf events using libpfm4 and saves them to JSON.
    """
    def __init__(self, output_file=PC_INFO_FILE):
        self.pc_info_file = output_file
        os.makedirs(os.path.dirname(self.pc_info_file), exist_ok=True)

        # Load libpfm4
        try:
            self.lib = ctypes.CDLL(LIBPFM4_PATH)
        except OSError as e:
            raise RuntimeError(f"Failed to load libpfm4: {e}")

        # Initialize libpfm4
        if self.lib.pfm_initialize() != 0:
            raise RuntimeError("libpfm4 initialization failed")

        # Define basic ctypes structures
        # pfm_get_event_count returns int
        self.lib.pfm_get_event_count.restype = ctypes.c_int
        # pfm_get_event_info takes int and pointer to pfm_event_info struct
        # We'll define pfm_event_info partially for Name, Type, Unit
        class pfm_event_info(ctypes.Structure):
            _fields_ = [
                ("name", ctypes.c_char_p),
                ("desc", ctypes.c_char_p),
                ("pme_type", ctypes.c_uint)
            ]
        self.pfm_event_info = pfm_event_info

    def collect_perf_events(self):
        """
        Collect all available perf events and write to JSON file.
        """
        event_count = self.lib.pfm_get_event_count()
        print(f"[*] Found {event_count} PMU events via libpfm4")

        events = {}

        # Prepare a pfm_event_info struct
        info = self.pfm_event_info()

        for idx in range(event_count):
            # pfm_get_event_info(idx, info) returns 0 on success
            ret = self.lib.pfm_get_event_info(ctypes.c_int(idx), ctypes.byref(info))
            if ret != 0:
                continue  # skip if failed

            name = info.name.decode() if info.name else f"event_{idx}"
            desc = info.desc.decode() if info.desc else ""
            event_type = "cpu_core" if info.pme_type == 0 else f"pmu_type_{info.pme_type}"

            key = f"{event_type}/{name}/"
            events[key] = {
                "Name": key,
                "Type": event_type,
                "Description": desc
            }

        # Save events into both system and group lists
        events_by_category = {
            "system": list(events.values()),
            "group": list(events.values())
        }

        # Write JSON
        with open(self.pc_info_file, "w") as f:
            json.dump(events_by_category, f, indent=2)

        print(f"[*] Saved {len(events)} perf events to {self.pc_info_file}")

        # Terminate libpfm4
        self.lib.pfm_terminate()

    def is_pc_info_populated(self):
        """
        Quick check if JSON file exists and has events.
        """
        if not os.path.exists(self.pc_info_file):
            return False

        try:
            with open(self.pc_info_file) as f:
                data = json.load(f)
                if data.get("system") or data.get("group"):
                    return True
        except Exception:
            return False

        return False

