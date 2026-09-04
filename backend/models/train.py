"""
models/train.py — Phase 8 Machine Learning Upgrade

Trains a Random Forest Classifier on historical payment data and ground truth
to predict the probability of recovering a failed payment.
"""

import sys
import pickle
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import get_connection
from logging_config import get_logger

logger = get_logger(__name__)

MODEL_PATH = Path(__file__).resolve().parent / "recovery_model.pkl"
ENCODER_PATH = Path(__file__).resolve().parent / "encoder_metadata.pkl"

def fetch_training_data() -> pd.DataFrame:
    """Fetch joined data from SQLite for training."""
    query = """
        SELECT 
            p.amount,
            p.previous_attempts,
            p.payment_method,
            p.failure_reason,
            c.total_payments,
            c.successful_payments,
            g.actual_recovery_outcome
        FROM payments p
        JOIN customers c ON p.customer_id = c.customer_id
        JOIN ground_truth g ON p.payment_id = g.payment_id
    """
    with get_connection() as conn:
        df = pd.read_sql_query(query, conn)
    return df

def preprocess_data(df: pd.DataFrame, is_training: bool = True, encoder_meta: dict = None):
    """
    Preprocess dataframe for the model. 
    One-hot encodes categorical variables and ensures consistent columns.
    """
    # Create derived features
    df['success_rate'] = df['successful_payments'] / df['total_payments'].replace(0, 1)
    
    # Select base features
    categorical_cols = ['payment_method', 'failure_reason']
    numerical_cols = ['amount', 'previous_attempts', 'total_payments', 'success_rate']
    
    # One-hot encode
    df_encoded = pd.get_dummies(df[numerical_cols + categorical_cols], columns=categorical_cols)
    
    if is_training:
        # Save columns to ensure test/inference time data matches perfectly
        feature_columns = df_encoded.columns.tolist()
        return df_encoded, feature_columns
    else:
        # At inference time, we must match the training columns exactly
        expected_cols = encoder_meta['feature_columns']
        for col in expected_cols:
            if col not in df_encoded.columns:
                df_encoded[col] = 0
        df_encoded = df_encoded[expected_cols] # reorder and drop extra
        return df_encoded

def train_model():
    print("Fetching data from SQLite...")
    df = fetch_training_data()
    
    if len(df) < 100:
        print("Not enough data to train. Please run generate_data.py first.")
        return

    print(f"Loaded {len(df)} records. Preprocessing...")
    
    # Prepare X and y
    y = df['actual_recovery_outcome']
    X, feature_columns = preprocess_data(df, is_training=True)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training Random Forest Classifier...")
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    print("\n--- Model Evaluation ---")
    print(classification_report(y_test, y_pred))
    auc = roc_auc_score(y_test, y_prob)
    print(f"ROC-AUC Score: {auc:.3f}\n")
    
    # Save model and metadata
    print(f"Saving model to {MODEL_PATH}...")
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
        
    with open(ENCODER_PATH, "wb") as f:
        pickle.dump({'feature_columns': feature_columns}, f)
        
    print("Training complete! Phase 8 ML upgrade active.")

if __name__ == "__main__":
    train_model()
