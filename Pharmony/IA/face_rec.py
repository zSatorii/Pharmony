import base64
import os

import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DETECTOR_PATH = os.path.join(BASE_DIR, "face_detection_yunet_2023mar.onnx")
RECOGNIZER_PATH = os.path.join(BASE_DIR, "face_recognition_sface_2021dec.onnx")

COSINE_THRESHOLD = 0.42

_detector_instance = None
_recognizer_instance = None


def get_detector():
    global _detector_instance
    if _detector_instance is None:
        if not os.path.exists(DETECTOR_PATH):
            raise FileNotFoundError(f"Model file YuNet not found at {DETECTOR_PATH}")
        _detector_instance = cv2.FaceDetectorYN.create(
            model=DETECTOR_PATH,
            config="",
            input_size=(320, 320),
            score_threshold=0.8,
            nms_threshold=0.3,
            top_k=5000
        )
    return _detector_instance


def get_recognizer():
    global _recognizer_instance
    if _recognizer_instance is None:
        if not os.path.exists(RECOGNIZER_PATH):
            raise FileNotFoundError(f"Model file SFace not found at {RECOGNIZER_PATH}")
        _recognizer_instance = cv2.FaceRecognizerSF.create(
            model=RECOGNIZER_PATH,
            config=""
        )
    return _recognizer_instance


def decode_base64_image(base64_str):
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    
    try:
        img_data = base64.b64decode(base64_str)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Decoded image is empty or invalid format")
        return img
    except Exception as e:
        raise ValueError(f"Failed to decode base64 image: {str(e)}")


try:
    cv2.setNumThreads(4)
except Exception:
    pass


def extract_face_embedding(img):
    detector = get_detector()
    recognizer = get_recognizer()
    
    h, w, _ = img.shape
    
    max_dim = 640
    scale = 1.0
    detect_img = img
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        new_w = int(w * scale)
        new_h = int(h * scale)
        detect_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        detector.setInputSize((new_w, new_h))
    else:
        detector.setInputSize((w, h))
    
    retval, faces = detector.detect(detect_img)
    
    if faces is None or len(faces) == 0:
        raise ValueError("No se detectó ningún rostro en la imagen. Asegúrate de estar frente a la cámara en un entorno iluminado.")
    
    if len(faces) > 1:
        raise ValueError("Se detectó más de un rostro. Por favor, asegúrate de que solo haya una persona visible.")
    
    face = faces[0]
    
    if scale != 1.0:
        face = face.copy()
        face /= scale
    
    try:
        aligned_face = recognizer.alignCrop(img, face)
        embedding = recognizer.feature(aligned_face)
        return embedding[0].tolist()
    except Exception as e:
        raise ValueError(f"Error al procesar y alinear el rostro: {str(e)}")


def get_embedding_from_base64(base64_str):
    img = decode_base64_image(base64_str)
    return extract_face_embedding(img)


def compare_embeddings(embedding1, embedding2):
    recognizer = get_recognizer()
    feat1 = np.array([embedding1], dtype=np.float32)
    feat2 = np.array([embedding2], dtype=np.float32)
    score = recognizer.match(feat1, feat2, cv2.FaceRecognizerSF_FR_COSINE)
    return float(score)


def check_match(embedding1, embedding2):
    score = compare_embeddings(embedding1, embedding2)
    return score >= COSINE_THRESHOLD, score
