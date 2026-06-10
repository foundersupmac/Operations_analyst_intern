"""Predictive maintenance classifier (week 19): Random Forest with SMOTE
applied inside the CV pipeline (training folds only) to avoid leakage."""
import pickle

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (classification_report, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

import config
from src.etl_pipeline import read_table

FEATURES = ["vibration_mm_s", "temperature_c", "current_a",
            "cycle_count", "days_since_maintenance"]


def main():
    sensors = read_table("sensors")
    X = sensors[FEATURES]
    y = sensors["failure_within_72h"]
    print(f"  positive class share: {y.mean():.1%}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=config.RANDOM_SEED)

    pipe = Pipeline([
        ("smote", SMOTE(random_state=config.RANDOM_SEED)),
        ("rf", RandomForestClassifier(n_estimators=200,
                                      random_state=config.RANDOM_SEED, n_jobs=-1)),
    ])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=config.RANDOM_SEED)
    f1_cv = cross_val_score(pipe, X_train, y_train, scoring="f1", cv=cv, n_jobs=-1)
    print(f"  5-fold CV F1: {f1_cv.mean():.3f} (std {f1_cv.std():.3f})")

    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)
    y_prob = pipe.predict_proba(X_test)[:, 1]
    metrics = {
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred),
        "auc_roc": roc_auc_score(y_test, y_prob),
    }
    print("  test set: " + ", ".join(f"{k}={v:.3f}" for k, v in metrics.items()))

    (config.REPORTS_DIR / "pdm_classification_report.txt").write_text(
        classification_report(y_test, y_pred)
        + f"\nAUC-ROC: {metrics['auc_roc']:.3f}\n"
        + f"5-fold CV F1: {f1_cv.mean():.3f} +/- {f1_cv.std():.3f}\n")
    with open(config.MODELS_DIR / "rf_pdm_v1.pkl", "wb") as fh:
        pickle.dump(pipe, fh)
    return metrics


if __name__ == "__main__":
    main()
