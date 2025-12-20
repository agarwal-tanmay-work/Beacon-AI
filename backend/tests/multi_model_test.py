"""
Test gemini-pro which might have separate quota
"""
import google.generativeai as genai

API_KEY = "AIzaSyAuXMtZchaq1l-pZ29RN_qTLRlc6GgeEZI"

print("=== TESTING DIFFERENT MODELS ===")
genai.configure(api_key=API_KEY)

models_to_try = [
    "gemini-pro",
    "gemini-1.5-flash",
    "gemini-1.0-pro",
]

for model_name in models_to_try:
    print(f"\n--- Testing {model_name} ---")
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Hi")
        print(f"✅ SUCCESS: {response.text[:50]}...")
        print(f"\n>>> WORKING MODEL FOUND: {model_name} <<<")
        break
    except Exception as e:
        error_type = type(e).__name__
        print(f"❌ {error_type}")
        if "429" in str(e) or "ResourceExhausted" in str(e):
            print("   (Quota exceeded)")
        elif "404" in str(e):
            print("   (Model not found)")
        else:
            print(f"   {str(e)[:100]}")
