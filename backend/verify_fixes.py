import re
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Mocking parts of the app for local testing
class MockReportEngine:
    @staticmethod
    def fix_response(llm_response, case_id, secret_key_display):
        print(f"DEBUG: Initial: {repr(llm_response)}")
        
        # Logic from report_engine.py
        llm_response = re.sub(r"CASE_ID_(PLACEHOLDER|\d+)", case_id, llm_response, flags=re.IGNORECASE)
        print(f"DEBUG: After 1st sub: {repr(llm_response)}")
        
        llm_response = re.sub(r"SECRET_KEY_(PLACEHOLDER|\d+)", secret_key_display, llm_response, flags=re.IGNORECASE)
        print(f"DEBUG: After 2nd sub: {repr(llm_response)}")
        
        llm_response = re.sub(r"(Case ID is:?\s*)([A-Z0-9_-]+)", rf"\g<1>{case_id}", llm_response, flags=re.I)
        print(f"DEBUG: After 3rd sub: {repr(llm_response)}")
        
        llm_response = re.sub(r"(Secret Key is:?\s*)([A-Z0-9_-]+)", rf"\g<1>{secret_key_display}", llm_response, flags=re.I)
        print(f"DEBUG: After 4th sub: {repr(llm_response)}")

        if secret_key_display not in llm_response:
            llm_response = llm_response.rstrip()
            if not llm_response.endswith("."):
                llm_response += "."
            llm_response += f"\n\nYour Secret Key is {secret_key_display}. Please save this."
            print(f"DEBUG: After safety net: {repr(llm_response)}")
        
        return llm_response

def test_regex():
    case_id = "BCN-1234"
    secret_key = "8EF5-F40B"
    
    test_cases = [
        # 1. The original problematic message
        {
            "input": """Thank you for your courage in reporting this.
Your Case ID is: CASE_ID_1234
Your Secret Key is: SECRET_KEY_5678
IMPORTANT: Please save both of these safely to track your case status. We will investigate and take appropriate action. You've done the right thing by speaking up.""",
            "desc": "Original problematic message"
        },
        # 2. Standard placeholder
        {
            "input": "Your Case ID is: CASE_ID_PLACEHOLDER\nYour Secret Key is: SECRET_KEY_PLACEHOLDER",
            "desc": "Standard placeholders"
        },
        # 3. No placeholders (safety net check)
        {
            "input": "Thank you for reporting. Your case is being investigated.",
            "desc": "No placeholders (Safety net)"
        },
        # 4. Partial replacement (shouldn't happen with LLM but let's be robust)
        {
            "input": f"Case ID: {case_id}\nSecret Key: SECRET_KEY_PLACEHOLDER",
            "desc": "Partial placeholders"
        }
    ]

    with open("debug_regex_output.txt", "w") as f:
        for tc in test_cases:
            f.write(f"\n--- Testing: {tc['desc']} ---\n")
            output = MockReportEngine.fix_response(tc['input'], case_id, secret_key)
            f.write(f"Output: {repr(output)}\n")
            f.write(f"Checking for case_id: {repr(case_id)}\n")
            
            found_case = case_id in output
            found_key = secret_key in output
            f.write(f"Case ID found: {found_case}\n")
            f.write(f"Secret Key found: {found_key}\n")
            
            if not found_case:
                f.write(f"FAILED: Case ID {case_id} not found\n")
            
            assert found_case, f"Case ID {case_id} not found in output"
            assert found_key, f"Secret Key {secret_key} not found in output"
            
            occurrences = len(re.findall(re.escape(secret_key), output))
            f.write(f"Occurrences of secret key: {occurrences}\n")
            assert occurrences == 1, f"Secret key found {occurrences} times instead of 1"
            f.write("PASSED\n")
    print("Done. Results in debug_regex_output.txt")

if __name__ == "__main__":
    test_regex()
