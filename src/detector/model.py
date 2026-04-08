import os
import joblib
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from typing import Dict, Any, List

class IDSModel:
    def __init__(self, model_path: str = "ids_decision_tree.pkl"):
        self.model_path = model_path
        self.model = None
        self.feature_columns = [
            "syscall_count", "execve_count", "open_count", 
            "socket_count", "connect_count", "unique_binaries_count",
            "flow_count", "unique_destinations_count", 
            "tcp_count", "udp_count"
        ]

    def load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
        else:
            print(f"Model file {self.model_path} not found.")

    def train(self, X: np.array, y: np.array):
        # Basic Decision Tree as per reference paper
        self.model = DecisionTreeClassifier(random_state=42)
        self.model.fit(X, y)
        joblib.dump(self.model, self.model_path)
        print(f"Model trained and saved to {self.model_path}")

    def predict(self, feature_dict: Dict[str, Any]) -> int:
        if self.model is None:
            self.load_model()
        
        if self.model is None:
            return 0 # No detection if no model

        # Prepare feature vector in the correct order
        x_vector = np.array([feature_dict.get(col, 0) for col in self.feature_columns]).reshape(1, -1)
        prediction = self.model.predict(x_vector)
        return int(prediction[0])
