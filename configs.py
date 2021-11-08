from micropython import const

POST_TO_INFLUX_INTERVAL = const(30) # in seconds
PM_PASSIVE_MODE_INTERVAL = const(5) # in seconds
CO2_READING_INTERVAL = const(5) # in seconds
NUM_READINGS_TO_AVG = const(10)
MIN_READINGS_FOR_POST = const(5) # miniumum number of readings to average together before sending to Influx

DHT_SENSOR_PIN = const(5)
CO2_SENSOR_PIN = const(4)

INFLUX_DB_AUTH = 'user:password' # set to None if you do not have any auth

# This can either be a URL to a text file containing the location string or a static location string
# This is so you can move the device around and update the location info without needing to upload code
SENSOR_LOCATION = "http://webserver.example.com/sensorlocation"
#SENSOR_LOCATION = "garage"

INFLUX_DB_HOST = 'grafana.example.com'
INFLUX_DB_PORT = '8086'
INFLUX_DB_NAME = 'grafana' #DB name

SEND_MEMORY_INFO_TO_INFLUX = True
MEMORY_INFO_INTERVAL = const(5)