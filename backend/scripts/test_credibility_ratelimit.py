"""
Rate-Limit Aware Credibility Scoring Test
Runs 5 iterations per scenario with proper backoff delays
"""
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.ai import EvidenceMetadata, EvidenceType

# Simplified test scenarios
SCENARIOS = [
    # LOW scenarios
    {
        "name": "LOW - Vague + No Evidence",
        "chat": [
            {"role": "user", "content": "I saw corruption."},
            {"role": "assistant", "content": "Can you tell me more?"},
            {"role": "user", "content": "Someone took money."}
        ],
        "evidence": [],
        "expected_max": 33,
        "category": "LOW"
    },
    {
        "name": "LOW - Unrelated Evidence",
        "chat": [
            {"role": "user", "content": "Traffic cop asked for bribe."},
            {"role": "assistant", "content": "Do you have evidence?"},
            {"role": "user", "content": "Yes a photo."}
        ],
        "evidence": [EvidenceMetadata(
            file_name="cat.jpg", file_path="cat.jpg", file_type=EvidenceType.IMAGE,
            object_labels=["sharp_high_clarity_image"], has_relevant_keywords=False
        )],
        "expected_max": 33,
        "category": "LOW"
    },
    # MEDIUM scenario
    {
        "name": "MEDIUM - Details + No Evidence",
        "chat": [
            {"role": "user", "content": "On Jan 20, 2026 at RTO Mumbai, Officer Sharma badge 4521 asked for Rs 2000."},
            {"role": "assistant", "content": "Do you have evidence?"},
            {"role": "user", "content": "No, I didn't record it."}
        ],
        "evidence": [],
        "expected_min": 20,
        "expected_max": 50,
        "category": "MEDIUM"
    },
    # HIGH scenario
    {
        "name": "HIGH - Strong Evidence",
        "chat": [
            {"role": "user", "content": "Sub-Registrar Krishnamurthy at Jayanagar Bangalore demanded Rs 10000 on Jan 25, 2026. I have audio of him asking."},
            {"role": "assistant", "content": "What does the recording say?"},
            {"role": "user", "content": "He says give 10000 or file stuck for months."}
        ],
        "evidence": [
            EvidenceMetadata(
                file_name="audio.mp3", file_path="audio.mp3", file_type=EvidenceType.AUDIO,
                audio_transcript_snippet="Give me ten thousand rupees or your file will be stuck for months.",
                has_relevant_keywords=True
            ),
            EvidenceMetadata(
                file_name="nameplate.jpg", file_path="nameplate.jpg", file_type=EvidenceType.IMAGE,
                ocr_text_snippet="Sri Krishnamurthy - Sub Registrar, Jayanagar",
                object_labels=["sharp_high_clarity_image", "signal: possible_document_layout"],
                has_relevant_keywords=True
            )
        ],
        "expected_min": 60,
        "expected_max": 100,
        "category": "HIGH"
    }
]

async def run_test():
    from app.services.ai_service import GroqService
    
    print("=" * 60)
    print("CREDIBILITY SCORING TEST (Rate-Limit Aware)")
    print(f"Started: {datetime.now()}")
    print("=" * 60)
    
    results = []
    ITERATIONS = 5
    BASE_DELAY = 8  # Start with 8 seconds between calls
    
    for scenario in SCENARIOS:
        print(f"\n[{scenario['name']}]")
        scores = []
        
        for i in range(ITERATIONS):
            # Exponential backoff delay
            delay = BASE_DELAY + (i * 2)
            if i > 0:
                print(f"  Waiting {delay}s for rate limit...")
                await asyncio.sleep(delay)
            
            try:
                result, retry_after = await GroqService.calculate_credibility_score(
                    scenario["chat"],
                    scenario["evidence"],
                    {"evidence_count": len(scenario["evidence"]), "timestamp": str(datetime.now())},
                    timeout=45.0
                )
                
                if result:
                    scores.append(result.credibility_score)
                    print(f"  Run {i+1}: Score={result.credibility_score}%, Confidence={result.confidence_level}")
                elif retry_after:
                    print(f"  Run {i+1}: Rate limited, waiting {retry_after}s...")
                    await asyncio.sleep(retry_after + 3)
                    # Retry
                    result, _ = await GroqService.calculate_credibility_score(
                        scenario["chat"], scenario["evidence"],
                        {"evidence_count": len(scenario["evidence"])}, timeout=45.0
                    )
                    if result:
                        scores.append(result.credibility_score)
                        print(f"  Run {i+1} (retry): Score={result.credibility_score}%")
                else:
                    print(f"  Run {i+1}: ERROR")
            except Exception as e:
                print(f"  Run {i+1}: ERROR - {str(e)[:40]}")
        
        if scores:
            avg = sum(scores) / len(scores)
            in_range = all(
                (scenario.get("expected_min", 0) <= s <= scenario.get("expected_max", 100))
                for s in scores
            )
            results.append({
                "name": scenario["name"],
                "category": scenario["category"],
                "scores": scores,
                "avg": avg,
                "min": min(scores),
                "max": max(scores),
                "in_range": in_range,
                "expected": f"{scenario.get('expected_min', 0)}-{scenario['expected_max']}%"
            })
            status = "PASS" if in_range else "FAIL"
            print(f"  Summary: Avg={avg:.1f}%, Range={min(scores)}-{max(scores)}%, {status}")
    
    # Generate Report
    print("\n" + "=" * 60)
    print("TEST REPORT")
    print("=" * 60)
    
    report = ["# Credibility Scoring Test Report", f"\nGenerated: {datetime.now()}\n"]
    report.append("## Summary\n")
    report.append("| Category | Scenario | Runs | Avg | Min-Max | Expected | Result |")
    report.append("|----------|----------|------|-----|---------|----------|--------|")
    
    for r in results:
        status = "PASS" if r["in_range"] else "FAIL"
        report.append(f"| {r['category']} | {r['name'].split(' - ')[1]} | {len(r['scores'])} | {r['avg']:.0f}% | {r['min']}-{r['max']}% | {r['expected']} | {status} |")
    
    report.append("\n## Detailed Scores\n")
    for r in results:
        report.append(f"**{r['name']}**: {r['scores']}")
    
    report_text = "\n".join(report)
    print(report_text)
    
    # Save report
    report_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "credibility_test_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\nSaved to: {report_path}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_test())
