import os
import json
import numpy as np
from typing import List
from redteam.ablation import AblationStudy, cosine_similarity
from contracts import AttackSpec

class SpecNoveltyChecker:
    def __init__(self):
        self.ablation = AblationStudy()

    def load_specs(self) -> List[AttackSpec]:
        specs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "artifacts", "specs")
        specs = []
        if not os.path.exists(specs_dir):
            return specs
            
        for file in os.listdir(specs_dir):
            if file.endswith(".json"):
                with open(os.path.join(specs_dir, file), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    specs.append(AttackSpec(**data))
        return specs

    def audit_dataset(self, similarity_threshold: float = 0.85) -> bool:
        """
        Loads all specs, gets Voyage embeddings for payload_texts,
        calculates duplicate rates and intra-family distances, and asserts INV-2 criteria.
        """
        specs = self.load_specs()
        if not specs:
            print("No specs found in artifacts/specs to audit.")
            return True

        print(f"Auditing {len(specs)} attack specs for novelty and duplicate limits (INV-2)...")
        payloads = [spec.payload_text for spec in specs]
        
        # Get embeddings
        embeddings = self.ablation.get_embeddings(payloads)
        
        # Check duplicate pairs (similarity > threshold)
        duplicates = []
        intra_family_sims = []
        inter_family_sims = []
        
        for i in range(len(specs)):
            for j in range(i + 1, len(specs)):
                sim = cosine_similarity(embeddings[i], embeddings[j])
                is_same_family = specs[i].family == specs[j].family
                
                if is_same_family:
                    intra_family_sims.append(sim)
                else:
                    inter_family_sims.append(sim)
                    
                if sim > similarity_threshold:
                    duplicates.append((specs[i].attack_id, specs[j].attack_id, sim))

        # Calculate metrics
        num_pairs = len(specs) * (len(specs) - 1) // 2 if len(specs) > 1 else 0
        dup_rate = len(duplicates) / num_pairs if num_pairs > 0 else 0.0
        
        mean_intra = np.mean(intra_family_sims) if intra_family_sims else 0.0
        mean_inter = np.mean(inter_family_sims) if inter_family_sims else 0.0
        
        print("\n--- Audit Results ---")
        print(f"Total evaluated pairs: {num_pairs}")
        print(f"Near-duplicate rate (similarity > {similarity_threshold}): {dup_rate:.2%}")
        print(f"Mean intra-family similarity: {mean_intra:.4f}")
        print(f"Mean inter-family similarity: {mean_inter:.4f}")
        print(f"Distinct family separation gap: {(mean_intra - mean_inter):.4f}")
        
        # Assert INV-2 criteria
        passed_dup_check = dup_rate < 0.05
        print(f"INV-2 Duplicate Rate Check (<5%): {'PASS' if passed_dup_check else 'FAIL'}")
        
        if duplicates:
            print("\nFlagged Near-Duplicate Pairs:")
            for atka, atkb, sim in duplicates:
                print(f"  * {atka} <-> {atkb} (Similarity: {sim:.4f})")
                
        return passed_dup_check

if __name__ == "__main__":
    checker = SpecNoveltyChecker()
    checker.audit_dataset()
