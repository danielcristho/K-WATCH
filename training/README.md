# K-IDS Model Training

Direktori ini berisi notebook dan script untuk training model Machine Learning K-IDS.

## File Structure

```
training/
├── train_model.ipynb          # Notebook untuk training Decision Tree
├── KK_Klasifikasi kNN dan DT.ipynb  # Referensi dari tugas kuliah
├── models/                    # Direktori untuk menyimpan trained models
│   ├── decision_tree_model.pkl
│   └── scaler.pkl
└── README.md
```

## Training Process

1. **Load Dataset**: Memuat dataset yang sudah diproses dari feature engineering
2. **Data Preparation**: Split data menjadi training dan testing set. Jika tersedia, split dilakukan berdasarkan `session_id` atau `pod_name` agar data dari grup yang sama tidak bocor ke train dan test sekaligus.
3. **Class Balancing**: Oversampling hanya pada training set.
4. **Model Training**: Training Decision Tree classifier tanpa scaler.
5. **Evaluation**: Evaluasi model dengan metrics (accuracy, precision, recall, F1-score)
6. **Save Model**: Simpan trained model dan feature names

## Usage

### Training Model

```bash
jupyter notebook train_model.ipynb
```

Atau jalankan semua cells dalam notebook.

### Load Trained Model

```python
import joblib

# Load model dan feature names
model = joblib.load('models/decision_tree_model.pkl')
feature_names = joblib.load('models/feature_names_syscall.pkl')

# Predict
predictions = model.predict(X[feature_names])
```

## Model Parameters

Decision Tree parameters yang digunakan:

- `max_depth`: None
- `min_samples_split`: 5
- `min_samples_leaf`: 2
- `random_state`: 42

## Future Improvements

- [x] Implementasi oversampling untuk handling imbalanced data
- [ ] Hyperparameter tuning dengan GridSearchCV
- [ ] Ensemble methods (Random Forest, XGBoost)
- [ ] Cross-validation untuk evaluasi yang lebih robust
- [ ] Feature selection untuk optimasi model
