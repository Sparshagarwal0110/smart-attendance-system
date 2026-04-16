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

def recognize_face(image_bytes, known_students):
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
    
    known_encodings = [s["face_encoding"] for s in known_students]
    known_names = [s["name"] for s in known_students]
    known_ids = [s["student_id"] for s in known_students]
    
    matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.5)
    face_distances = face_recognition.face_distance(known_encodings, face_encoding)
    
    if len(face_distances) > 0:
        best_match_index = np.argmin(face_distances)
        if matches[best_match_index]:
            return {
                "student_id": known_ids[best_match_index],
                "name": known_names[best_match_index]
            }
    return None

# ---------------------- Liveness Detection ----------------------
def get_face_info(rgb_image):
    face_locations = face_recognition.face_locations(rgb_image)
    if not face_locations:
        return None, None
    face_loc = face_locations[0]
    landmarks = face_recognition.face_landmarks(rgb_image, [face_loc])
    if landmarks:
        landmarks = landmarks[0]
    else:
        landmarks = None
    return face_loc, landmarks

def compute_eye_aspect_ratio(landmarks):
    if not landmarks or 'left_eye' not in landmarks or 'right_eye' not in landmarks:
        return None
    left_eye = np.array(landmarks['left_eye'])
    right_eye = np.array(landmarks['right_eye'])
    A = np.linalg.norm(left_eye[1] - left_eye[5])
    B = np.linalg.norm(left_eye[2] - left_eye[4])
    C = np.linalg.norm(left_eye[0] - left_eye[3])
    left_ear = (A + B) / (2.0 * C)
    A = np.linalg.norm(right_eye[1] - right_eye[5])
    B = np.linalg.norm(right_eye[2] - right_eye[4])
    C = np.linalg.norm(right_eye[0] - right_eye[3])
    right_ear = (A + B) / (2.0 * C)
    return (left_ear + right_ear) / 2.0

def has_blinked(landmarks):
    ear = compute_eye_aspect_ratio(landmarks)
    return ear is not None and ear < 0.2

def analyze_texture(rgb_image, face_loc):
    top, right, bottom, left = face_loc
    face_roi = rgb_image[top:bottom, left:right]
    gray = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)
    f = fft2(gray)
    fshift = fftshift(f)
    magnitude = 20 * np.log(np.abs(fshift) + 1)
    h, w = magnitude.shape
    center_h, center_w = h//2, w//2
    high_freq_region = magnitude[center_h+10:center_h+50, center_w+10:center_w+50]
    high_freq_mean = np.mean(high_freq_region)
    return high_freq_mean

def passive_liveness_multi(frame_bytes_list):
    """
    Takes list of 5 frames (JPEG bytes). Returns (is_live, score, reason).
    Uses: head movement consistency (no blink required).
    """
    if len(frame_bytes_list) < 3:
        return False, 0, "Not enough frames"
    
    rgb_frames = []
    face_locs = []
    for b in frame_bytes_list:
        nparr = np.frombuffer(b, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return False, 0, "Invalid frame"
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rgb_frames.append(rgb)
        loc, _ = get_face_info(rgb)
        face_locs.append(loc)
    
    if any(loc is None for loc in face_locs):
        return False, 0, "Face not detected in all frames"
    
    # Movement consistency (std dev of face centers)
    centers = []
    for loc in face_locs:
        top, right, bottom, left = loc
        cx = (left + right) / 2
        cy = (top + bottom) / 2
        centers.append((cx, cy))
    centers = np.array(centers)
    movement_std = np.std(centers, axis=0).mean()
    
    # Texture analysis on first frame
    texture_score = analyze_texture(rgb_frames[0], face_locs[0])
    
    # Simple decision: if movement > 1.5 pixels, accept as live
    # Real faces have natural micro-movements; static photos have near-zero movement.
    if movement_std > 1.5:
        return True, movement_std, f"Live (movement={movement_std:.1f}px)"
    else:
        return False, movement_std, f"Static/masked (movement={movement_std:.1f}px, texture={texture_score:.0f})"