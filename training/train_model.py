import pandas as pd
import numpy as np
import joblib
import argparse
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

def load_and_preprocess(csv_files):
    """Load multiple CSVs and prepare feature matrix X and target vector y."""
    dfs = []
    for f in csv_files:
        try:
            dfs.append(pd.read_csv(f))
        except Exception as e:
            print(f"Failed to read {f}: {e}")
            
    if not dfs:
        raise ValueError("No valid CSV data provided for training.")
        
    df = pd.concat(dfs, ignore_index=True)
    
    # Feature columns defined in detector/model.py
    feature_columns = [
        "syscall_count", "execve_count", "open_count", 
        "socket_count", "connect_count", "unique_binaries_count",
        "flow_count", "unique_destinations_count", 
        "tcp_count", "udp_count"
    ]
    
    # Ensure all columns exist and fill NaNs
    for col in feature_columns:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0)
            
    X = df[feature_columns]
    y = df["label"]
    
    print(f"✅ Data loaded: {len(df)} samples")
    print(f"📊 Label Distribution:\n{df['label'].value_counts()}")
    
    return X, y, feature_columns

def train_model(X, y, feature_names, model_output):
    # Split data (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Initialize Decision Tree
    clf = DecisionTreeClassifier(max_depth=10, random_state=42)
    clf.fit(X_train, y_train)
    
    # Predict & Evaluate
    y_pred = clf.predict(X_test)
    
    print("\n--- 📈 Model Evaluation Metrics ---")
    print(f"Accuracy Score: {accuracy_score(y_test, y_pred):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    
    # Save the trained model
    joblib.dump(clf, model_output)
    print(f"\n💾 Model successfully saved to: {model_output}")
    
    # Display the tree logic for transparency
    tree_rules = export_text(clf, feature_names=feature_names)
    print("\n--- 🌳 Decision Tree Logic (Truncated) ---")
    print(tree_rules[:1000] + "...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IDS Model Training Script")
    parser.add_argument("--input", nargs='+', required=True, help="Space-separated paths to CSV files")
    parser.add_argument("--output", default="src/detector/ids_decision_tree.pkl", help="Where to save the .pkl model")
    args = parser.parse_args()

    try:
        X, y, feature_names = load_and_preprocess(args.input)
        train_model(X, y, feature_names, args.output)
    except Exception as e:
        print(f"❌ Training failed: {e}")
