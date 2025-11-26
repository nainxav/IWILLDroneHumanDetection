from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import mysql.connector
import threading
import cv2
import imutils
import numpy as np
import argparse
import coordinates
import logging

DEBUG = True
DEBUG_VIDEO = r"C:\sapi\sapi kuliah\iwill\DroneIWILLHumanDetection\VideoDroneIWILL.mp4"


logger = logging.getLogger("follow_logger")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("follow.log")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

# logging.basicConfig(
#     filename='follow.log', 
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )


#cap = cv2.VideoCapture(0)
# cap = None

if DEBUG:
    video = cv2.VideoCapture(DEBUG_VIDEO)
    if not video.isOpened():
        print("Error: video tidak bisa dibuka!")
else:
    cap = cv2.VideoCapture(0)

last_detected_frame = None

HOGCV = cv2.HOGDescriptor()
HOGCV.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

# def detect(frame):
#     # Detect people in the image
#     bounding_box_cordinates, weights = HOGCV.detectMultiScale(
#         frame, 
#         winStride=(4, 4), 
#         padding=(8, 8), 
#         scale=1.03
#     )

#     person = 1
#     for x, y, w, h in bounding_box_cordinates:
#         cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
#         cv2.putText(frame, f'person {person}', (x, y),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
#         person += 1

#     cv2.putText(frame, 'Status : Detecting ', (40, 40),
#                 cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 0, 0), 2)
#     cv2.putText(frame, f'Total Persons : {person - 1}', (40, 70),
#                 cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 0, 0), 2)

#     return frame

def detect(frame):
    global last_detected_frame

    bounding_box_cordinates, weights = HOGCV.detectMultiScale(
        frame, 
        winStride=(4, 4), 
        padding=(8, 8), 
        scale=1.03
    )

    for (x, y, w, h) in bounding_box_cordinates:
        cv2.rectangle(frame, (x,y), (x+w, y+h), (0,255,0), 2)

    # Simpan frame terakhir yang ada manusia
    if len(bounding_box_cordinates) > 0:
        last_detected_frame = frame.copy()

    return frame

def take_photo(teks, filename):
    global last_detected_frame

    if last_detected_frame is None:
        print("Belum ada frame terdeteksi manusia. Foto tidak diambil.")
        return

    # Baru tampilkan kalau sudah pasti tidak None
    cv2.imshow("Last Detected Frame", last_detected_frame)
    cv2.waitKey(1)

    frame = last_detected_frame.copy()

    font = cv2.FONT_HERSHEY_SIMPLEX
    posisi = (10, frame.shape[0] - 10)
    cv2.putText(frame, teks, posisi, font, 0.5, (255,255,255), 2)

    cv2.imwrite('./foto/' + filename + '.jpg', frame)
    print("Foto berhasil disimpan dari frame deteksi manusia.")



def humanDetector(args):
    # # If video path is provided, use it; otherwise, use webcam
    # if args["video"]:
    #     video_path = args["video"]
    #     print(f'[INFO] Opening video {video_path}')
    #     # video = cv2.VideoCapture(0)
    #     # video = "C:\sapi\sapi kuliah\iwill\Drone\VideoDroneIWILL.mp4"
    # else:
    #     print('[INFO] Starting webcam stream.')
    #     # video = cv2.VideoCapture(0)
    #     # video = "C:\sapi\sapi kuliah\iwill\Drone\VideoDroneIWILL.mp4"

    if DEBUG:
        video = cv2.VideoCapture(DEBUG_VIDEO)
        if not video.isOpened():
            print("Error: video tidak bisa dibuka!")
    elif args["video"]:
        video = cv2.VideoCapture(args["video"])
    else:
        video = cv2.VideoCapture(0)

    # Process each frame
    while video.isOpened():
        check, frame = video.read()
        if not check:
            break

        frame = imutils.resize(frame, width=min(800, frame.shape[1]))
        frame = detect(frame)
        cv2.imshow('output', frame)

        key = cv2.waitKey(1)
        if key == ord('q'):
            break

    video.release()
    cv2.destroyAllWindows()

# def take_photo(teks,filename):
#     # if not cap.isOpened():
#     #     print("Tidak bisa membuka kamera.")
#     #     exit()

#     video = "C:\sapi\sapi kuliah\iwill\Drone\VideoDroneIWILL.mp4"

#     if not video.isOpened():
#         print("Tidak bisa membuka video debug.")
#         return


#     #ret, frame = cap.read()
#     ret, frame = video.read()
#     video.release()
#     # frame = detect(frame)

#     if not ret:
#         print("Frame pertama tidak bisa dibaca.")
#         return

#     font = cv2.FONT_HERSHEY_SIMPLEX
#     posisi = (10, frame.shape[0] - 10)

#     cv2.putText(frame, teks, posisi, font, 0.4, (255, 255, 255), 2, cv2.LINE_AA)

#     cv2.imwrite('./foto/' + filename + '.jpg', frame)

