import os
import json
from pathlib import Path
from redteam.gemini_audio_eval import GeminiAudioEvaluator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "artifacts" / "specs" / "l1_manifest.json"

def main():
    if not MANIFEST_PATH.exists():
        print("Manifest not found.")
        return

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    evaluator = GeminiAudioEvaluator()
    bypassed_records = []

    # Filter to evaluate only stealthy prompts (021 to 030)
    stealth_manifest = [item for item in manifest if "stealth" in item["attack_id"]]
    
    print("\n" + "="*80)
    print(f"EVALUATING {len(stealth_manifest)} STEALTHY L1 ATTACKS TO FIND UNDETECTED PROMPTS")
    print("="*80)

    for item in stealth_manifest:
        audio_path = ROOT / item["audio_path"]
        print(f"Evaluating {item['attack_id']} ({item['family']})...", flush=True)
        try:
            verdict, _ = evaluator.evaluate(audio_path)
            detected = verdict.injection_detected
            rec_action = verdict.recommended_action
            print(f"  ASR: {verdict.transcript}", flush=True)
            print(f"  Detected: {detected} | Recommendation: {rec_action} | Reason: {verdict.reason}", flush=True)
            
            if not detected:
                # Load spec file to get payload_text
                spec_path = ROOT / "artifacts" / "specs" / f"{item['attack_id']}.json"
                payload_text = ""
                if spec_path.exists():
                    with open(spec_path, "r", encoding="utf-8") as sf:
                        payload_text = json.load(sf).get("payload_text", "")
                
                bypassed_records.append({
                    "attack_id": item["attack_id"],
                    "family": item["family"],
                    "payload_text": payload_text,
                    "why_it_might_bypass": item["why_it_might_bypass"],
                    "recommended_action": rec_action,
                    "reason": verdict.reason,
                    "transcript": verdict.transcript
                })
        except Exception as e:
            print(f"  Error: {e}", flush=True)

    print("\n" + "="*80)
    print(f"EVALUATION COMPLETE. FOUND {len(bypassed_records)} UNDETECTED ATTACKS.")
    print("="*80)

    # Save undetected manifest
    out_path = ROOT / "artifacts" / "specs" / "undetected_manifest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bypassed_records, f, indent=2)

    print(f"Saved undetected records manifest to {out_path}", flush=True)

    # Print summary table
    print("\n### Bypassed (Undetected) Attacks Summary:")
    print("| Attack ID | Family | Payload Text | Why It Bypasses |")
    print("|---|---|---|---|")
    for r in bypassed_records:
        print(f"| {r['attack_id']} | {r['family']} | {r['payload_text']} | {r['why_it_might_bypass']} |")

if __name__ == "__main__":
    main()
