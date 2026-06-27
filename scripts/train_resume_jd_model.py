import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sentence_transformers import InputExample, SentenceTransformer, losses
from sentence_transformers.util import batch_to_device
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "colab_notebooks" / "data" / "cleaned_resumeJD_pairs.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "backend" / "ml_models" / "finetuned_resume_jd_model"
DEFAULT_METADATA_PATH = PROJECT_ROOT / "colab_notebooks" / "data" / "finetune_metadata.json"
DEFAULT_PREDICTIONS_PATH = PROJECT_ROOT / "colab_notebooks" / "data" / "finetune_test_predictions.csv"


def make_examples(frame: pd.DataFrame) -> list[InputExample]:
    return [
        InputExample(
            texts=[str(row["resume_text"]), str(row["job_description"])],
            label=float(row["match_score"]),
        )
        for _, row in frame.iterrows()
    ]


def predict_similarity(model: SentenceTransformer, frame: pd.DataFrame, batch_size: int) -> np.ndarray:
    resume_emb = model.encode(
        frame["resume_text"].astype(str).tolist(),
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    jd_emb = model.encode(
        frame["job_description"].astype(str).tolist(),
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return np.sum(resume_emb * jd_emb, axis=1)


def train_model(
    model: SentenceTransformer,
    train_examples: list[InputExample],
    val_df: pd.DataFrame,
    epochs: int,
    batch_size: int,
) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    loss_model = losses.CosineSimilarityLoss(model=model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5)

    def collate(batch: list[InputExample]):
        texts_a = [example.texts[0] for example in batch]
        texts_b = [example.texts[1] for example in batch]
        labels = torch.tensor([example.label for example in batch], dtype=torch.float)
        features = [model.tokenize(texts_a), model.tokenize(texts_b)]
        features = [batch_to_device(feature, device) for feature in features]
        return features, labels.to(device)

    train_dataloader = DataLoader(
        train_examples,
        shuffle=True,
        batch_size=batch_size,
        collate_fn=collate,
    )

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0

        for features, labels in train_dataloader:
            optimizer.zero_grad()
            loss = loss_model(features, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += float(loss.detach().cpu())

        avg_loss = total_loss / max(1, len(train_dataloader))
        val_similarity = predict_similarity(model, val_df, batch_size)
        val_corr = float(np.corrcoef(val_df["match_score"], val_similarity)[0, 1])
        print(f"Epoch {epoch}/{epochs} | loss={avg_loss:.4f} | val_correlation={val_corr:.4f}")


def summarize(model_name: str, y_true, y_pred) -> dict:
    return {
        "model": model_name,
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "correlation": float(np.corrcoef(y_true, y_pred)[0, 1]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune a SentenceTransformer for resume/job-description matching."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--metadata-path", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--predictions-path", type=Path, default=DEFAULT_PREDICTIONS_PATH)
    parser.add_argument("--base-model", default="all-MiniLM-L6-v2")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--allow-downloads",
        action="store_true",
        help="Allow downloading the base model if it is not already cached locally.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.dataset.is_file():
        raise FileNotFoundError(f"Dataset not found: {args.dataset}")

    df = pd.read_csv(args.dataset)
    required = {"resume_text", "job_description", "match_score", "match_label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    train_df, temp_df = train_test_split(
        df,
        test_size=0.30,
        random_state=args.seed,
        stratify=df["match_label"],
    )
    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.50,
        random_state=args.seed,
        stratify=temp_df["match_label"],
    )

    train_examples = make_examples(train_df)

    print(f"Loading base model: {args.base_model}")
    model = SentenceTransformer(args.base_model, local_files_only=not args.allow_downloads)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    train_model(model, train_examples, val_df, args.epochs, args.batch_size)
    model.save(str(args.output_dir))

    print("Evaluating base and fine-tuned models...")
    base_model = SentenceTransformer(args.base_model, local_files_only=not args.allow_downloads)
    finetuned_model = SentenceTransformer(str(args.output_dir), local_files_only=True)

    test_eval = test_df.copy()
    test_eval["base_similarity"] = predict_similarity(base_model, test_eval, args.batch_size)
    test_eval["finetuned_similarity"] = predict_similarity(finetuned_model, test_eval, args.batch_size)

    metrics = [
        summarize("base", test_eval["match_score"], test_eval["base_similarity"]),
        summarize("finetuned", test_eval["match_score"], test_eval["finetuned_similarity"]),
    ]

    args.predictions_path.parent.mkdir(parents=True, exist_ok=True)
    test_eval.to_csv(args.predictions_path, index=False)

    metadata = {
        "base_model": args.base_model,
        "dataset": str(args.dataset.relative_to(PROJECT_ROOT)),
        "output_dir": str(args.output_dir.relative_to(PROJECT_ROOT)),
        "total_pairs": int(len(df)),
        "train_pairs": int(len(train_df)),
        "val_pairs": int(len(val_df)),
        "test_pairs": int(len(test_df)),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "label_distribution": df["match_label"].value_counts().to_dict(),
        "metrics": metrics,
    }
    args.metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Saved fine-tuned model folder: {args.output_dir}")
    print(f"Saved predictions: {args.predictions_path}")
    print(f"Saved metadata: {args.metadata_path}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
