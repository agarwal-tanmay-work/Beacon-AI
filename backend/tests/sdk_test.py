"""
Test using official Google generativeai SDK
"""
import google.generativeai as genai

API_KEY = "AIzaSyAuXMtZchaq1l-pZ29RN_qTLRlc6GgeEZI"

print("=== TESTING WITH OFFICIAL GOOGLE SDK ===")
print(f"API Key: {API_KEY[:15]}...")

try:
    genai.configure(api_key=API_KEY)
    
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    print("Sending request...")
    response = model.generate_content("Say hello in one word")
    
    print(f"\n✅ SUCCESS!")
    print(f"Response: {response.text}")
    
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}")
    print(f"Message: {e}")
