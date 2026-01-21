"""
Comprehensive, cleaned and robust single-file server for Drone human-detection + telemetry
- Flask REST API for receiving telemetry (/data), recent (/recent), follow (/follow), command (/command)
- HOG-based human detector running in background thread
- Save detected-frame photos with optional GPS EXIF (piexif)
- MySQL initialization and insertion
- Robust parsing and error handling

Dependencies:
- flask, flask_cors
- opencv-python, imutils, pillow, piexif
- mysql-connector-python

Usage:
- Configure DEBUG and DEBUG_VIDEO paths
- Ensure MySQL server running or adjust dbconfig
- Run: python drone_server_full.py
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import mysql.connector
import threading
import cv2
import imutils
import logging
import os
import time

# Optional imports used if available
try:
    from PIL import Image
    import piexif
    HAS_PIL = True
except Exception:
    HAS_PIL = False

# Try to import MissionPlanner / MAVLink for command execution (optional)
try:
    import clr
    clr.AddReference("MissionPlanner")
    clr.AddReference("MAVLink")
    from MAVLink import MAV_CMD
    import MissionPlanner
    HAS_MISSIONPLANNER = True
except Exception:
    HAS_MISSIONPLANNER = False

# ============================================================
# CONFIG
# ============================================================
DEBUG = True
DEBUG_VIDEO = r"C:\sapi\sapi kuliah\iwill\DroneIWILLHumanDetection\VideoDroneIWILL.mp4"
DB_CONFIG = {"host": "localhost", "user": "root", "password": "", "database": "drone"}
PHOTO_DIR = "./foto"
os.makedirs(PHOTO_DIR, exist_ok=True)

# ============================================================
# LOGGER
# ============================================================
logger = logging.getLogger("follow_logger")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("follow.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# ============================================================
# VIDEO & DETECTOR SETUP
# ============================================================
# We keep a global last_detected_frame shared between threads
last_detected_frame = None

HOGCV = cv2.HOGDescriptor()
HOGCV.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

# Helper: open video source (debug file or webcam)
def _open_video_source(path=None):
    if DEBUG and path is None:
        cap = cv2.VideoCapture(DEBUG_VIDEO)
    elif path:
        cap = cv2.VideoCapture(path)
    else:
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Video source cannot be opened: %s", path or ("DEBUG" if DEBUG else "WEBCAM"))
    return cap

# ============================================================
# IMAGE / EXIF UTILITIES
# ============================================================

def deg_to_dms_rational(deg):
    """Convert decimal degrees to EXIF DMS rational format.
    Returns a tuple of 3 tuples: ((deg,1),(min,1),(sec,100))
    """
    deg_abs = abs(float(deg))
    d = int(deg_abs)
    m = int((deg_abs - d) * 60)
    s = round((deg_abs - d - m/60) * 3600, 2)
    return ((d, 1), (m, 1), (int(s * 100), 100))


def add_gps_to_image(input_path, output_path, latitude, longitude, altitude=None):
    """Add GPS EXIF to an existing JPEG image. Uses piexif if available.
    latitude/longitude: numeric (float). altitude optional (float).
    If PIL/piexif not available, function will silently skip EXIF writing but keep the image.
    """
    try:
        if not HAS_PIL:
            logger.warning("PIL/piexif not available: skipping EXIF write")
            return

        lat = float(latitude)
        lon = float(longitude)

        img = Image.open(input_path)

        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        lat_ref = "N" if lat >= 0 else "S"
        lon_ref = "E" if lon >= 0 else "W"

        exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat_ref
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = deg_to_dms_rational(lat)
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lon_ref
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = deg_to_dms_rational(lon)

        if altitude is not None:
            alt = float(altitude)
            exif_dict["GPS"][piexif.GPSIFD.GPSAltitudeRef] = 1 if alt < 0 else 0
            exif_dict["GPS"][piexif.GPSIFD.GPSAltitude] = (int(abs(alt) * 100), 100)

        exif_bytes = piexif.dump(exif_dict)
        img.save(output_path, "jpeg", exif=exif_bytes)
        logger.info("Saved GPS EXIF to %s", output_path)
    except Exception as e:
        logger.exception("Failed to add GPS EXIF: %s", e)

# ============================================================
# DETECTION & PHOTO FUNCTIONS
# ============================================================

def detect(frame):
    """Detect people in frame (HOG) and draw bounding boxes.
    Stores last_detected_frame when detection occurs.
    """
    global last_detected_frame
    boxes, _ = HOGCV.detectMultiScale(frame, winStride=(4, 4), padding=(8, 8), scale=1.03)
    for (x, y, w, h) in boxes:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    if len(boxes) > 0:
        last_detected_frame = frame.copy()
    return frame


def take_photo(text, filename, drone_data=None):
    """Capture last detected frame, add overlay text, save image, optionally embed GPS.
    drone_data: dict containing latitude, longitude, altitude (strings/floats) — will be parsed safely.
    """
    global last_detected_frame

    if last_detected_frame is None:
        logger.info("No detected frame available; photo not taken")
        return None

    frame = last_detected_frame.copy()
    pos = (10, frame.shape[0] - 10)
    cv2.putText(frame, str(text), pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    filepath = os.path.join(PHOTO_DIR, f"{filename}.jpg")
    cv2.imwrite(filepath, frame)
    logger.info("Saved photo to %s", filepath)

    # Try to embed GPS if provided
    try:
        if drone_data:
            lat_raw = drone_data.get("latitude")
            lon_raw = drone_data.get("longitude")
            alt_raw = drone_data.get("altitude")
            if lat_raw not in (None, "", "None") and lon_raw not in (None, "", "None"):
                lat = float(lat_raw)
                lon = float(lon_raw)
                alt = float(alt_raw) if (alt_raw not in (None, "", "None")) else None
                add_gps_to_image(filepath, filepath, lat, lon, alt)
    except Exception:
        logger.exception("Failed to attach GPS to photo")

    return filepath

# ============================================================
# BACKGROUND HUMAN DETECTOR THREAD
# ============================================================

def human_detector_thread(video_path=None):
    cap = _open_video_source(video_path)
    if not cap or not cap.isOpened():
        logger.error("Detector thread exiting because video source couldn't open")
        return

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame = imutils.resize(frame, width=min(800, frame.shape[1]))
        frame = detect(frame)
        cv2.imshow("output", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

# ============================================================
# DATABASE HELPERS
# ============================================================

def initiate_database():
    try:
        conn = mysql.connector.connect(host=DB_CONFIG['host'], user=DB_CONFIG['user'], password=DB_CONFIG['password'])
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS drone")
        cursor.execute("USE drone")
        cursor.execute("""
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
        """)
        logger.info("Database initialized")
    except Exception as e:
        logger.exception("Failed to init database: %s", e)
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


def connect_database():
    return mysql.connector.connect(host=DB_CONFIG['host'], user=DB_CONFIG['user'], password=DB_CONFIG['password'], database=DB_CONFIG['database'])

# ============================================================
# FLASK APP + ROUTES
# ============================================================

app = Flask(__name__)
CORS(app)

current_command = {"command": ""}
command_lock = threading.Lock()

droneData = {'altitude': None, 'latitude': None, 'longitude': None,
             'roll': None, 'groundspeed': None, 'verticalspeed': None,
             'yaw': None, 'satcount': None, 'wp_dist': None, 'human_detected': False}


@app.route('/data', methods=['GET', 'POST'])
def data_route():
    global droneData

    if request.method == 'GET':
        try:
            conn = connect_database()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM drone_data")
            rows = cursor.fetchall()
            return jsonify(rows), 200
        except Exception as e:
            logger.exception("/data GET error: %s", e)
            return jsonify({'error': str(e)}), 500
        finally:
            try:
                cursor.close(); conn.close()
            except Exception:
                pass

    # POST
    try:
        data = request.get_json(force=True)
        # update global
        droneData.update(data)

        # Save photo with timestamp name
        timestamp = datetime.now().strftime('%m-%d-%H-%M-%S')
        teks = f"alt:{data.get('altitude')} lat:{data.get('latitude')} lon:{data.get('longitude')}"
        photo_path = take_photo(teks, timestamp, drone_data=data)

        # Insert to DB (convert strings to floats when possible)
        conn = connect_database()
        cursor = conn.cursor()
        insert_query = (
            "INSERT INTO drone_data (altitude, latitude, longitude, roll, groundspeed, verticalspeed, yaw, satcount, wp_dist, timestamp)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        )
        def _to_float(v):
            try:
                return float(v) if v not in (None, "", "None") else None
            except Exception:
                return None

        data_tuple = (
            _to_float(data.get('altitude')),
            _to_float(data.get('latitude')),
            _to_float(data.get('longitude')),
            _to_float(data.get('roll')),
            _to_float(data.get('groundspeed')),
            _to_float(data.get('verticalspeed')),
            _to_float(data.get('yaw')),
            int(float(data.get('satcount'))) if data.get('satcount') not in (None, "", "None") else None,
            _to_float(data.get('wp_dist')),
            datetime.now()
        )
        cursor.execute(insert_query, data_tuple)
        conn.commit()

        return jsonify({'message': 'Data saved', 'photo': photo_path}), 200

    except Exception as e:
        logger.exception("/data POST error: %s", e)
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close(); conn.close()
        except Exception:
            pass


@app.route('/recent', methods=['GET'])
def recent_route():
    try:
        conn = connect_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM drone_data ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            return jsonify({'data': row}), 200
        else:
            return jsonify({'data': None}), 404
    except Exception as e:
        logger.exception("/recent error: %s", e)
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close(); conn.close()
        except Exception:
            pass


@app.route('/follow', methods=['GET', 'POST'])
def follow_route():
    global target
    if request.method == 'GET':
        if target.get('latitude') is not None and target.get('longitude') is not None:
            return jsonify({'target': target}), 200
        return jsonify({'message': 'no target'}), 404

    # POST
    data = request.get_json()
    if not all(k in data for k in ('altitude', 'latitude', 'longitude')):
        return jsonify({'error': 'missing params'}), 400
    target.update(data)
    logger.info("New follow target: %s", target)
    return jsonify({'message': 'target updated', 'target': target}), 200


@app.route('/command', methods=['GET', 'POST'])
def command_route():
    global current_command
    if request.method == 'GET':
        with command_lock:
            return jsonify(current_command)

    # POST
    try:
        payload = request.json
        if 'command' not in payload:
            return jsonify({'error': 'invalid format'}), 400
        cmd = payload['command'].strip()

        # Basic validation for complex commands (testmotor,goto,followtarget)
        if cmd.startswith('testmotor'):
            parts = cmd.split(',')
            if len(parts) != 3:
                return jsonify({'error': 'invalid testmotor format'}), 400
        elif cmd.startswith('goto') or cmd.startswith('followtarget'):
            parts = cmd.split(',')
            if len(parts) != 4:
                return jsonify({'error': 'invalid goto/followtarget format'}), 400
            try:
                float(parts[1]); float(parts[2]); float(parts[3])
            except Exception:
                return jsonify({'error': 'invalid numeric parameters'}), 400

        with command_lock:
            current_command = payload

        return jsonify({'message': 'command updated', 'command': cmd}), 200

    except Exception as e:
        logger.exception("/command error: %s", e)
        return jsonify({'error': str(e)}), 500


# ============================================================
# COMMAND EXECUTOR (optional MissionPlanner integration)
# ============================================================

def execute_command_on_vehicle(command_str):
    """Execute command on vehicle. If MissionPlanner not available, we log only."""
    logger.info("Executing command: %s", command_str)
    if not HAS_MISSIONPLANNER:
        logger.warning("MissionPlanner not available; skipping actual execution")
        return False

    # Minimal example: parse and call relevant MissionPlanner functions
    try:
        cmd = command_str.lower().strip()
        if cmd == 'arm':
            # Example: this depends on your MissionPlanner environment
            MAV.doARM(True)
            return True
        if cmd == 'disarm':
            MAV.doARM(False)
            return True
        if cmd.startswith('takeoff'):
            parts = cmd.split(',')
            if len(parts) == 2:
                alt = float(parts[1])
                MAV.doCommand(MAV_CMD.TAKEOFF, 0, 0, 0, 0, 0, 0, alt)
                return True
        if cmd.startswith('goto') or cmd.startswith('followtarget'):
            parts = cmd.split(',')
            if len(parts) == 4:
                alt = float(parts[1]); lat = float(parts[2]); lon = float(parts[3])
                # Implement your flight function here (fly/fly2)
                logger.info("(MissionPlanner) would fly to: %s", (lat, lon, alt))
                return True
        # Add more handlers as needed
    except Exception as e:
        logger.exception("Failed to execute on vehicle: %s", e)
        return False

    return False

# ============================================================
# MAIN
# ============================================================

target = {'altitude': None, 'latitude': None, 'longitude': None}

if __name__ == '__main__':
    # Initialize DB
    initiate_database()

    # Start detector thread
    detector_thread = threading.Thread(target=human_detector_thread, kwargs={'video_path': None}, daemon=True)
    detector_thread.start()

    # Run Flask
    app.run(host='0.0.0.0', port=5000)