#     print("Foto debug berhasil disimpan.")

    # # teks = "Ini teks di pojok kiri bawah"
    # font = cv2.FONT_HERSHEY_SIMPLEX
    # ukuran_font = 0.4
    # warna = (255, 255, 255)  
    # ketebalan = 2

    # tinggi, lebar = frame.shape[:2]
    # posisi = (10, tinggi - 10)

    # cv2.putText(frame, teks, posisi, font, ukuran_font, warna, ketebalan, cv2.LINE_AA)

    # # cv2.imshow('Gambar dengan Teks', frame)

    # cv2.imwrite('./foto/'+filename+'.jpg', frame)    
    
    # print("berhasil")

    # cv2.waitKey(0)

    # cap.release()
    # cv2.destroyAllWindows()

app = Flask(__name__)
CORS(app)


current_command = {"command": ""}
command_lock = threading.Lock()

# bagian sini samain sama mySQL anata ya aibou
dbconfig = {"host": "localhost", "user":"root", "password":""}

droneData = {'altitude':None, 'latitude':None, 'longitude':None, 
             "roll":None,"groundspeed":None,"verticalspeed":None,"yaw":None,
             "satcount":None,"wp_dist":None}

def initiateDatabase():
    try:        
        conn = mysql.connector.connect(
            host=dbconfig["host"],
            user=dbconfig["user"],
            password=dbconfig['password']
        )
        cursor = conn.cursor()
        
        cursor.execute("CREATE DATABASE IF NOT EXISTS drone")
                
        cursor.execute("USE drone")
                
        query = """
        CREATE TABLE IF NOT EXISTS drone_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            altitude FLOAT,
            latitude FLOAT,
            longitude FLOAT,
            roll FLOAT,
            groundspeed FLOAT,
            verticalspeed FLOAT,
            yaw FLOAT,
            satcount INT,
            wp_dist FLOAT
        )
        """
        cursor.execute(query)

        print("berhasil anjai")        
        
    except mysql.connector.Error as err:
        print(err)  
        
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def connectDatabase():
    return mysql.connector.connect(
        host=dbconfig['host'],
        user=dbconfig['user'],
        password=dbconfig['password'],
        database='drone'
    )

@app.route('/data', methods=['GET','POST'])
def get_altitude():    
    global droneData
    if request.method == 'GET':
        try:
            conn = connectDatabase()        
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM drone_data"
            cursor.execute(query)
            data = cursor.fetchall()            
            return data
        except mysql.connector.errors as e:
            print(e)
        except Exception as e:
            print(e)
    elif request.method == "POST":
        try:            
            data = request.get_json()                                
            conn = connectDatabase()
            cursor = conn.cursor()   
            droneData.update(data)
            time = datetime.now()
            time = f"{str(time.month)}-{str(time.day)}-{str(time.hour)}-{str(time.minute)}-{str(time.second)}"
            take_photo("alt: "+data.get("altitude")+" latitude: "+data.get('latitude')+" longitude: "+data.get('longitude'), time)
            print("foto berhasil")                     
            insert_query = """
                INSERT INTO drone_data 
                (altitude, latitude, longitude, roll, groundspeed, 
                verticalspeed, yaw, satcount, wp_dist, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            data_tuple = (                
                data.get('altitude'),
                data.get('latitude'),
                data.get('longitude'),
                data.get('roll'),
                data.get('groundspeed'),
                data.get('verticalspeed'),
                data.get('yaw'),
                data.get('satcount'),
                data.get('wp_dist'),
                time
            )
                        
            cursor.execute(insert_query, data_tuple)                        
            conn.commit()
                        
            
            #coordinates.add_attribute(time,data.get('latitude'),data.get('longitude'))

            cursor.close()
            conn.close()
            
            return jsonify({
                'message': 'Data successfully saved',                
                'data': data
            }), 200
            
        except mysql.connector.Error as e:
            return jsonify({
                'error': f'Database error: {str(e)}'
            }), 500
            
        except Exception as e:
            print(e)
            return jsonify({
                'error': f'Error: {str(e)}'
            }), 500
        
@app.route('/follow', methods=['GET', 'POST'])
def follow():
    global target

    if request.method == 'GET':     
        if target['longitude'] != None or target['latitude'] != None:   
            return jsonify({
                'message': 'Current target coordinates',
                'target': target
            }), 200
        else:
            return jsonify({
                'message': 'there\'s no target yet'                
            }), 404

    elif request.method == 'POST':
        data = request.get_json()
        
        if not all(a in data for a in ('altitude', 'latitude', 'longitude')):
            return jsonify({'error': 'Missing altitude, latitude, or longitude'}), 400
        
        target['altitude'] = data['altitude']
        target['latitude'] = data['latitude']
        target['longitude'] = data['longitude']
        
        logger.info(f"New follow target set: altitude={data['altitude']}, latitude={data['latitude']}, longitude={data['longitude']}")

        return jsonify({
            'message': 'Target coordinates updated successfully',
            'target': target
        }), 200


            


target = {'altitude':None, 'latitude':None, 'longitude':None}
commands = []

def changedata(data):
    global droneData
    if 'altitude' in data:
        altitude = data['altitude']
        return jsonify({'altitude': altitude}), 200
    else:
        return jsonify({'error': 'No altitude provided'}), 400

@app.route('/changealt', methods=['POST'])
def changealt():   
    global droneData 
    data = request.get_json()
    if 'altitude' and 'latitude' and 'longitude' in data:
        droneData = data
        return jsonify(droneData), 200
    else:
        return jsonify({'error': 'No altitude provided'}), 400

@app.route('/recent', methods=['GET'])
def get_recent():
    try:
        conn = connectDatabase()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT * FROM drone_data 
        ORDER BY timestamp DESC 
        LIMIT 1
        """

        cursor.execute(query)
        recent_data = cursor.fetchone()

        if recent_data:
            return jsonify({                
                'data': recent_data
            }), 200
        else:
            return jsonify({
                'message': 'No data found',
                'data': None
            }), 404

    except mysql.connector.Error as e:
        return jsonify({
            'error': f'Database error: {str(e)}'
        }), 500

    except Exception as e:
        return jsonify({
            'error': f'Error: {str(e)}'
        }), 500

    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/command', methods=['GET','POST'])
