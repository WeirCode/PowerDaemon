import inotify.adapters

CGROUP_PATH = "/sys/fs/cgroup/sensor"

i = inotify.adapters.Inotify()

i.add_watch(CGROUP_PATH)

print("Watching CGROUP for changes")

for event in i.event_gen(yield_nones=False):
    (_, type_names, path, filename) = event
    print(f"Event {type_names} on {filename} in {path}")
    if "IN_CREATE" in type_names or "IN_MOVED_TO" in type_names:
        print(f"New PID added: {filename}")