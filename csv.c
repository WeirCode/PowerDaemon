#include "csv_logger.h"
#include <stdio.h>

static FILE *csv_file = NULL;

int csv_logger_init(const char *filename) {
    csv_file = fopen(filename, "w");
    if (!csv_file) {
        return -1;
    }
    fprintf(csv_file, "timestamp,energy_uj\n");
    fflush(csv_file);
    return 0;
}

void csv_logger_log(const char *timestamp, uint64_t energy_uj) {
    if (!csv_file) return;
    fprintf(csv_file, "%s,%llu\n", timestamp, (unsigned long long)energy_uj);
    fflush(csv_file);
}

void csv_logger_close() {
    if (csv_file) {
        fclose(csv_file);
        csv_file = NULL;
    }
}
