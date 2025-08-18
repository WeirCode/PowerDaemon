import inotify.adapters
import os
import threading
import time

class CgroupWatcher:
    """
    Watches a single cgroup for PID changes and triggers callbacks.
    """

    def __init__(self, cgroup_path, on_pid_added=None, on_empty=None, poll_interval=1.0):
        """
        :param cgroup_path: Path to the cgroup (e.g., '/sys/fs/cgroup/sensor')
        :param on_pid_added: Callback when a PID is added: f(cgroup_path)
        :param on_empty: Callback when cgroup becomes empty: f(cgroup_path)
        :param poll_interval: Seconds to wait between empty checks
        """
        self.cgroup_path = cgroup_path
        self.on_pid_added = on_pid_added
        self.on_empty = on_empty
        self.poll_interval = poll_interval
        self._stop_flag = threading.Event()
        self._thread = None

    def start(self):
        """Start watching the cgroup in a separate thread."""
        self._thread = threading.Thread(target=self._watch_cgroup, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop watching the cgroup."""
        self._stop_flag.set()
        if self._thread:
            self._thread.join()

    def _watch_cgroup(self):
        """Internal method to watch the cgroup using inotify."""
        if not os.path.exists(self.cgroup_path):
            raise FileNotFoundError(f"Cgroup path does not exist: {self.cgroup_path}")

        previous_count = 0
        i = inotify.adapters.Inotify()
        procs_file = os.path.join(self.cgroup_path, "cgroup.procs")
        i.add_watch(procs_file)

        while not self._stop_flag.is_set():
            for event in i.event_gen(yield_nones=False):
                (_, type_names, path, filename) = event
                if filename == "cgroup.procs" and "IN_MODIFY" in type_names:
                    current_count = self._count_pids(procs_file)

                    if current_count > previous_count and self.on_pid_added:
                        self.on_pid_added(self.cgroup_path)

                    elif current_count == 0 and previous_count > 0 and self.on_empty:
                        self.on_empty(self.cgroup_path)

                    previous_count = current_count
            #time.sleep(self.poll_interval)

    @staticmethod
    def _count_pids(procs_file):
        """Return the number of PIDs currently in the cgroup."""
        try:
            with open(procs_file, "r") as f:
                return len([line for line in f if line.strip()])
        except FileNotFoundError:
            return 0
