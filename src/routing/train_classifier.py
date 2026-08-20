"""Train a logistic regression complexity classifier and save it to disk."""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.routing.features import FEATURE_NAMES, extract_features

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "labeled_prompts.csv"
MODEL_PATH = ROOT / "data" / "complexity_classifier.joblib"
LABELS = ["simple", "moderate", "complex"]


def load_dataset(path: Path = DATA_PATH) -> tuple[list[list[float]], list[str]]:
    df = pd.read_csv(path)
    if not {"prompt", "label"}.issubset(df.columns):
        raise ValueError("CSV must have columns: prompt, label")

    unknown = sorted(set(df["label"]) - set(LABELS))
    if unknown:
        raise ValueError(f"Unexpected labels: {unknown}. Expected {LABELS}")

    X = [extract_features(p) for p in df["prompt"].astype(str)]
    y = df["label"].astype(str).tolist()
    return X, y


def train_and_save() -> None:
    X, y = load_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.3,
        random_state=42,
        stratify=y,
    )

    pipe = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ]
    )
    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    print(f"Holdout accuracy: {acc:.1%}  (n_train={len(y_train)}, n_test={len(y_test)})")
    print("\nConfusion matrix (rows=true, cols=pred):")
    print("labels:", LABELS)
    print(confusion_matrix(y_test, y_pred, labels=LABELS))
    print("\nClassification report:")
    print(classification_report(y_test, y_pred, labels=LABELS, digits=3))

    # Refit on all labeled data for the shipped model
    pipe.fit(X, y)
    payload = {
        "pipeline": pipe,
        "feature_names": FEATURE_NAMES,
        "labels": LABELS,
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, MODEL_PATH)
    print(f"\nSaved model → {MODEL_PATH}")


if __name__ == "__main__":
    train_and_save()
