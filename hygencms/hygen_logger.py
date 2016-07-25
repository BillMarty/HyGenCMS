# Configuration map
{
    # Enabled threads
    # Each string in this list corresponds to a sub-configuration map
    # in the top level configuration map
    'enabled': ['deepsea', 'bms', 'woodward', 'analog', 'filewriter'],

    # DeepSea Configuration
    'deepsea': {
        # Where to find the measurement list
        'mlistfile':\
        '/home/hygen/dev/PPI_Cdocs/PythonTools/hygen/logger/cur_rpm.csv',
        # Possible mode values are 'rtu' or 'tcp'
        'mode': 'rtu',
        # RTU settings
        'baudrate': 19200,  # serial port baudrate
        'dev': '/dev/ttyO1',  # serial device
        'id': 10,  # Set on deepsea - slave ID
    },

    # BMS Configuration
    'bms': {
        # serial port settings
        'baudrate': 9600,
        'dev': '/dev/ttyO4',
        # File name for ASCII stream to be saved
        'sfilename': '/home/hygen/log/bmsstream.log',
    },

    # Control signal to Woodward
    'woodward': {
        'pin': 'P9_21',
        'Kp': 1.0,
        'Ki': 0.8,
        'Kd': 0.0,
        'setpoint': 25.0,  # Amps
        'period': 1.0,
    },

    # Analog measurements to take
    'analog': {
        # How many values to average for each reported value
        'averages': 64,
        'measurements': [
            # [ 'name', 'units', 'pin', gain, offset ]
            # valid values for 'pin' are:
            # 'P9_33' = AIN4
            # 'P9_35' = AIN6
            # 'P9_36' = AIN5
            # 'P9_37' = AIN2
            # 'P9_38' = AIN3 = pulse count circuit / spare analog input
            # 'P9_39' = AIN0 = high bus voltage
            # 'P9_40' = AIN1 = high bus current shunt
            # These will change gains
            ['an_300v_cur', 'A', 'P9_40', 40.0, -0.2],
            ['an_300v_volt', 'V', 'P9_39', 1.0, 0.0]
        ],
        # How often to report values
        'frequency': 1.0,
    },

    # filewriter thread configuration (write data to disk)
    'filewriter': {
        'ldir': 'logs',
    },

    # Program log
    'logfile': 'errors.log',
}
