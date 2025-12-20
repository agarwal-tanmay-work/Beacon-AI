import io
import os
import cv2
import numpy as np
from PIL import Image
import structlog

logger = structlog.get_logger()

class MediaCleaner:
    """
    Handles image sanitization:
    1. Strips Metadata (EXIF)
    2. Blurs Faces (using OpenCV Haarcascades)
    """

    @staticmethod
    def clean_image(image_bytes: bytes) -> bytes:
        """
        Process image bytes: Strip EXIF and Blur Faces.
        Returns cleaned image bytes (always converted to JPEG).
        """
        try:
            # 1. Load into OpenCV for Face Blurring
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                raise ValueError("Could not decode image")

            # Face Detection
            # Load standard hare cascade
            # Note: In a real docker container, we'd ensure this xml is present. 
            # We use the built-in path from cv2 if available or fail gracefully.
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_cascade = cv2.CascadeClassifier(cascade_path)
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            
            # Blur Faces
            for (x, y, w, h) in faces:
                # Region of interest
                roi = img[y:y+h, x:x+w]
                # Apply heavy blur
                roi = cv2.GaussianBlur(roi, (99, 99), 30)
                # Put back
                img[y:y+h, x:x+w] = roi

            # 2. Convert back to Bytes (stripping metadata effectively by re-encoding)
            success, encoded_img = cv2.imencode('.jpg', img)
            if not success:
                raise ValueError("Could not encode cleaned image")
            
            return encoded_img.tobytes()

        except Exception as e:
            logger.error("media_cleaning_failed", error=str(e))
            # Fallback: Just simple PIL metadata strip if OpenCV fails
            return MediaCleaner._strip_metadata_only(image_bytes)

    @staticmethod
    def _strip_metadata_only(image_bytes: bytes) -> bytes:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            data = list(img.getdata())
            image_without_exif = Image.new(img.mode, img.size)
            image_without_exif.putdata(data)
            
            out_buffer = io.BytesIO()
            image_without_exif.save(out_buffer, format="JPEG")
            return out_buffer.getvalue()
        except Exception as e:
            logger.error("metadata_strip_failed", error=str(e))
            raise e
