import cv2
import threading
cap = cv2.VideoCapture(0)
import numpy as np
from ultralytics import YOLO
import mediapipe as mp
import socket
import base64
import time


HOST, PORT = "localhost", 9999
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.settimeout(5.0)

try:
    client_socket.connect((HOST, PORT))
    print("🔌 Connecté au serveur du jeu.")
except Exception as e:
    print(f"Erreur connexion serveur : {e}")
    exit()

def envoyer_commande(cmd):
    try:
        client_socket.sendall((cmd + "\n").encode('utf-8'))
    except Exception as e:
        print(f"⚠️ Erreur envoi commande: {e}")

# === Modèles ===
model = YOLO("yolov8n-seg.pt")
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
mp_face = mp.solutions.face_detection
face_detector = mp_face.FaceDetection(min_detection_confidence=0.5)

# === ArUco ===
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
aruco_id_target = 0 
# === Variables ===
player_selected = False
selected_bbox = None
face_sent = False
countdown_done = False
iou_threshold = 0.3
frames_lost = 0

GAME_WIDTH, GAME_HEIGHT = 1520, 800

def compute_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2]-boxA[0])*(boxA[3]-boxA[1])
    boxBArea = (boxB[2]-boxB[0])*(boxB[3]-boxB[1])
    return interArea / float(boxAArea + boxBArea - interArea)


if not cap.isOpened():
    print("❌ Erreur : caméra non détectée.")
    exit()

while True:
    ret, frame = cap.read()

    if not ret:
        break

    h, w = frame.shape[:2]
    results = model(frame, verbose=False)[0]

    # === Détection des personnes ===
    bboxes, masks = [], []
    if results.boxes is not None and results.masks is not None:
        for i, box in enumerate(results.boxes.data):
            if int(box[5]) == 0:  # personne
                x1, y1, x2, y2 = map(int, box[:4])
                bboxes.append((x1, y1, x2, y2))
                masks.append(results.masks.data[i].cpu().numpy())

    # === Détection ArUco ===
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=aruco_params)

    if not player_selected:
        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                if marker_id == aruco_id_target:
                    (xA, yA) = corners[i][0][0]
                    (xB, yB) = corners[i][0][2]
                    aruco_center = ((xA+xB)//2, (yA+yB)//2)
                    for bbox in bboxes:
                        if bbox[0] < aruco_center[0] < bbox[2] and bbox[1] < aruco_center[1] < bbox[3]:
                            selected_bbox = bbox
                            player_selected = True
                            face_sent = False
                            frames_lost = 0
                            print("✅ Joueur sélectionné via ArUco")
                            break

    # === Suivi du joueur par bbox ===
    matched = False
    if player_selected and selected_bbox:
        for bbox in bboxes:
            if compute_iou(selected_bbox, bbox) > iou_threshold:
                selected_bbox = bbox
                matched = True
                break

        if not matched:
            frames_lost += 1
            if frames_lost > 10:
                print("❌ Joueur perdu → retour à la recherche ArUco")
                player_selected = False
                selected_bbox = None

    output = cv2.flip(frame, 1)

    if player_selected and selected_bbox:
        # === Segmentation joueur ===
        matched_index = None
        for i, bbox in enumerate(bboxes):
            if bbox == selected_bbox:
                matched_index = i
                break

        if matched_index is not None:
            mask = cv2.resize(masks[matched_index], (w, h))
            segmented = np.zeros_like(frame)
            condition = mask > 0.5
            for c in range(3):
                segmented[:, :, c] = np.where(condition, frame[:, :, c], 0)

            frame_rgb = cv2.cvtColor(segmented, cv2.COLOR_BGR2RGB)
            results_pose = pose.process(frame_rgb)
            output = cv2.flip(segmented, 1)

            # === Capture visage (une seule fois) ===
            if not face_sent:
                face_results = face_detector.process(frame_rgb)
                if face_results.detections:
                    for detection in face_results.detections:
                        bboxC = detection.location_data.relative_bounding_box
                        fx1 = int(bboxC.xmin * w)
                        fy1 = int(bboxC.ymin * h)
                        fx2 = int((bboxC.xmin + bboxC.width) * w)
                        fy2 = int((bboxC.ymin + bboxC.height) * h)
                        face_img = frame[max(0, fy1):min(h, fy2), max(0, fx1):min(w, fx2)]
                        if face_img.size > 0:
                            face_img = cv2.resize(face_img, (200, 200))
                            face_img = cv2.flip(face_img, 1)
                            _, buffer = cv2.imencode('.jpg', face_img)
                            face_data = base64.b64encode(buffer).decode('utf-8')
                            envoyer_commande(f"face:{face_data}")
                            print("📸 Visage capturé et envoyé !")
                            face_sent = True
                        break

            # === Contrôle du jeu ===
            if results_pose.pose_landmarks:
                lm = results_pose.pose_landmarks.landmark
                rwrist = lm[mp_pose.PoseLandmark.RIGHT_WRIST.value]
                rshoulder = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
                lshoulder = lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value]

                if not countdown_done and rwrist.visibility > 0.5 and rshoulder.visibility > 0.5 and rwrist.y < rshoulder.y:
                    print("✋ Main levée ➜ Début du jeu")
                    for i in range(3, 0, -1):
                        frame_countdown = output.copy()
                        cv2.putText(frame_countdown, str(i), (w // 2 - 30, h // 2),
                                    cv2.FONT_HERSHEY_SIMPLEX, 4, (0, 0, 255), 6)
                        cv2.imshow("Detection", frame_countdown)
                        cv2.waitKey(1000)
                    envoyer_commande("start")
                    countdown_done = True

                if countdown_done:
                    if lshoulder.visibility > 0.5 and rshoulder.visibility > 0.5:
                        center_x = (lshoulder.x + rshoulder.x) / 2
                        pos_x = int((1 - center_x) * GAME_WIDTH)
                        envoyer_commande(f"x:{pos_x}")

        cv2.putText(output, "🎯 Joueur suivi", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    else:
        cv2.putText(output, "⛔ Recherche joueur (ArUco)...", (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    cv2.imshow("Detection", output)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
client_socket.close()
cv2.destroyAllWindows()
