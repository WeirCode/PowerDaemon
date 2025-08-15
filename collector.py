import subprocess
import argparse
import json
import sys
import os
import matplotlib.pyplot as plt

from pathlib import Path

EVENTS_FILE = Path.home() / ".powersensor_events.json"

def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Collect perf events and pc info")
    
    run_parser = subparsers.add_parser("run", help="Run the power sensor.")
    run_parser.add_argument("cgroup", help="Path to the cgroup to monitor.")
    run_parser.add_argument("time", type=float, help="Time in seconds to monitor.")
    run_parser.add_argument("frequency", type=float, help="Sampling frequency (Hz).")
    run_parser.add_argument("detail", type=int, help="Detail level from init.")

    return parser.parse_args()

def validate_run_args(args):
    # Check numbers
    if args.time <= 0:
        sys.exit("Error: time must be > 0")
    if args.frequency <= 0:
        sys.exit("Error: frequency must be > 0")

    # Load events file for detail validation
    if not EVENTS_FILE.exists():
        sys.exit("Error: no events file found, run 'init' first.")
    with open(EVENTS_FILE) as f:
        events_data = json.load(f)
    max_detail = max(events_data.keys(), key=int)
    if not (0 <= args.detail <= int(max_detail)):
        sys.exit(f"Error: detail must be between 0 and {max_detail}")

    # Check cgroup exists
    if not os.path.exists(args.cgroup):
        sys.exit(f"Error: cgroup '{args.cgroup}' does not exist.")


def init_events():
    print("[*] Running 'perf list --json' to get available events...")
    result = subprocess.run(
        ["perf", "list", "--json", "pmu"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        sys.exit(f"Error: failed to run 'perf list --json'\n{result.stderr}")

    try:
        events_data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        sys.exit(f"Error parsing JSON from perf list: {e}")

    print(events_data)
    
    # Normalize to a flat list of groups
    if isinstance(events_data, dict):
        groups = []
        for section in events_data.values():
            if isinstance(section, list):
                groups.extend(section)
    elif isinstance(events_data, list):
        groups = events_data
    else:
        sys.exit("Unexpected JSON format from perf list")

    # Filter for power/ or msr/ events
    filtered_events = []
    for group in groups:
        for ev in group.get("event_list", []):
            name = ev.get("name", "")
            if name.startswith("power/") or name.startswith("msr/"):
                filtered_events.append(name)

    if not filtered_events:
        sys.exit("No power/ or msr/ events found from perf list.")

    # Assign detail levels (could be same if list is short)
    events_by_detail = {
        0: filtered_events[:3],   # low detail = fewer events
        1: filtered_events[:min(6, len(filtered_events))],
        2: filtered_events        # all
    }

    with open(EVENTS_FILE, "w") as f:
        json.dump(events_by_detail, f, indent=2)

    print(f"[*] Saved {len(filtered_events)} power/msr events into {EVENTS_FILE}")



def run_monitor(args):
    validate_run_args(args)
    with open(EVENTS_FILE) as f:
        events_data = json.load(f)
    events = events_data[str(args.detail)] if str(args.detail) in events_data else events_data[args.detail]

    # Build perf stat commands
    time_arg = str(args.time)
    events_arg = ",".join(events)

    sys_cmd = ["perf", "stat", "-a", "-e", events_arg, "sleep", time_arg]
    cg_cmd = ["perf", "stat", "-G", args.cgroup, "-e", events_arg, "sleep", time_arg]

    print("[*] Running system-wide perf stat...")
    sys_out = subprocess.run(sys_cmd, capture_output=True, text=True)
    print("[*] Running cgroup perf stat...")
    cg_out = subprocess.run(cg_cmd, capture_output=True, text=True)

    # Parse outputs into dict {event: value}
    sys_results = parse_perf_output(sys_out.stderr)
    cg_results = parse_perf_output(cg_out.stderr)

    # Graph
    plot_comparison(sys_results, cg_results)

def parse_perf_output(output):
    results = {}
    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].replace(",", "").isdigit():
            val = int(parts[0].replace(",", ""))
            event_name = parts[1]
            results[event_name] = val
    return results

def plot_comparison(sys_data, cg_data):
    events = list(sys_data.keys())
    sys_vals = [sys_data[e] for e in events]
    cg_vals = [cg_data.get(e, 0) for e in events]

    x = range(len(events))
    plt.bar(x, sys_vals, width=0.4, label="System", align="center")
    plt.bar([i + 0.4 for i in x], cg_vals, width=0.4, label="Cgroup", align="center")
    plt.xticks([i + 0.2 for i in x], events, rotation=90)
    plt.ylabel("Count")
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    args = parse_args()
    if args.command == "init":
        init_events()
    elif args.command == "run":
        run_monitor(args)

if __name__ == "__main__":
    main()

