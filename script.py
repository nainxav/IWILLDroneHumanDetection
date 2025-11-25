import clr
import json
clr.AddReference("System")
clr.AddReference("System.IO")
clr.AddReference("MissionPlanner")
clr.AddReference("MAVLink")
import MissionPlanner
from MAVLink import MAV_CMD
from System import IO, Text
from System.Net import HttpWebRequest, WebResponse
import sys
import os


def post_request(url, data):
    request = HttpWebRequest.Create(url)
    request.Method = "POST"
    request.ContentType = "application/json"
    print("ini data kirim",data)
    
    json_data = json.dumps(data)    
    byte_data = Text.Encoding.UTF8.GetBytes(json_data)
    
    request.ContentLength = byte_data.Length
    request_stream = request.GetRequestStream()
    request_stream.Write(byte_data, 0, byte_data.Length)
    request_stream.Close()
    
    response = request.GetResponse()
    response_stream = response.GetResponseStream()
    
    reader = IO.StreamReader(response_stream)
    response_text = reader.ReadToEnd()
    
    reader.Close()
    response.Close()
    
    return response_text

def get_request(url):
    request = HttpWebRequest.Create(url)
    request.Method = "GET"
    request.ContentType = "application/json"    
    
    response = request.GetResponse()
    response_stream = response.GetResponseStream()
    
    reader = IO.StreamReader(response_stream)
    response_text = reader.ReadToEnd()
    
    reader.Close()
    response.Close()
    
    return response_text

def get_data():
    current_altitude = str(cs.alt)
    current_latitude = str(cs.lat)
    current_longitude = str(cs.lng)
    current_roll = str(cs.roll)        
    current_groundspeed = str(cs.groundspeed) 
    current_verticalspeed = str(cs.verticalspeed) 
    current_yaw = str(cs.yaw)        
    current_satcount = str(cs.satcount)   
    current_wp_dist = str(cs.wp_dist)  
    current_volt = str(cs.battery_voltage)  
    current_battery_remaining = str(cs.battery_remaining)  
    data = {
    'altitude': current_altitude,
    'latitude': current_latitude,
    'longitude': current_longitude,
    'roll': current_roll,
    'groundspeed': current_groundspeed,
    'verticalspeed': current_verticalspeed,
    'yaw': current_yaw,
    'satcount': current_satcount,
    'wp_dist': current_wp_dist,
    'volt' : current_volt,
    'battery_remaining' : current_battery_remaining
    }
    return data

def execute_command(command):
    try:
        command = command.lower().strip()
        
        if command == "arm":            
            Script.ChangeMode("GUIDED")
            MAV.doARM(True)
            print("Menjalankan ARM command")
            return True
            
        elif command == "disarm":            
            MAV.doARM(False)
            print("Menjalankan DISARM command")
            return True

        elif command.startswith("testmotor"):
            try:
                parts = command.split(',')
                if len(parts) == 3:
                    motor_num = int(parts[1])
                    throttle = float(parts[2])
                    return test_motor(motor_num, throttle)
                else:
                    print("Invalid test motor command format")
                    return False
            except:
                print("Invalid test motor parameters")
                return False
            
        elif command == "takeoff":            
            Script.ChangeMode("GUIDED")
            MAV.doARM(True)
            Script.Sleep(2000)
            MAV.doCommand(MAV_CMD.TAKEOFF, 0, 0, 0, 0, 0, 0, 10)       
            # MAV.doCommand(MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 10)     
            print("Executing TAKEOFF command")
            return True
            
        elif command == "land":            
            Script.ChangeMode("LAND")
            print("Executing LAND command")
            return True
            
        elif command == "rtl":            
            Script.ChangeMode("RTL")
            print("Executing RTL command")
            return True                    
                
        else:
            print(f"Unknown command: {command}")
            return False
            
    except Exception as e:
        print(f"Error executing command: {e}")
        return False
    
def test_motor(motor_number, throttle_value):
    try:        
        if cs.armed:
            print("Please disarm drone first")
            return False
                    
        pwm_value = 1000 + (throttle_value * 10)
                
        if pwm_value < 1000:
            pwm_value = 1000
        elif pwm_value > 2000:
            pwm_value = 2000                    
        MAV.doCommand(MAV_CMD.DO_MOTOR_TEST, 
                     motor_number, 
                     1,            
                     pwm_value,    
                     2,            
                     0,            
                     0,            
                     0)           
                     
        print(f"Testing Motor #{motor_number} at {throttle_value}% throttle")
        return True
        
    except Exception as e:
        print(f"Error testing motor: {e}")
        return False

urlpost = "http://127.0.0.1:5000/data"
urlget = "http://127.0.0.1:5000/command"

while True:
    data = get_data()
    response_text = post_request(urlpost, data) 
    # command = get_request(urlget)    
     
    try:
        command_response = get_request(urlget)
        if command_response:
            command_data = json.loads(command_response)
            if 'command' in command_data:
                execute_command(command_data['command'])
    except Exception as e:
        print(f"Error getting/executing command: {e}")
    Script.Sleep(1000)