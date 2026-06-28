# %% [markdown]
# # AgentImmune Gemma LoRA smoke fine-tune
#
# Run this in Colab after cloning the repo. It trains a first text guardrail LoRA
# over the real live-browser notes-exfil traces. This is not the final robust
# model until more measured bypass families arrive.

# %%
# Colab setup. Restart the runtime if pip asks you to.
!pip install -q unsloth datasets accelerate trl peft bitsandbytes

# %%
import json
import os
from pathlib import Path

REPO = Path("/content/Recursive-shield")
if not REPO.exists():
    !git clone https://github.com/vineeth917/Recursive-shield.git /content/Recursive-shield

%cd /content/Recursive-shield
!git pull --rebase origin main

# %%
# Expand the real evidence bundle if artifacts are not already present.
bundle = Path("fixtures/stealth_candidate_traces/notes_exfil_live_browser_batch_20260628.zip")
if bundle.exists() and not Path("artifacts/notes_exfil_live_browser/consolidated_summary.json").exists():
    !python -m zipfile -e fixtures/stealth_candidate_traces/notes_exfil_live_browser_batch_20260628.zip .

!python scripts/prepare_notes_exfil_splits.py

# %%
from datasets import load_dataset
from unsloth import FastLanguageModel
from trl import SFTConfig, SFTTrainer

MODEL_ID = os.environ.get("MODEL_ID", "unsloth/gemma-4-4b-it-bnb-4bit")
MAX_SEQ_LENGTH = int(os.environ.get("MAX_SEQ_LENGTH", "2048"))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "artifacts/models/gemma_notes_exfil_lora_v1")

dataset = load_dataset(
    "json",
    data_files={
        "train": "artifacts/training/notes_exfil_splits/train.jsonl",
        "dev": "artifacts/training/notes_exfil_splits/dev.jsonl",
        "held_out": "artifacts/training/notes_exfil_splits/held_out.jsonl",
    },
)

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_ID,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

# %%
def formatting_prompts_func(batch):
    texts = []
    for messages in batch["messages"]:
        texts.append(
            tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )
        )
    return {"text": texts}


formatted = dataset.map(formatting_prompts_func, batched=True)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=formatted["train"],
    eval_dataset=formatted["dev"],
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    packing=False,
    args=SFTConfig(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        warmup_ratio=0.05,
        num_train_epochs=8,
        learning_rate=1e-4,
        fp16=False,
        bf16=True,
        logging_steps=1,
        eval_strategy="epoch",
        save_strategy="epoch",
        seed=3407,
        report_to="none",
    ),
)

trainer.train()
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

# %%
# Tiny held-out sanity check. This is not a full eval, just "does the adapter answer JSON-ish verdicts".
FastLanguageModel.for_inference(model)
for row in formatted["held_out"].select(range(min(4, len(formatted["held_out"])))):
    prompt = row["text"].rsplit("<start_of_turn>model", 1)[0] if "<start_of_turn>model" in row["text"] else row["text"]
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(**inputs, max_new_tokens=96, temperature=0.0, do_sample=False)
    print(tokenizer.decode(outputs[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True))

