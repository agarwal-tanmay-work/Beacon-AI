
import asyncio
import base64
from app.services.ai_service import GroqService
import os

async def test_vision():
    path = 'C:/Users/priya/.gemini/antigravity/brain/f3097c31-91ff-4164-a5b0-4f0ce40f14e1/uploaded_image_1767966225041.png'
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, "rb") as f:
        img_bytes = f.read()
    
    print("Running vision analysis...")
    desc = await GroqService.perform_forensic_visual_analysis(img_bytes, "image/png")
    print(f"Vision Description: {desc}")

if __name__ == "__main__":
    asyncio.run(test_vision())
