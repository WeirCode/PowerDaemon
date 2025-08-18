import subprocess
import argparse
import json
import sys
import os
import matplotlib.pyplot as plt
from itertools import zip_longest
import math

def parse_args():
    #ArgumentParser Class from Library
    parser = argparse.ArgumentParser()
    #subparser for main command
    subparsers = parser.add_subparsers(dest="command", required=True)
    #init subparser - parser contains sub_parsers which contain arguments
    subparsers.add_parser("init", help="Collect perf events and pc info")
    #run subparser
    run_parser = subparsers.add_parser("run", help="Run the power sensor")
    #arguments for run subparser
    run_parser.add_argument("cgroup", type=str, help="Path to the cgroup to monitor.")
    run_parser.add_argument("time", type=float, help="Time in seconds to monitor.")
    run_parser.add_argument("frequency", type=float, help="Sampling frequency (Hz).")
    run_parser.add_argument("detail", type=int, help="Detail level from init.")

    #return arguments
    return parser.parse_args()

def init_events():
    print("[*] Running 'perf list --json pmu'")
    result = subprocess.run(
        ["perf", "list", "--json", "pmu"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        sys.exit(f"Error: failed to run 'perf list --json'\n{result.stderr}")
    print("Parsing into a dictionary")
    try:
        events_data = json.loads(result.stdout.replace("\n",""))
    except json.JSONDecodeError as e:
        sys.exit(f"Error parsing JSON from perf list: {e}")
    
    event_dict = {}
    for event in events_data:
        unit = event.get("Unit")
        if unit == "cpu_core":
            name = f"cpu_core/{event.get("EventName")}/"
        else:
            name = event.get("EventName")
        encoding = event.get("Encoding")
        eventType = event.get("EventType", None)
        if name and encoding:
            event_dict[name] = {"Unit":unit, "Name":name, "Type":eventType, "Encoding":encoding}
    print("Creating Detail levels")
    # Assign detail levels (could be same if list is short)
    events_by_detail = {
        0:{"system":[], "group":[]},
        1:{"system":[], "group":[]}
    }
    for e in event_dict:
        if event_dict[e]["Unit"] == "power":
            events_by_detail[0]["system"].append(event_dict[e])
        elif event_dict[e]["Unit"] == "msr":
            events_by_detail[1]["system"].append(event_dict[e])
            events_by_detail[1]["group"].append(event_dict[e])
        elif event_dict[e]["Unit"] == "cpu_core" and event_dict[e]["Type"] and event_dict[e]["Type"] == "Kernel PMU event" and event_dict[e]["Unit"] in ["cpu_core", "cpu_atom"]:
            events_by_detail[1]["system"].append(event_dict[e])
            events_by_detail[1]["group"].append(event_dict[e])
            if event_dict[e]["Name"] == "cpu_core/instructions/":
                events_by_detail[0]["system"].append(event_dict[e])
                events_by_detail[0]["group"].append(event_dict[e])

    with open("pc_info.json", "w") as f:
        json.dump(events_by_detail, f, indent=2)

    print(f"[*] Saved events into file")

def validate_run_args(args):
    info_file = "pc_info.json"
    # Check numbers
    print("Checking args")
    print("Checking time,frequency > 0")
    if args.time <= 0:
        sys.exit("Error: time must be > 0")
    if args.frequency <= 100:
        sys.exit("Error: frequency must be > 100")

    print("Checking cgroup")
    # Check cgroup exists
    if args.cgroup != "":
        if not os.path.exists(f"/sys/fs/cgroup/{args.cgroup}"):
            sys.exit(f"Error: cgroup '{args.cgroup}' does not exist.")
    
    print("Checking if pc_info has been saved")
    try:
        with open(info_file) as f:
            print(f"file exists")
    except:
        sys.exit("Error: no info file found, run 'init' first.")
    
    if not (0 <= args.detail <= 2):
        sys.exit(f"Error: detail must be between 0 and 2")

def run_monitor(args):
    validate_run_args(args)

    print("collecting events to track")
    with open("pc_info.json") as f:
        events_data = json.load(f)

    print("Creating events list")
    sysevents = []
    groupevents = []
    for i in range(0, args.detail + 1):
        try:
            for j in events_data[str(i)]["system"]:
                sysevents.append(j["Name"])
            for x in events_data[str(i)]["group"]:
                groupevents.append(x["Name"])
        except:
            continue
    sysevents_arg = ",".join(sysevents)
    groupevents_arg = ",".join(groupevents)
    print(sysevents_arg)
    print(groupevents_arg)
    sevents = len(sysevents)
    cgevents = len(groupevents)
    # Interval in ms
    interval = int(args.frequency)  # e.g., 1000 for 1s
    time_arg = int(args.time)    # total run time (s)

    print("Running Perf")
    #Shell method
    #cmd = f"perf stat -I {interval} -e {sysevents_arg} -a -- perf stat -I {interval} -e {groupevents_arg} -a --for-each-cgroup {args.cgroup} sleep {time_arg}"
    #result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    #print(result.stderr)
    #parse_stat(result.stderr)
    
    results = []
    # parallel method
    syscmd = ["perf", "stat", "-I", str(interval), "-a", "-e", sysevents_arg, "sleep", str(time_arg)]
    # Cgroup
    if args.cgroup != "":
        groupcmd = ["perf", "stat", "-I", str(interval), "-e", groupevents_arg, "-a", "--for-each-cgroup", args.cgroup, "sleep", str(time_arg)]
        sysproc = subprocess.Popen(syscmd, stderr=subprocess.PIPE, text=True)
        groupproc = subprocess.Popen(groupcmd, stderr=subprocess.PIPE, text=True)
        sys_chunks = read_perf_chunks(sysproc, sevents)
        cg_chunks  = read_perf_chunks(groupproc, cgevents)
        for line in zip_longest(sys_chunks, cg_chunks):
            results.append(parse_perf_line(line,True,args.cgroup))
            #parse_perf_line(sys_line,cg_line)
            # cg_line = first line from cgroup perf
    else:
        sysproc = subprocess.Popen(syscmd, stderr=subprocess.PIPE, text=True)
        sys_chunks = read_perf_chunks(sysproc, sevents)
        for line in zip(sys_chunks):
            results.append(parse_perf_line(line,False))
    
    sysproc.wait()
    with open("measurement.json", "w") as f:
        json.dump(results, f, indent=2)

def read_perf_chunks(proc, events_per_interval):
    chunk = []
    for line in proc.stderr:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        chunk.append(line)
        if len(chunk) == events_per_interval:
            yield chunk
            chunk = []
    if chunk:
        yield chunk

def parse_perf_line(line, cg, cgname=None):
    result = {}
    print(line)
    sysline = line[0]
    result["timestamp"] = float(sysline[0].split()[0])
    result["system"] = {}
    for i in sysline:
        measure = i.split()
        if "<not counted>" in i:
            result["system"][measure[-1]] = 0
            continue
        
        if "Joules" in i:
            result["system"][measure[3]] = float(measure[1].replace(",",""))
            continue
        result["system"][measure[2]] = float(measure[1].replace(",",""))
    if cg:
        cgline = line[1]
        result[cgname] = {}
        for i in cgline:
            measure = i.split()
            if "<not counted>" in i and "Joules" in i:
                result[cgname][measure[4]] = 0
                continue
            if "<not counted>" in i:
                result[cgname][measure[3]] = 0
                continue
            
            if "Joules" in i:
                result[cgname][measure[3]] = float(measure[1].replace(",",""))
                continue
            result[cgname][measure[2]] = float(measure[1].replace(",",""))
    
    return result

def graph(cgname, plott=0):
    with open("measurement.json") as f:
        data = json.load(f)
    time = []
    syspow = []
    sysinstr = []
    groupinstr = []
    for i in data:
        time.append(i["timestamp"])
        sysinstr.append(i["system"]["cpu_core/instructions/"])
        syspow.append(i["system"]["power/energy-cores/"])
        groupinstr.append(i[cgname]["cpu_core/instructions/"])
    est_power = []
    for p, si, gi in zip(syspow, sysinstr, groupinstr):
        est_power.append(p * gi / si)
    
    # Plot
    if plott == 0:
        plt.figure(figsize=(10,6))
        plt.plot(time, syspow, label="System Power", marker="o")
        plt.plot(time, est_power, label="Scaled (sysinstr/groupinstr)", marker="x")

        plt.xlabel("Time")
        plt.ylabel("Value")
        plt.title("System vs Scaled Power")
        plt.legend()
        plt.grid(True)

        plt.show()
    if plott == 1:
        fig, ax1 = plt.subplots()

    # System power on left y-axis
        ax1.plot(time, syspow, label="System Power", color="blue")
        ax1.set_ylabel("System Power (Joules)", color="blue")

    # Cgroup power on right y-axis
        ax2 = ax1.twinx()
        ax2.plot(time, est_power, label="Cgroup Estimated Power", color="red")
        ax2.set_ylabel("Cgroup Power (Joules)", color="red")

        plt.xlabel("Time (s)")
        plt.title("System vs Cgroup Power")
        plt.show()
    plt.figure(figsize=(10,6))
    plt.plot(time, sysinstr, label="System Instructions", marker="o")
    plt.plot(time, groupinstr, label="group instructions", marker="x")

    plt.xlabel("Time")
    plt.ylabel("Value")
    plt.title("System vs group instr")
    plt.legend()
    plt.grid(True)

    plt.show()


def main(): #LATER MAKE CGROUP A LIST
    print("Parsing Arguments")
    args = parse_args()
    print(f"returned args : {args}")
    if args.command == "init":
        print("INIT RUN")
        init_events()
    elif args.command == "run":
        print("RUN COMMAND")
        run_monitor(args)
        graph(args.cgroup)

if __name__ == "__main__":
    main()

