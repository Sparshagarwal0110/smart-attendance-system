import face_recognition
import numpy as np
import cv2
from scipy.fft import fft2, fftshift

def get_face_encoding_from_image_bytes(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_img)
    if not face_locations:
        return None
    encodings = face_recognition.face_encodings(rgb_img, face_locations)
    if not encodings:
        return None
    return encodings[0]

def recognize_face(image_bytes, known_employees):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    face_locations = face_recognition.face_locations(rgb_img)
    if not face_locations:
        return None
    
    face_encodings = face_recognition.face_encodings(rgb_img, face_locations)
    if not face_encodings:
        return None
    
    face_encoding = face_encodings[0]
    
    known_encodings = [e["face_encoding"] for e in known_employees]
    known_names = [e["name"] for e in known_employees]
    known_ids = [e["employee_id"] for e in known_employees]
    
    matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.5)
    face_distances = face_recognition.face_distance(known_encodings, face_encoding)
    
    if len(face_distances) > 0:
        best_match_index = np.argmin(face_distances)
        if matches[best_match_index]:
            return {
                "employee_id": known_ids[best_match_index],
                "name": known_names[best_match_index]
            }
    return None

# ---------------------- Passive Liveness (motion-based) ----------------------
def get_face_landmarks_array(rgb_image):
    landmarks_list = face_recognition.face_landmarks(rgb_image)
    if not landmarks_list:
        return None
    landmarks = landmarks_list[0]
    all_points = []
    for key in ['chin', 'left_eyebrow', 'right_eyebrow', 'nose_bridge', 'nose_tip', 'left_eye', 'right_eye', 'top_lip', 'bottom_lip']:
        if key in landmarks:
            all_points.extend(landmarks[key])
    return np.array(all_points)

def compute_movement(landmarks1, landmarks2):
    if landmarks1 is None or landmarks2 is None:
        return 0
    min_len = min(len(landmarks1), len(landmarks2))
    if min_len == 0:
        return 0
    diff = np.linalg.norm(landmarks1[:min_len] - landmarks2[:min_len], axis=1)
    return np.mean(diff)

def passive_liveness_multi(frame_bytes_list):
    if len(frame_bytes_list) < 2:
        return False, 0, "Need at least 2 frames"
    
    landmarks_list = []
    for b in frame_bytes_list:
        nparr = np.frombuffer(b, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return False, 0, "Invalid frame"
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        lm = get_face_landmarks_array(rgb)
        landmarks_list.append(lm)
    
    # Check face presence
    if any(lm is None for lm in landmarks_list):
        return False, 0, "Face not detected in all frames"
    
    # Compute average movement between consecutive frames
    movements = []
    for i in range(len(landmarks_list)-1):
        mov = compute_movement(landmarks_list[i], landmarks_list[i+1])
        movements.append(mov)
    avg_movement = np.mean(movements)
    
    if avg_movement > 2.0:
        return True, avg_movement, f"Natural movement ({avg_movement:.1f}px)"
    else:
        return False, avg_movement, f"Insufficient movement ({avg_movement:.1f}px)"