from machine import UART
from machine import Pin
from machine import time_pulse_us
import uasyncio as asyncio
import pms5003
import dht
import urequests
import network
import time
import gc
import configs
from helper_functions import *

# Init some sensors
pm = None
dhtSensor = dht.DHT22(Pin(configs.DHT_SENSOR_PIN))
co2Pin = Pin(configs.CO2_SENSOR_PIN, Pin.IN, Pin.PULL_UP)

# Some additional config stuff
influx_headers = {
            'Accept': 'text/plain',
            'Connection': 'close',
            'Content-type': 'application/octet-stream'            
           }
if configs.INFLUX_DB_AUTH != None: influx_headers['Authorization'] = 'Token {auth}'.format(auth=configs.INFLUX_DB_AUTH)
influx_endpoint = "http://{hostname}:{port}/write?db={db}".format(hostname=configs.INFLUX_DB_HOST, port=configs.INFLUX_DB_PORT, db=configs.INFLUX_DB_NAME)

if configs.SENSOR_LOCATION.startswith('http://'): # Not getting into TLS fun..
    # Wait for the wifi adapter to connect before trying to get location
    sta_if = network.WLAN(network.STA_IF)
    while not sta_if.isconnected():
        time.sleep(1)
    location = get_location(configs.SENSOR_LOCATION)
else:
    location = configs.SENSOR_LOCATION

# Track PMS readings to avg
pm_currentReadingIdx = 0
pm_numReadings = 0
pm_dataList = [[0 for x in range(12)] for x in range(configs.NUM_READINGS_TO_AVG)]
pm_avgData = [0 for x in range(12)]

# Track CO2 readings to avg
co2_currentReadingIdx = 0
co2_numReadings = 0
co2_dataList = [0 for x in range(configs.NUM_READINGS_TO_AVG)]
co2_avgData = 0

########### BEGIN PMS METHODS
def pm_calculate_average():
    global pm_avgData
    for col in range(12):
        pm_avgData[col] = int(sum([pm_dataList[idx][col] for idx in range(pm_numReadings)]) / pm_numReadings)

async def pm_handle_reading():
    if pm._active:
        global pm_currentReadingIdx, pm_numReadings
        try:
            pm_dataList[pm_currentReadingIdx][0] = pm._pm10_standard
            pm_dataList[pm_currentReadingIdx][1] = pm._pm25_standard
            pm_dataList[pm_currentReadingIdx][2] = pm._pm100_standard
            pm_dataList[pm_currentReadingIdx][3] = pm._pm10_env
            pm_dataList[pm_currentReadingIdx][4] = pm._pm25_env
            pm_dataList[pm_currentReadingIdx][5] = pm._pm100_env
            pm_dataList[pm_currentReadingIdx][6] = pm._particles_03um
            pm_dataList[pm_currentReadingIdx][7] = pm._particles_05um
            pm_dataList[pm_currentReadingIdx][8] = pm._particles_10um
            pm_dataList[pm_currentReadingIdx][9] = pm._particles_25um
            pm_dataList[pm_currentReadingIdx][10] = pm._particles_50um
            pm_dataList[pm_currentReadingIdx][11] = pm._particles_100um
            pm_currentReadingIdx = (pm_currentReadingIdx+1) % configs.NUM_READINGS_TO_AVG
            if pm_numReadings < configs.NUM_READINGS_TO_AVG: pm_numReadings += 1
        except Exception as e:
            print('Caught exception in pm_handle_reading, {}'.format(e))

async def pm_post_to_influx():
    while True:
        if pm_numReadings > configs.MIN_READINGS_FOR_POST:
            try:
                pm_calculate_average()
                data_to_submit = (
                                "airquality,"
                                "location={location}"
                                " "
                                "pm10_standard={value0},"
                                "pm25_standard={value1},"
                                "pm100_standard={value2},"
                                "pm10_env={value3},"
                                "pm25_env={value4},"
                                "pm100_env={value5},"
                                "particles_03um={value6},"
                                "particles_05um={value7},"
                                "particles_10um={value8},"
                                "particles_25um={value9},"
                                "particles_50um={value10},"
                                "particles_100um={value11}".format(
                                    location=location,
                                    value0=pm_avgData[0],
                                    value1=pm_avgData[1],
                                    value2=pm_avgData[2],
                                    value3=pm_avgData[3],
                                    value4=pm_avgData[4],
                                    value5=pm_avgData[5],
                                    value6=pm_avgData[6],
                                    value7=pm_avgData[7],
                                    value8=pm_avgData[8],
                                    value9=pm_avgData[9],
                                    value10=pm_avgData[10],
                                    value11=pm_avgData[11],
                                    )
                                ) 
            
                response = urequests.post(influx_endpoint,
                                data=data_to_submit,
                                headers=influx_headers
                                )
                response.close()
            except Exception as e:
                print('Caught exception in pm_post_to_influx, {}'.format(e))
                continue
        await asyncio.sleep(configs.POST_TO_INFLUX_INTERVAL)
