#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <time.h>
#include <fcntl.h>
#include <sys/syscall.h>
#include <linux/perf_event.h>
#include <asm/unistd.h>
#include <errno.h>

static long perf_event_open(struct perf_event_attr *hw_event, pid_t pid,
                            int cpu, int group_fd, unsigned long flags)
{
    return syscall(__NR_perf_event_open, hw_event, pid, cpu,
                group_fd, flags);
}

// Get current time in ISO 8601
void get_timestamp(char *buffer, size_t size)
{
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    strftime(buffer, size, "%Y-%m-%d %H:%M:%S", t);
}

int main()
{
    struct perf_event_attr pea;
    memset(&pea, 0, sizeof(struct perf_event_attr));
    pea.type = PERF_TYPE_POWER;
    pea.config = PERF_COUNT_POWER_ENERGY_PKG;
    pea.size = sizeof(struct perf_event_attr);
    pea.disabled = 0;
    pea.exclude_kernel = 0;
    pea.exclude_hv = 0;

    // Monitor CPU 0 system-wide
    int fd = perf_event_open(&pea, -1, 0, -1, 0);
    if (fd == -1) {
        perror("perf_event_open");
        return 1;
    }

    FILE *csv = fopen("energy_log.csv", "w");
    if (!csv) {
        perror("fopen");
        close(fd);
        return 1;
    }

    fprintf(csv, "timestamp,energy_uj\n");

    uint64_t prev_value = 0;
    read(fd, &prev_value, sizeof(uint64_t));

    for (int i = 0; i < 30; i++) { // 30 seconds sample
        sleep(1);

        uint64_t value;
        read(fd, &value, sizeof(uint64_t));

        char timestamp[64];
        get_timestamp(timestamp, sizeof(timestamp));

        fprintf(csv, "%s,%llu\n", timestamp, (unsigned long long)(value));
        fflush(csv);
    }

    fclose(csv);
    close(fd);
    return 0;
}

