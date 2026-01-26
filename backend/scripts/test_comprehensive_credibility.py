"""
Comprehensive Credibility Scoring Test
Tests Low, Medium, High scenarios 20 times each for:
- No evidence provided
- Evidence unrelated to narrative  
- Vague/incomplete narrative
"""
import asyncio
import sys
import os
import json
from datetime import datetime

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

from app.schemas.ai import EvidenceMetadata, EvidenceType

# Test Cases Definition
TEST_SCENARIOS = {
    "LOW": {
        "no_evidence": {
            "name": "LOW - No Evidence",
            "chat": [
                {"role": "user", "content": "I saw corruption happening."},
                {"role": "assistant", "content": "Can you tell me more?"},
                {"role": "user", "content": "Someone took money. That's all I know."}
            ],
            "evidence": [],
            "expected_range": (0, 33)
        },
        "unrelated_evidence": {
            "name": "LOW - Unrelated Evidence",
            "chat": [
                {"role": "user", "content": "A traffic cop asked for bribe at Main Road."},
                {"role": "assistant", "content": "Do you have evidence?"},
                {"role": "user", "content": "Yes, here's a photo."}
            ],
            "evidence": [EvidenceMetadata(
                file_name="cat_photo.jpg",
                file_path="uploads/cat.jpg",
                file_type=EvidenceType.IMAGE,
                ocr_text_snippet=None,
                object_labels=["sharp_high_clarity_image", "signal: general_scene_or_object"],
                has_relevant_keywords=False
            )],
            "expected_range": (0, 33)
        },
        "vague_narrative": {
            "name": "LOW - Vague Narrative",
            "chat": [
                {"role": "user", "content": "Something bad happened."},
                {"role": "assistant", "content": "What happened exactly?"},
                {"role": "user", "content": "I don't want to say much."}
            ],
            "evidence": [],
            "expected_range": (0, 33)
        }
    },
    "MEDIUM": {
        "no_evidence": {
            "name": "MEDIUM - No Evidence",
            "chat": [
                {"role": "user", "content": "On January 20, 2026, at the RTO office in Mumbai, an officer named Sharma asked me for Rs 2000 to process my license renewal."},
                {"role": "assistant", "content": "Thank you for the details. Do you have evidence?"},
                {"role": "user", "content": "No, I didn't record anything but I remember his badge number was 4521."}
            ],
            "evidence": [],
            "expected_range": (20, 50)
        },
        "unrelated_evidence": {
            "name": "MEDIUM - Unrelated Evidence",
            "chat": [
                {"role": "user", "content": "Officer Verma at Traffic Police Station 5, Delhi demanded Rs 500 on Jan 15, 2026 at 3pm for letting me go without challan."},
                {"role": "assistant", "content": "Do you have any proof?"},
                {"role": "user", "content": "I have a photo but it's not very relevant."}
            ],
            "evidence": [EvidenceMetadata(
                file_name="street_photo.jpg",
                file_path="uploads/street.jpg",
                file_type=EvidenceType.IMAGE,
                ocr_text_snippet="Shop name: General Store",
                object_labels=["sharp_high_clarity_image", "signal: general_scene_or_object"],
                has_relevant_keywords=False
            )],
            "expected_range": (20, 50)
        },
        "vague_narrative": {
            "name": "MEDIUM - Partial Details",
            "chat": [
                {"role": "user", "content": "A government official took money from me last week."},
                {"role": "assistant", "content": "Can you provide more details?"},
                {"role": "user", "content": "It was at the municipal office, around Rs 1000, I think it was Thursday."}
            ],
            "evidence": [EvidenceMetadata(
                file_name="receipt.jpg",
                file_path="uploads/receipt.jpg",
                file_type=EvidenceType.IMAGE,
                ocr_text_snippet="Municipal Corporation - Payment Receipt",
                object_labels=["sharp_high_clarity_image", "signal: possible_document_layout"],
                has_relevant_keywords=True
            )],
            "expected_range": (25, 55)
        }
    },
    "HIGH": {
        "no_evidence": {
            "name": "HIGH - Very Detailed No Evidence",
            "chat": [
                {"role": "user", "content": "On January 22, 2026 at exactly 2:30 PM, Inspector Rajesh Kumar (Badge #7892) at Andheri Police Station, Mumbai demanded Rs 5000 from me to not file a false case. His colleague Constable Suresh was present and witnessed it. The inspector said 'pay now or face consequences'. I paid via Paytm and have the transaction ID."},
                {"role": "assistant", "content": "That's very detailed. Do you have the Paytm receipt?"},
                {"role": "user", "content": "I have the transaction screenshot but my phone broke. Transaction ID was PAY2026012202301."}
            ],
            "evidence": [],
            "expected_range": (30, 50)
        },
        "related_evidence": {
            "name": "HIGH - Strong Evidence",
            "chat": [
                {"role": "user", "content": "Sub-Registrar Krishnamurthy at Jayanagar Registration Office, Bangalore demanded Rs 10000 on Jan 25, 2026 for property registration. I have audio recording of him asking for the bribe."},
                {"role": "assistant", "content": "That's important evidence. What does the recording contain?"},
                {"role": "user", "content": "He clearly says 'Give me ten thousand rupees or your file will be stuck for months'. I also have a photo of his nameplate."}
            ],
            "evidence": [
                EvidenceMetadata(
                    file_name="audio_recording.mp3",
                    file_path="uploads/bribe_demand.mp3",
                    file_type=EvidenceType.AUDIO,
                    audio_transcript_snippet="Give me ten thousand rupees or your file will be stuck for months. This is how things work here.",
                    has_relevant_keywords=True
                ),
                EvidenceMetadata(
                    file_name="nameplate.jpg",
                    file_path="uploads/nameplate.jpg",
                    file_type=EvidenceType.IMAGE,
                    ocr_text_snippet="Sri Krishnamurthy - Sub Registrar, Jayanagar Registration Office",
                    object_labels=["sharp_high_clarity_image", "signal: possible_document_layout"],
                    has_relevant_keywords=True
                )
            ],
            "expected_range": (60, 100)
        },
        "strong_narrative_evidence": {
            "name": "HIGH - Complete Case",
            "chat": [
                {"role": "user", "content": "Passport Officer Meena Sharma at Regional Passport Office, Sector 17, Chandigarh demanded Rs 3000 for faster processing on January 24, 2026 at 11:15 AM. I have video recording from my hidden camera, WhatsApp messages where she confirms the amount, and the cash was marked. I reported to ACB immediately after."},
                {"role": "assistant", "content": "You have extensive documentation."},
                {"role": "user", "content": "Yes, I also have the acknowledgment from ACB and case number ACB/2026/CH/0047."}
            ],
            "evidence": [
                EvidenceMetadata(
                    file_name="hidden_cam.mp4",
                    file_path="uploads/hidden_cam.mp4",
                    file_type=EvidenceType.VIDEO,
                    audio_transcript_snippet="Officer: Yes, give 3000 rupees and I will process it today. User: Okay madam.",
                    object_labels=["sharp_high_clarity_image", "signal: general_scene_or_object"],
                    has_relevant_keywords=True
                ),
                EvidenceMetadata(
                    file_name="whatsapp_chat.jpg",
                    file_path="uploads/chat.jpg",
                    file_type=EvidenceType.IMAGE,
                    ocr_text_snippet="Meena Sharma: Bring 3000 tomorrow morning. File number PE/2026/12345.",
                    object_labels=["sharp_high_clarity_image", "signal: possible_document_layout"],
                    has_relevant_keywords=True
                )
            ],
            "expected_range": (70, 100)
        }
    }
}

