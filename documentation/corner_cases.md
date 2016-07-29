# analogclient.py

- ADC.setup throws RuntimeError on ADC error - handled in main.py
- config file does not have required config values throws ValueError - handled in main.py
- averages is set to 0 in the config file, causing div by 0 - handled in `AnalogClient.__init__`, throws ValueError, handled in main.py
- time is corrected backwards, so we never report a value (time not monotonic) - handled by using the `monotonic` library
- ADC.read_raw returns RuntimeError, ValueError, or IOError - handled in `AnalogClient.run`
- Measurement with invalid IO Pins or lists - handled in check_config, where we check that all measurement items are the right length and contain the right types

# bmsclient.py

- Constructor fails: caller must handle - handled in main.py
	+ Error opening serial port - SerialException
	+ Error opening stream file - IOError (Python2) or OSError (Python >= 3.3)
	+ Error with configuration map - ValueError
- Integer conversion of charge or SoC fails (Extremely unlikely - we have confirmed checksum) But try blocks are cheap - handled in `BmsClient.run`
- Integer conversion of checksum fails (ValueError) - handled in `BmsClient.run`
- Stream file write error (USB removed, corrupted, unmounted, etc.) - ignored in `BmsClient.run`

# config.py

- Not important. Once we're in production, this will just read in a configuration file once at the beginning.

# deepseaclient.py

- Constructor fails - handled IOError, serial.SerialException, and ValueError in `main.py`
	+ Cannot open TCP port - IOError
	+ Cannot open serial RTU - serial.SerialException
	+ Fails out of constructor before `_client` assigned, so `__del__` throws an exception - handled in `__del__`
	+ Read measurement description file fails - ValueError
- Time set during loop (non-monotonic) - handled using `monotonic` package
- Modbus execute errors
	+ Sending errors
		* SerialException from serial.serialutil
		* portNotOpenError from serial.serialutil
		* writeTimeoutError from serial.serialutil
	+ Receiving errors:
		* SerialException from serial.serialutil
		* portNotOpenError from serial.serialutil
	+ Modbus errors:
		* ModbusError from modbus_tk.exceptions
		* ModbusInvalidResponseError from modbus_tk.exceptions
- Getting out of sync in modbus_tk?

# entry.py

- Not terribly important, since it only runs once
- Changed file locations problematic for hardcoded log, directory, config file

# logfilewriter.py

- 'ldir' key not in config - handled with ValueError in `logfilewriter.py`
- constructor errors - handled in `main`
- Main thread crashes, how do we respond? - current approach: loop infinitely, never do anything.
- File cannot be written to (full disk, USB removed, etc.) - Handled in `write_line` - simply logged and skipped

# main.py

- Threads crash - monitor and restart - every 10th time around the `main` loop (about once a second) check if threads are alive and start them again if they aren't.
- print_data raises an exception from one of the clients - we want to handle this in the functions, not in main. Avoid hardening this to avoid missing errors.
- csv_line raises an exception from one of the clients - same.
- Queue runs out of space (unlikely, since we're using an unlimited queue. Only if logfilewriter crashes) - catching the exception. This probably ought to be an exit condition, because something went really screwy.
- analog.values does not have the necessary key 'current' for sending to woodwardcontrol as process_variable - report it once by logger then pass
- Unhandled exceptions ought to restart the program - I think actually we'd rather just make sure that every possible exception is handled. On an unhandled exception, exit.

# woodwardcontrol.py

- Constructor exceptions - handled in `main.py`
	+ ValueError for invalid config map
	+ ValueError for invalid config value such as PWM pin
- Still need to debug compute and main run loop - Ran through with Herb. Need to test.
- non-monotonic time - handled using `monotonic` library