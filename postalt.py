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
import time

def execute_command(command):
    """
    Fungsi untuk mengeksekusi perintah yang diterima dari API
    Args:
        command: string perintah yang akan dieksekusi
    Returns:
        bool: True jika berhasil, False jika gagal
    """
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
                # Format: testmotor,motor_number,throttle_percentage
                # Contoh: testmotor,1,50 (test motor 1 dengan 50% throttle)
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
            # Takeoff ke ketinggian default (misalnya 10 meter)
            Script.ChangeMode("GUIDED")
            MAV.doARM(True)
            Script.Sleep(2000)
            MAV.doCommand(MAV_CMD.TAKEOFF, 0, 0, 0, 0, 0, 0, 10)       
            # MAV.doCommand(MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 10)     
            print("Executing TAKEOFF command")
            return True
            
        elif command == "land":
            # Melakukan landing
            Script.ChangeMode("LAND")
            print("Executing LAND command")
            return True
            
        elif command == "rtl":
            # Return to Launch
            Script.ChangeMode("RTL")
            print("Executing RTL command")
            return True
            
        elif command.startswith("goto"):
            # Format: goto,altitude,latitude,longitude
            try:
                parts = command.split(',')
                if len(parts) == 4:
                    alt = float(parts[1])
                    lat = float(parts[2])
                    lon = float(parts[3])
                    return fly(alt, lat, lon)
            except:
                print("Invalid GOTO command format")
                return False
                
        else:
            print(f"Unknown command: {command}")
            return False
            
    except Exception as e:
        print(f"Error executing command: {e}")
        return False
    
def test_motor(motor_number, throttle_value):
    """
    Fungsi untuk testing motor individual
    Args:
        motor_number: nomor motor (1-4/1-6/1-8 tergantung frame)
        throttle_value: nilai throttle (0-100%)
    Returns:
        bool: True jika berhasil, False jika gagal
    """
    try:
        # Pastikan drone dalam keadaan disarm
        if cs.armed:
            print("Please disarm drone first")
            return False
            
        # Konversi throttle dari persentase ke nilai PWM (1000-2000)
        pwm_value = 1000 + (throttle_value * 10)
        
        # Batasi nilai PWM
        if pwm_value < 1000:
            pwm_value = 1000
        elif pwm_value > 2000:
            pwm_value = 2000                    
        MAV.doCommand(MAV_CMD.DO_MOTOR_TEST, 
                     motor_number,  # Motor number (1-4)
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

def fly(altitude, latitude, longitude):
    """
    Fungsi untuk memindahkan drone ke titik koordinat tertentu
    Args:
        altitude: ketinggian dalam meter
        latitude: garis lintang dalam derajat
        longitude: garis bujur dalam derajat
    """
    try:
        # Pastikan drone dalam mode GUIDED
        Script.ChangeMode("GUIDED")
        
        # Tunggu sampai mode berubah
        while cs.mode != "GUIDED":
            print("Menunggu mode GUIDED...")
            Script.Sleep(1000)
        
        # Perintah untuk terbang ke titik yang ditentukan
        item = MissionPlanner.Utilities.Locationwp()
        MissionPlanner.Utilities.Locationwp.lat.SetValue(item, float(latitude))
        MissionPlanner.Utilities.Locationwp.lng.SetValue(item, float(longitude))
        MissionPlanner.Utilities.Locationwp.alt.SetValue(item, float(altitude))
        
        # Kirim perintah ke drone
        MAV.setGuidedModeWP(item)
        
        print(f"Terbang ke koordinat: LAT={latitude}, LON={longitude}, ALT={altitude}m")
        
        # Monitor progress
        while True:            
            current_lat = cs.lat
            current_lon = cs.lng
            current_alt = cs.alt
            
            
            dist_to_target = MissionPlanner.Utilities.Coords.GetDistance(
                current_lat, current_lon,
                latitude, longitude
            )
            
            
            alt_diff = abs(current_alt - altitude)
            
            print(f"Jarak ke target: {dist_to_target:.1f}m, Selisih ketinggian: {alt_diff:.1f}m")
            

            if dist_to_target < 1 and alt_diff < 1:
                print("Sampai di titik target!")
                break
                
            Script.Sleep(1000) 
            
    except Exception as e:
        print(f"Error: {e}")
        return False
        
    return True

urlpost = "http://127.0.0.1:5000/data"
urlget = "http://127.0.0.1:5000/command"
while True:
    current_altitude = str(cs.alt)
    current_latitude = str(cs.lat)
    current_longitude = str(cs.lng)
    current_roll = str(cs.roll)        
    current_groundspeed = str(cs.groundspeed) 
    current_verticalspeed = str(cs.verticalspeed) 
    current_yaw = str(cs.yaw)        
    current_satcount = str(cs.satcount)   
    current_wp_dist = str(cs.wp_dist)  
    data = {
    'altitude': current_altitude,
    'latitude': current_latitude,
    'longitude': current_longitude,
    'roll': current_roll,
    'groundspeed': current_groundspeed,
    'verticalspeed': current_verticalspeed,
    'yaw': current_yaw,
    'satcount': current_satcount,
    'wp_dist': current_wp_dist
}
    time.sleep(1)
    response_text = post_request(urlpost, data) 
    # command = get_request(urlget)    

     # Ambil dan eksekusi command
    try:
        command_response = get_request(urlget)
        if command_response:
            command_data = json.loads(command_response)
            if 'command' in command_data:
                execute_command(command_data['command'])
    except Exception as e:
        print(f"Error getting/executing command: {e}")
    Script.Sleep(2000)