def command():
    global current_command
    
    if request.method == 'GET':
        with command_lock:
            return jsonify(current_command)
            
    elif request.method == 'POST':
        try:            
            new_command = request.json
                        
            if 'command' not in new_command:
                return jsonify({"error": "Invalid command format"}), 400
                            
            command = new_command['command'].lower().strip()
                        
            valid_commands = ['arm', 'disarm', 'takeoff', 'land', 'rtl', 'followtarget','']                        
                                
            if command.startswith('testmotor'):
                parts = command.split(',')
                if len(parts) != 3:
                    return jsonify({"error": "Invalid testmotor command format"}), 400
                try:                    
                    motor_num = int(parts[1])
                    throttle = float(parts[2])
                    if not (1 <= motor_num <= 8 and 0 <= throttle <= 100):
                        return jsonify({"error": "Invalid motor number or throttle value"}), 400
                except ValueError:
                    return jsonify({"error": "Invalid testmotor parameters"}), 400
                
            elif command.startswith('goto'):
                parts = command.split(',')
                if len(parts) != 4:
                    return jsonify({"error": "Invalid followtarget command format"}), 400
                try:
                    altitude = float(parts[1])
                    latitude = float(parts[2])
                    longitude = float(parts[3])
                    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180 and altitude >= 0):
                        return jsonify({"error": "Invalid GPS or altitude values"}), 400
                except ValueError:
                    return jsonify({"error": "Invalid followtarget parameters"}), 400
                
            elif command.startswith('followtarget'):
                parts = command.split(',')
                if len(parts) != 4:
                    return jsonify({"error": "Invalid followtarget command format"}), 400
                try:
                    altitude = float(parts[1])
                    latitude = float(parts[2])
                    longitude = float(parts[3])
                    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180 and altitude >= 0):
                        return jsonify({"error": "Invalid GPS or altitude values"}), 400
                except ValueError:
                    return jsonify({"error": "Invalid followtarget parameters"}), 400

                                
            # elif command not in valid_commands:
            #     return jsonify({"error": "Unknown command"}), 400
                        
            with command_lock:
                current_command = new_command
                
            return jsonify({"message": "Command updated successfully", "command": command})
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
#buat nambahin gps
from PIL import Image
import piexif

def deg_to_dms_rational(deg_float):
    deg = int(deg_float)
    min_float = abs(deg_float - deg) * 60
    minute = int(min_float)
    sec = round((min_float - minute) * 60 * 100)
    return [(deg, 1), (minute, 1), (sec, 100)]

def add_gps_to_image(input_path, output_path, droneData):
    img = Image.open(input_path)

    lat = droneData["latitude"]
    lon = droneData["longitude"]

    # Check if lat/lon exist
    if lat is None or lon is None:
        raise ValueError("Latitude or longitude is missing in droneData.")

    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    # references
    lat_ref = "N" if lat >= 0 else "S"
    lon_ref = "E" if lon >= 0 else "W"

    # convert
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat_ref
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = deg_to_dms_rational(abs(lat))

    exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lon_ref
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = deg_to_dms_rational(abs(lon))

    # optional — you can also embed altitude if available
    if droneData["altitude"] is not None:
        exif_dict["GPS"][piexif.GPSIFD.GPSAltitude] = (int(droneData["altitude"]), 1)
        exif_dict["GPS"][piexif.GPSIFD.GPSAltitudeRef] = 0  # 0 = above sea level

    # save image with GPS EXIF
    exif_bytes = piexif.dump(exif_dict)
    img.save(output_path, "jpeg", exif=exif_bytes)

    print(f"Saved GPS metadata to {output_path}")


if __name__ == '__main__':
    initiateDatabase()
    threading.Thread(target=humanDetector, args=({"video": None},), daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
