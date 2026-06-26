import os
import cv2
import numpy as np
import base64
import json

# Absolute paths for ONNX models
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DETECTOR_PATH = os.path.join(BASE_DIR, "face_detection_yunet_2023mar.onnx")
RECOGNIZER_PATH = os.path.join(BASE_DIR, "face_recognition_sface_2021dec.onnx")

# Standard threshold for SFace cosine similarity match
COSINE_THRESHOLD = 0.42

# Caching instances of detectors/recognizers to avoid reloading files on every request
_detector_instance = None
_recognizer_instance = None

def get_detector():
    global _detector_instance
    if _detector_instance is None:
        if not os.path.exists(DETECTOR_PATH):
            raise FileNotFoundError(f"Model file YuNet not found at {DETECTOR_PATH}")
        # Note: input_size will be set dynamically before detection
        _detector_instance = cv2.FaceDetectorYN.create(
            model=DETECTOR_PATH,
            config="",
            input_size=(320, 320),
            score_threshold=0.8, # slightly lower threshold for better recall in sub-optimal lighting
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
    """
    Decodes a base64 encoded image string (with or without HTML5 canvas headers) 
    and returns a cv2 BGR image.
    """
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

def extract_face_embedding(img):
    """
    Detects a single face in the image, aligns/crops it, and extracts the 128-d embedding vector.
    Returns:
        list of floats: 128-dimensional embedding vector.
    Raises:
        ValueError if face detection or alignment fails.
    """
    detector = get_detector()
    recognizer = get_recognizer()
    
    # Update input size to match current image shape
    h, w, _ = img.shape
    detector.setInputSize((w, h))
    
    retval, faces = detector.detect(img)
    
    if faces is None or len(faces) == 0:
        raise ValueError("No se detectó ningún rostro en la imagen. Asegúrate de estar frente a la cámara en un entorno iluminado.")
    
    if len(faces) > 1:
        raise ValueError("Se detectó más de un rostro. Por favor, asegúrate de que solo haya una persona visible.")
    
    # faces[0] has coordinates and landmarks
    face = faces[0]
    
    try:
        aligned_face = recognizer.alignCrop(img, face)
        embedding = recognizer.feature(aligned_face)
        # embedding is shape (1, 128), convert to 1D list of floats
        return embedding[0].tolist()
    except Exception as e:
        raise ValueError(f"Error al procesar y alinear el rostro: {str(e)}")

def get_embedding_from_base64(base64_str):
    """
    Wrapper that decodes base64 and extracts the embedding.
    """
    img = decode_base64_image(base64_str)
    return extract_face_embedding(img)

def compare_embeddings(embedding1, embedding2):
    """
    Compares two embeddings (lists of floats) using SFace Cosine similarity.
    Returns:
        float: Cosine similarity score (higher is more similar, typically 1.0 is identical).
    """
    recognizer = get_recognizer()
    feat1 = np.array([embedding1], dtype=np.float32)
    feat2 = np.array([embedding2], dtype=np.float32)
    score = recognizer.match(feat1, feat2, cv2.FaceRecognizerSF_FR_COSINE)
    return float(score)

def check_match(embedding1, embedding2):
    """
    Checks if two embeddings represent the same person based on SFace similarity threshold.
    """
    score = compare_embeddings(embedding1, embedding2)
    return score >= COSINE_THRESHOLD, score
