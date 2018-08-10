import sys, subprocess
from datetime import datetime, date, time
from sense_api import Senseable
from weather import current_temp, min_temp, max_temp, forecast_text

DATE = datetime.now().strftime("%Y%m%d")
TIME = datetime.now().strftime("%H:%M")
username = 'senseusername'
password = 'sensepass'
PVOutputURL = 'https://pvoutput.org/service/r2/addstatus.jsp'
PVOutputAPI = ''
PVOutputSID = ''

sense = Senseable(username,password)
active_power = str(sense.active_power).split('.')[0]
active_solar_power = str(sense.active_solar_power).split('.')[0]
active_voltage_split = str(sense.active_voltage).split(' ')[0]
active_voltage_strip = str(active_voltage_split).strip('[ ,')
active_voltage = active_voltage_strip[:5]
temp = round(float(current_temp),1)

PVOutputCURL = """curl -d "d={}" -d "t={}" -d "v4={}" -d "v2={}" -d "v5={}" -d "v6={}" -H "X-Pvoutput-APIkey:{}" -H "X-Pvoutput-SystemId:{}" {}""".format(DATE, TIME, active_power, active_solar_power, temp, active_voltage,PVOutputAPI, PVOutputSID, PVOutputURL)

subprocess.call(PVOutputCURL, shell=True)
print()