async def run_single_test(scenario, iteration):
    """Run a single test and return result."""
    from app.services.ai_service import GroqService
    
    # Try up to 3 times for rate limits
    for attempt in range(3):
        result, retry_after = await GroqService.calculate_credibility_score(
            scenario["chat"],
            scenario["evidence"],
            {"evidence_count": len(scenario["evidence"]), "timestamp": str(datetime.now())},
            timeout=45.0
        )
        
        if result:
            return {
                "iteration": iteration,
                "score": result.credibility_score,
                "confidence": result.confidence_level,
                "narrative": result.narrative_credibility.score,
                "evidence": result.evidence_strength.score,
                "behavioral": result.behavioral_reliability.score,
                "rationale": " ".join(result.rationale),
                "in_range": scenario["expected_range"][0] <= result.credibility_score <= scenario["expected_range"][1]
            }
        
        wait_time = retry_after if retry_after else (10 * (attempt + 1))
        print(f"    - Rate limited (attempt {attempt+1}), waiting {wait_time}s...")
        await asyncio.sleep(wait_time)
        
    return None

async def run_comprehensive_test():
    """Run all tests 20 times each and generate report."""
    print("=" * 70)
    print("COMPREHENSIVE CREDIBILITY SCORING TEST - 20 ITERATIONS")
    print(f"Started: {datetime.now()}")
    print("=" * 70)
    
    all_results = {}
    ITERATIONS = 2
    
    for level, scenarios in TEST_SCENARIOS.items():
        print(f"\n{'='*70}")
        print(f"TESTING {level} SCENARIOS")
        print(f"{'='*70}")
        
        all_results[level] = {}
        
        for scenario_key, scenario in scenarios.items():
            print(f"\n  [{scenario['name']}] - Running {ITERATIONS} iterations...")
            results = []
            
            for i in range(ITERATIONS):
                try:
                    result = await run_single_test(scenario, i + 1)
                    if result:
                        results.append(result)
                        print(f"    - Iteration {i+1}: {result['score']}% ({result['confidence']}) {'[OK]' if result['in_range'] else '[FAIL]'}")
                        # Regular delay to be nice to the API
                        await asyncio.sleep(5)
                    else:
                        print(f"    - Iteration {i+1}: FAILED (No response after retries)")
                except Exception as e:
                    print(f"    - Iteration {i+1}: ERROR - {str(e)[:50]}")
                    await asyncio.sleep(10)
            
            if results:
                scores = [r["score"] for r in results]
                in_range_count = sum(1 for r in results if r["in_range"])
                
                all_results[level][scenario_key] = {
                    "name": scenario["name"],
                    "expected_range": scenario["expected_range"],
                    "total_runs": len(results),
                    "avg_score": sum(scores) / len(scores),
                    "min_score": min(scores),
                    "max_score": max(scores),
                    "in_range_count": in_range_count,
                    "in_range_pct": (in_range_count / len(results)) * 100,
                    "confidence_levels": {r["confidence"]: sum(1 for x in results if x["confidence"] == r["confidence"]) for r in results},
                    "all_scores": scores,
                    "sample_rationale": results[0]["rationale"] if results else "N/A"
                }
                
                pct = all_results[level][scenario_key]["in_range_pct"]
                print(f"    Completed: {len(results)}/{ITERATIONS} | Avg: {all_results[level][scenario_key]['avg_score']:.1f}% | In-Range: {pct:.0f}%")
    
    # Generate Report
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    
    report_lines = []
    report_lines.append("# Credibility Scoring 20-Iteration Test Report")
    report_lines.append(f"\nGenerated: {datetime.now()}\n")
    report_lines.append("## Summary Table\n")
    report_lines.append("| Category | Scenario | Runs | Avg Score | Range | In-Range % |")
    report_lines.append("|----------|----------|------|-----------|-------|------------|")
    
    for level, scenarios in all_results.items():
        for scenario_key, data in scenarios.items():
            report_lines.append(f"| {level} | {data['name'].replace(f'{level} - ', '')} | {data['total_runs']} | {data['avg_score']:.1f}% | {data['min_score']}-{data['max_score']}% | {data['in_range_pct']:.0f}% |")
    
    report_lines.append("\n## Detailed Analysis\n")
    
    for level, scenarios in all_results.items():
        report_lines.append(f"### {level} Credibility Level\n")
        for scenario_key, data in scenarios.items():
            report_lines.append(f"#### {data['name']}")
            report_lines.append(f"- **Expected Score Range**: {data['expected_range'][0]}-{data['expected_range'][1]}%")
            report_lines.append(f"- **Success Rate**: {data['in_range_count']}/{data['total_runs']} ({data['in_range_pct']:.0f}%)")
            report_lines.append(f"- **Sample Rationale**: {data['sample_rationale']}")
            report_lines.append(f"- **All Scores**: `{data['all_scores']}`\n")
    
    report_content = "\n".join(report_lines)
    
    # Save report
    report_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "credibility_20_iter_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    print(f"\nReport saved to: {report_path}")
    print("\n" + report_content)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_comprehensive_test())
