from flask import Flask, render_template, Response, send_file, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
import cv2
from pyzbar.pyzbar import decode
import hmac
import base64
import hashlib
import time
from pymongo import MongoClient
import io
import qrcode
import firebase_admin
from firebase_admin import credentials, auth

app = Flask(__name__)
socketio = SocketIO(app)
camera = None  # Camera is initially off
secret_key = "supersecretkey"
uri = "mongodb+srv://samriddh_kumar:sam123@tracknclassify.kjmrfft.mongodb.net/?retryWrites=true&w=majority&appName=TrackNClassify"

# MongoDB configuration
client = MongoClient(uri)
db = client["Employee"]
collection = db["Employee"]

# Initialize Firebase Admin SDK
cred = credentials.Certificate("new_env/credentials/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

def verify_token(token, secret_key, tolerance=1):
    current_time = int(time.time() / 60)
    for i in range(-tolerance, tolerance + 1):
        timestamp = current_time + i
        msg = str(timestamp).encode()
        hmac_obj = hmac.new(secret_key.encode(), msg, hashlib.sha256)
        expected_token = base64.urlsafe_b64encode(hmac_obj.digest()).decode().strip('=')
        if hmac.compare_digest(expected_token, token):
            return True
    return False

def verify_employee_data(qr_data):
    try:
        *data_parts, token = qr_data.split(',')
        employee_id, employee_name, employee_age = data_parts
        employee_age = int(employee_age)

        if not verify_token(token, secret_key):
            return "Invalid or expired QR code"
        
        with MongoClient(uri) as client:
            db = client['Employee']
            collection = db['Employee']
            
            found_document = collection.find_one({
                "ID": employee_id,
                "Name": employee_name,
                "Age": employee_age
            })

            if found_document:
                return f"{found_document['Name']} is an Employee"
            else:
                return "Not an Employee"
    except Exception as e:
        return f"An error occurred: {e}"

def generate_frames():
    global camera  # Use the global camera variable
    while True:
        if camera is not None:  # Only capture frames if the camera is turned on
            success, frame = camera.read()
            if not success:
                break
            else:
                for barcode in decode(frame):
                    qr_data = barcode.data.decode('utf-8')
                    result = verify_employee_data(qr_data)
                    socketio.emit('scan_result', result)
                    
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# Function to generate a time-based token
def generate_token(secret_key):
    timestamp = int(time.time() / 60)  # Time step of 60 seconds
    msg = str(timestamp).encode()
    hmac_obj = hmac.new(secret_key.encode(), msg, hashlib.sha256)
    token = base64.urlsafe_b64encode(hmac_obj.digest()).decode().strip('=')
    return token

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/Home')
def Home():
    return render_template('Home.html')

@app.route('/QRgenerate')
def QRgenerate():
    return render_template('QRgenerate.html')

@app.route('/generate_qr')
def generate_qr():
    # Data and secret key
    employee_data = {
        "ID": "1",
        "Name": "Samriddh",
        "Age": 19
    }
    secret_key = "supersecretkey"
    data = f'{employee_data["ID"]},{employee_data["Name"]},{employee_data["Age"]}'
    token = generate_token(secret_key)

    # Combine data with the token
    dynamic_data = f'{data},{token}'

    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    # Add dynamic data to the QR code
    qr.add_data(dynamic_data)
    qr.make(fit=True)

    # Create an image from the QR code
    img = qr.make_image(fill_color="black", back_color="white")

    # Save the image in a BytesIO object
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    return send_file(img_io, mimetype='image/png')

@app.route('/scanner')
def scanner():
    return render_template('scanner.html')

@app.route('/start_camera')
def start_camera():
    global camera  # Use the global camera variable
    if camera is None:
        camera = cv2.VideoCapture(0)  # Start the camera
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stop_camera')
def stop_camera():
    global camera  # Use the global camera variable
    if camera is not None:  # If the camera is running
        camera.release()  # Release the camera resources
        camera = None  # Set the camera to None to indicate it's off
    return 'Camera stopped'

@app.route('/AddEmployee')
def AddEmployee():
    return render_template('AddEmployee.html')

@app.route('/add_employee', methods=['POST'])
def add_employee():
    data = request.get_json()
    employee_id = data['ID']
    employee_name = data['name']
    employee_age = data['age']
    employee_email = data['email']
    employee_password = data['password']
    
    try:
        # Insert into MongoDB
        collection.insert_one({
            "ID": employee_id,
            "Name": employee_name,
            "Age": employee_age,
            "Email": employee_email,
            "Password": employee_password
        })
        
        return jsonify({"success": True}), 200
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == '__main__':
    socketio.run(app, debug=True)
