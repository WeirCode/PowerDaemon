#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>

int main(int argc, char *argv[]) {
    pid_t pid;
    int status;

    // Default time to run the perf stat in seconds
    int duration = 10;

    // If duration is provided via command line argument
    if (argc == 2) {
        duration = atoi(argv[1]);
    }

    // Fork to run the perf command in a child process
    pid = fork();

    if (pid == -1) {
        // Fork failed
        perror("Failed to fork");
        return 1;
    }

    if (pid == 0) {
        // Child process: Run the perf stat command to monitor energy events
        char command[256];
        snprintf(command, sizeof(command), 
                 "perf stat -e power/energy-pkg/ sleep %d", duration);

        // Execute the command
        if (system(command) == -1) {
            perror("Failed to run perf stat");
            return 1;
        }

        exit(0);
    } else {
        // Parent process: Wait for the child process to finish
        waitpid(pid, &status, 0);

        if (WIFEXITED(status)) {
            printf("Perf tracking finished.\n");
        } else {
            printf("Perf tracking failed.\n");
        }
    }

    return 0;
}
