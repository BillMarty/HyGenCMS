import time
import monotonic

# Keeps track of the last time the jobs ran.
# Key = period of job
# value = monotonic time value
next_run = {
    0.1: 0,
    0.5: 0,
    1.0: 0,
    5.0: 0,
    10.0: 0,
}

while True:
    now = monotonic.monotonic()
    now_time = time.time()
    # Every tenth of a second
    if now >= next_run[0.1]:
        print("[{:s}] 10Hz".format(str(now_time)))
        next_run[0.1] = now + 0.1

    # Twice a second
    if now >= next_run[0.5]:
        print("[{:s}] 2Hz".format(str(now_time)))
        next_run[0.5] = now + 0.5

    # Once a second
    if now >= next_run[1.0]:
        print("[{:s}] 1Hz".format(str(now_time)))
        next_run[1.0] = now + 1.0

    # Once every 5 seconds
    if now >= next_run[5.0]:
        print("[{:s}] 0.2Hz".format(str(now_time)))
        next_run[5.0] = now + 5.0

    if now >= next_run[10.0]:
        print("[{:s}] 0.1Hz".format(str(now_time)))
        next_run[10.0] = now + 10.0

    time.sleep(0.005)
