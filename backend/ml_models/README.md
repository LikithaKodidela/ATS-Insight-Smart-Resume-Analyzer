# Runtime ML Models

Put the exported fine-tuned SentenceTransformer folder here:

```text
backend/ml_models/finetuned_resume_jd_model/
```

That folder should contain files such as `modules.json`,
`config_sentence_transformers.json`, tokenizer files, and model weights
(`model.safetensors` or `pytorch_model.bin`).

To create it from the CSV data in this project, run:

```powershell
venv\Scripts\python.exe scripts\train_resume_jd_model.py
```

The backend automatically checks this folder at startup. If it exists, the
resume/JD semantic matching and skill evidence checks use the fine-tuned model.
