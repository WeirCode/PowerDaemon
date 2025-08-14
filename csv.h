#ifndef CSV_LOGGER_H
#define CSV_LOGGER_H

#include <stdint.h>

int csv_logger_init(const char *filename);
void csv_logger_log(const char *timestamp, uint64_t energy_uj);
void csv_logger_close();

#endif // CSV_LOGGER_H