########### END PMS METHODS

########### BEGIN DHT METHODS
async def dht_post_to_influx():
    while True:
        try:
            dhtSensor.measure()
            data_to_submit = (  
                            "sensors,"
                            "location={location}"
                            " "
                            "temperature={temperature},"
                            "humidity={humidity}".format(
                                location=location,
                                temperature=(dhtSensor.temperature() * (9/5) + 32.0),
                                humidity=(dhtSensor.humidity())
                                )
                         )
            response = urequests.post(influx_endpoint,
                            data=data_to_submit,
                            headers=influx_headers
                            )
            response.close()
        except OSError as e:
            print('Failed to read sensor.')
        except Exception as e:
            print('Caught exception in dht_post_to_influx, {}'.format(e))
            continue
        await asyncio.sleep(configs.POST_TO_INFLUX_INTERVAL)

########### END DHT METHODS

########### BEGIN CO2 METHODS
def co2_calculate_average():
    global co2_avgData
    co2_avgData = int(sum([co2_dataList[idx] for idx in range(co2_numReadings)]) / co2_numReadings)

async def co2_handle_reading():
    global co2_currentReadingIdx, co2_numReadings
    while True:
        try:
            raw_value = int(time_pulse_us(co2Pin, 1)/1000)
            calculated = 2000 * (raw_value - 2) / (raw_value + (1004 - raw_value) - 4)

            co2_dataList[co2_currentReadingIdx] = calculated
            co2_currentReadingIdx = (co2_currentReadingIdx+1) % configs.NUM_READINGS_TO_AVG
            if co2_numReadings < configs.NUM_READINGS_TO_AVG: co2_numReadings += 1
        except Exception as e:
            print('Caught exception in co2_handle_reading, {}'.format(e))
            continue
        await asyncio.sleep(configs.CO2_READING_INTERVAL)

async def co2_post_to_influx():
    while True:
        if co2_numReadings > configs.MIN_READINGS_FOR_POST:
            try:
                co2_calculate_average()
                data_to_submit = (  
                                "sensors,"
                                "location={location}"
                                " "
                                "co2={co2}".format(
                                    location=location,
                                    co2=co2_avgData
                                    )
                                )

                response = urequests.post(influx_endpoint,
                                data=data_to_submit,
                                headers=influx_headers
                                )
                response.close()
            except Exception as e:
                print('Caught exception in co2_post_to_influx, {}'.format(e))
                continue
        await asyncio.sleep(configs.POST_TO_INFLUX_INTERVAL)
########### END CO2 METHODS

async def mem_post_to_influx():
    while True:
        await asyncio.sleep(configs.MEMORY_INFO_INTERVAL)
        try:
            mem_free = gc.mem_free()
            mem_used = gc.mem_alloc()
            
            data_to_submit = (  "sysinfo,"
                                "location={location}"
                                " "
                                "mem_used={mem_used},"
                                "mem_free={mem_free}".format(
                                    location=location,
                                    mem_used=mem_used,
                                    mem_free=mem_free
                                    )
                            )
            response = urequests.post(influx_endpoint,
                                    data=data_to_submit,
                                    headers=influx_headers
                                    )
            response.close()
        except Exception as e:
            print('Caught exception in mem_post_to_influx, {}'.format(e))
            continue

def start():
    uart = UART(0, 9600, parity=None, stop=1, bits=8, rxbuf=64, timeout=250)
    global pm
    pm = pms5003.PMS5003(uart, active_mode=False, eco_mode=False, interval_passive_mode=configs.PM_PASSIVE_MODE_INTERVAL, accept_zero_values=True)
    pms5003.set_debug(False)
    pm.registerCallback(pm_handle_reading)
    asyncio.create_task(pm_post_to_influx())
    asyncio.create_task(dht_post_to_influx())
    asyncio.create_task(co2_handle_reading())
    asyncio.create_task(co2_post_to_influx())
    if configs.SEND_MEMORY_INFO_TO_INFLUX: asyncio.create_task(mem_post_to_influx())
    asyncio.get_event_loop().run_forever()

start()