
import asyncio
import sys
import os
import json
from termcolor import colored

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Manually load backend_config.env
from pathlib import Path
env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "backend_config.env"
if env_path.exists():
    print(f"Loading env from {env_path}")
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip("'").strip('"')

from app.services.llm_agent import LLMAgent

async def test_flow_scenario(name, user_inputs, expected_to_avoid=None, expected_to_ask=None):
    print(colored(f"\n--- TESTING SCENARIO: {name} ---", "cyan"))
    
    history = []
    state = {}
    
    for i, user_input in enumerate(user_inputs):
        print(colored(f"User: {user_input}", "green"))
        history.append({"role": "user", "content": user_input})
        
        response, state = await LLMAgent.chat(history, state)
        
        print(colored(f"Agent: {response}", "yellow"))
        history.append({"role": "assistant", "content": response})
        
        # Check assertions
        if expected_to_avoid:
            for phrase in expected_to_avoid:
               if phrase.lower() in response.lower():
                   print(colored(f"FAILED: Agent asked redundant question: '{phrase}'", "red"))
                   return False

    if expected_to_ask:
        found = False
        last_response = history[-1]["content"].lower()
        for phrase in expected_to_ask:
            if phrase.lower() in last_response:
                found = True
        if not found:
             print(colored(f"FAILED: Agent did not ask expected question. Expected one of: {expected_to_ask}", "red"))
             return False

    print(colored(f"PASSED: {name}", "green"))
    return True

async def run_tests():
    # Scenario 1: One Shot (User gives everything at once)
    # Goal: Agent should NOT ask for What, Where, When, Who. Should move to Evidence or Contact.
    scenario_1 = await test_flow_scenario(
        "One Shot - All Details Provided",
        ["I saw Officer Sharma taking a bribe at the Andheri Station yesterday at 5 PM."],
        expected_to_avoid=["Where", "When did this happen", "What happened", "details"],
        expected_to_ask=["evidence", "photo", "recording", "upload", "proof"]
    )

    # Scenario 2: Skipping Location
    # Goal: User says skip, Agent should move to next topic (Time/Who)
    scenario_2 = await test_flow_scenario(
        "Skipping A Field",
        [
            "I want to report corruption.", 
            "Someone asked for money.", 
            "skip" # In response to "Where?"
        ],
        expected_to_avoid=["Please provide the location"], 
        expected_to_ask=["When", "Time", "Who"] # Should move on
    )
    
    # Scenario 3: Date Provided, Time Missing
    # Goal: Agent should only ask for Time, not Date
    scenario_3 = await test_flow_scenario(
        "Date Provided, Time Missing",
        [
            "I saw something bad.",
            "It happened on Jan 25th 2026."
        ],
        expected_to_avoid=["What date"],
        expected_to_ask=["Time"]
    )
    
    # Scenario 4: Vague Narrative
    # Goal: Agent should reject "corruption" and ask for details
    scenario_4 = await test_flow_scenario(
        "Vague Narrative Handling",
        [
            "I want to report an incident.", 
            "Corruption happened."
        ],
        expected_to_avoid=["Where did it happen"], # Should not move to Where yet
        expected_to_ask=["details", "specific", "elaborate"] # Should press for What
    )

    # Scenario 5: Persistence on Location
    # Goal: User ignores "Where", Agent should re-ask "Where"
    scenario_5 = await test_flow_scenario(
        "Persistence on Location",
        [
            "I saw Officer Sharma take a bribe yesterday.", # Provides What, Who, When. Missing Where.
            "He took 500 rupees." # User ignores "Where?" question
        ],
        expected_to_avoid=["When", "Time"], # Should not move to Time
        expected_to_ask=["Where", "location", "address", "building", "city", "place"] # Must re-ask Where
    )

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_tests())
