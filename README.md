# 🔐 UPI Fraud Detection System

> A machine learning system that detects fraudulent UPI transactions using a CNN-based model — achieving ~85% accuracy on real transaction data.

📁 Built by [Syeda Ayesha](https://github.com/syedaayesha-28)

---

## 🎯 Problem Statement

UPI fraud is a growing threat in India's digital payments ecosystem. This project builds an ML pipeline that automatically classifies transactions as fraudulent or legitimate, with an admin monitoring module for real-time oversight.

## 🛠️ Tech Stack

| Layer | Tools |
|---|---|
| Language | Python 3.10 |
| ML Framework | Keras, TensorFlow |
| Classical ML | Scikit-learn |
| Data Processing | Pandas, NumPy |
| Model Architecture | CNN (Convolutional Neural Network) |
| Visualisation | Matplotlib, Seaborn |

## 📊 Results

| Metric | Score |
|---|---|
| Accuracy | ~85% |
| Dataset Size | 1000+ transaction records |
| Classes | Fraudulent / Legitimate |

## 🏗️ Project Architecture

```
Raw Transaction Data (CSV)
        ↓
  Data Preprocessing
  (null handling, normalisation, encoding)
        ↓
  Feature Engineering
  (transaction amount, time patterns, frequency)
        ↓
  CNN Model Training
  (Keras + TensorFlow)
        ↓
  Evaluation (Accuracy, Confusion Matrix, ROC)
        ↓
  Admin Monitoring Module
  (fraud flag, alert logging)
```

## 📁 Folder Structure

```
upi-fraud-detection/
├── data/
│   └── transactions.csv        # Dataset (sample)
├── notebooks/
│   └── fraud_detection.ipynb   # Full EDA + training notebook
├── src/
│   ├── preprocess.py           # Data cleaning & feature engineering
│   ├── model.py                # CNN model definition
│   ├── train.py                # Training script
│   └── admin_monitor.py        # Fraud monitoring module
├── models/
│   └── fraud_model.h5          # Saved trained model
├── requirements.txt
└── README.md
```

## 🚀 How to Run

```bash
git clone https://github.com/syedaayesha-28/upi-fraud-detection
cd upi-fraud-detection
pip install -r requirements.txt

# Train the model
python src/train.py

# Run admin monitor
python src/admin_monitor.py
```

Or open the notebook for full walkthrough:
```bash
jupyter notebook notebooks/fraud_detection.ipynb
```

## 🔑 Key Features

- **Data preprocessing pipeline** — handles missing values, normalisation, encoding
- **Feature engineering** — extracts time-based, amount-based, and frequency patterns
- **CNN model** — learns spatial patterns across transaction feature maps
- **Admin monitoring module** — flags high-risk transactions, logs alerts
- **Model evaluation** — accuracy, confusion matrix, classification report

## 📦 Requirements

```
tensorflow==2.13.0
keras==2.13.0
scikit-learn==1.3.0
pandas==2.0.3
numpy==1.24.3
matplotlib==3.7.2
seaborn==0.12.2
jupyter==1.0.0
```

## 🔗 Skills Demonstrated

- Machine learning model training & evaluation
- Data preprocessing and feature engineering
- Deep learning with Keras/TensorFlow
- Python data science pipeline
- Real-world problem solving (fintech / fraud detection)
