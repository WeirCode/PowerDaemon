import subprocess
import argparse
import json
def parse_args():
    parser = argparse.ArgumentParser(description="Perf Data Collector")
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Subcommand: init
    parser_init = subparsers.add_parser('init', help='Save available perf events')

    # Subcommand: run
    parser_run = subparsers.add_parser('run', help='Run perf data collection')
    parser_run.add_argument("-cgroup", type=str, default="", help="Cgroup name or path")
    parser_run.add_argument("-detail", type=int, choices=range(0, 5), required=True,
                            help="Detail level (0–4)")

    return parser.parse_args()


def init_event_list():
    result = subprocess.run(["perf", "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    events = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            parts = line.split()
            if len(parts) >= 1:
                event = parts[0].strip()
                if '/' in event or event.isalpha():  # crude filter
                    events.append(event)

    with open("events.json", "w") as f:
        json.dump(events, f, indent=2)

    print(f"Saved {len(events)} events to events.json")

def get_events_by_detail(detail):
    levels = {
        0: ["power/energy-pkg/"],
        1: ["power/energy-pkg/", "power/energy-cores/"],
        2: ["power/energy-pkg/", "power/energy-cores/", "instructions"],
        3: ["power/energy-pkg/", "power/energy-cores/", "instructions", "cycles"],
        4: ["power/energy-pkg/", "power/energy-cores/", "instructions", "cycles", "cache-misses"]
    }
    return levels.get(detail, [])

def run_perf(events, duration=5, cgroup_path=None):
    cmd = [
        "perf", "stat", "-I", "1000",
        "-e", ",".join(events)
    ]

    if cgroup_path:
        cmd += ["-G", cgroup_path]

    cmd += ["sleep", str(duration)]

    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    return result.stderr

def parse_and_save_csv(output_str, filename="perf_output.csv"):
    import csv

    lines = output_str.strip().split("\n")

    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["time_ms", "value", "unit", "event"])

        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 5 and parts[1] != '<not':
                try:
                    time_ms = float(parts[0])
                    value = parts[1].replace(",", "")
                    unit = parts[2]
                    event = parts[3]
                    writer.writerow([time_ms, value, unit, event])
                except ValueError:
                    continue

def main():
    args = parse_args()

    if args.command == "init":
        init_event_list()

    elif args.command == "run":
        events = get_events_by_detail(args.detail)
        print(f"Running with events: {events}")
        perf_output = run_perf(events, duration=5, cgroup_path=args.cgroup)
        parse_and_save_csv(perf_output)
        print("Data saved to perf_output.csv")

main()
