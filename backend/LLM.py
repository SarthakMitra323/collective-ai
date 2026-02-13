import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer, DataCollatorForLanguageModeling, pipeline
from datasets import load_dataset

# --- 1. Scalable Configuration ---
CONFIG = {
    "model_name": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",  
    "dataset_id": "timdettmers/openassistant-guanaco", 
    "output_dir": "./collective_ai_model",
    "max_length": 1024, 
    "batch_size": 1,    
    "grad_accumulation": 8,   
    "learning_rate": 2e-4,
    "epochs": 1,        
    "fp16": torch.cuda.is_available(),
}

def get_device():
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    return "cpu"

# --- PART A: TRAINING LOGIC ---
def train_model():
    print(f"🚀 Initializing Training Protocol on {get_device().upper()}...")
    
    tokenizer = AutoTokenizer.from_pretrained(CONFIG["model_name"])
    if tokenizer.pad_token is None: 
        tokenizer.pad_token = tokenizer.eos_token

    print(f"🌍 Downloading Collective Knowledge: {CONFIG['dataset_id']}...")
    dataset = load_dataset(CONFIG["dataset_id"], split="train") 

    def process_data(samples):
        return tokenizer(
            samples["text"], truncation=True, max_length=CONFIG["max_length"], padding="max_length"
        )

    print("🔄 Tokenizing data...")
    tokenized_dataset = dataset.map(process_data, batched=True, remove_columns=dataset.column_names)

    model = AutoModelForCausalLM.from_pretrained(CONFIG["model_name"])
    model.to(get_device()) # type:ignore

    training_args = TrainingArguments(
        output_dir=CONFIG["output_dir"],
        per_device_train_batch_size=CONFIG["batch_size"],
        gradient_accumulation_steps=CONFIG["grad_accumulation"],
        num_train_epochs=CONFIG["epochs"],
        learning_rate=CONFIG["learning_rate"],
        fp16=CONFIG["fp16"],
        save_strategy="epoch",
        logging_steps=50,
        report_to="none"
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    print("\n🔥 Starting Fine-Tuning...")
    trainer.train()
    
    print(f"\n💾 Saving Collective AI to {CONFIG['output_dir']}...")
    trainer.save_model()
    tokenizer.save_pretrained(CONFIG["output_dir"])
    print("✅ Training Complete.")

# --- PART B: INFERENCE CLASS (For server.py) ---
class CollectiveModel:
    def __init__(self):
        self.device = get_device()
        self.model_path = CONFIG["output_dir"] if os.path.exists(CONFIG["output_dir"]) else CONFIG["model_name"]
        print(f"🧠 Loading AI Model from: {self.model_path} ({self.device})")
        
        try:
            self.generator = pipeline(
                "text-generation",
                model=self.model_path,
                tokenizer=self.model_path,
                device_map="auto" if self.device == "cuda" else None,
                dtype=torch.float16 if CONFIG["fp16"] else torch.float32
            )
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            self.generator = None

    def generate_response(self, user_input, context_docs=[]):
        if not self.generator:
            return "Error: Neural Core Offline."

        # RAG Prompt Construction (if context exists from rag.py)
        system_prompt = "You are Collective AI, a wise assistant. Use the provided Context from the community to answer the user."
        
        context_block = ""
        if context_docs:
            context_block = "\nCONTEXT FROM COLLECTIVE MEMORY:\n" + "\n".join([f"- {doc}" for doc in context_docs]) + "\n"

        # TinyLlama format
        prompt = f"<|system|>\n{system_prompt}\n{context_block}</s>\n<|user|>\n{user_input}</s>\n<|assistant|>\n"
        
        sequences = self.generator(
            prompt,
            max_new_tokens=300, 
            do_sample=True,
            temperature=0.7,
            top_k=50,
            top_p=0.95,
            pad_token_id=self.generator.tokenizer.eos_token_id # type:ignore
        )
        
        full_text = sequences[0]['generated_text']
        response = full_text.split("<|assistant|>\n")[-1].strip()
        return response

# --- PART C: STANDALONE CHAT INTERFACE ---
def run_chat_interface():
    print("\n💬 Loading Collective AI Chat Interface...")
    ai = CollectiveModel()
    if not ai.generator: return
    
    print("\n✨ Collective AI is Online. Type 'exit' to quit.")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]: break
            print(f"AI: {ai.generate_response(user_input)}")
            print("-" * 50)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    print("Select Mode:")
    print("1. Train Model (Fine-tune on Dataset)")
    print("2. Run Chatbot (Terminal Inference Mode)")
    print("Note: To run the web API, execute server.py instead.")
    
    choice = input("Enter 1 or 2: ").strip()
    
    if choice == "1":
        train_model()
    elif choice == "2":
        run_chat_interface()
    else:
        print("Invalid selection.")