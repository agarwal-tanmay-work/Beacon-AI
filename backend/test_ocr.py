
import pytesseract
from PIL import Image, ImageDraw
import io

# Set path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Create image with text
img = Image.new('RGB', (400, 100), color=(255, 255, 255))
d = ImageDraw.Draw(img)
d.text((10, 40), "CORRUPTION EVIDENCE 12345", fill=(0, 0, 0))

# Save to bytes
img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# OCR
print("Running Tesseract OCR...")
text = pytesseract.image_to_string(Image.open(img_bytes))
print(f"Extracted Text: '{text.strip()}'")
if "CORRUPTION" in text:
    print("✅ SUCCESS")
else:
    print("❌ FAILED")
