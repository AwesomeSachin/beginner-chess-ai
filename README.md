# Hybrid Neuro-Symbolic Chess AI ♟️🧠

Welcome to the **Hybrid Neuro-Symbolic Chess AI** repository! 🚀
This project implements a unique **Teacher-Student AI Architecture** that combines the raw calculation power of Stockfish with the intuition of a custom-trained Convolutional Neural Network (CNN). Unlike standard engines that only calculate the "best" move, this system is designed to identify the "most instructive" move for human learning.

---

## 🏗️ System Architecture

The architecture follows a **Hybrid Intelligence Pipeline**, integrating deep learning with rule-based verification:


1.  **Data Ingestion Layer (The Student's Textbook)**:
    * Ingests massive PGN datasets (Lichess Database).
    * Parses raw moves into **Bitboard Tensors** (8x8x12 matrices) for CNN consumption.
2.  **Neural Network Layer (The Student)**:
    * A custom **Dual-Head CNN** (Convolutional Neural Network) trained to predict both the `Source Square` and `Target Square` of a human-like move.
    * Mimics high-level human intuition rather than brute-force calculation.
3.  **Verification Layer (The Teacher)**:
    * Integrates **Stockfish 16** via Python bindings.
    * Filters the Neural Network's suggestions against objective "safety" metrics to prevent blunders.
4.  **Heuristic Explanation Layer**:
    * A custom rule-based engine that interprets the board state to generate **Natural Language Explanations** (e.g., "Controlling the Center," "Developing the Knight").

---

## 📖 Project Overview

This project goes beyond simple model training by solving specific engineering challenges in **Human-AI Alignment**:

1.  **Advanced Data Engineering**: Built a custom pipeline to convert millions of chess positions into sparse matrix representations (One-Hot Encoding) optimized for TensorFlow.
2.  **Dual-Head Architecture**: Designed a model that solves two classification problems simultaneously (From-Square and To-Square), significantly reducing the output space compared to traditional "flat" move prediction.
3.  **Hybrid Inference Logic**: Developed a "Safety Filter" algorithm that allows the AI to be creative (human-like) but prevents it from making objective mistakes (computer-verified).
4.  **Interactive Explainability**: The system doesn't just play; it **explains**. It uses board state heuristics to translate tensor outputs into beginner-friendly chess concepts.

🎯 **Key Technical Skills Showcased:**
* **Deep Learning (CNNs)**: Custom architecture design in TensorFlow/Keras.
* **Data Engineering**: Handling large-scale PGN datasets and efficient tensor transformation.
* **System Design**: Integrating Python, TensorFlow, Stockfish, and Streamlit into a cohesive app.
* **Neuro-Symbolic AI**: Merging neural networks (learning) with symbolic logic (rules/Stockfish).

---

## 🛠️ Tech Stack & Tools

* **[TensorFlow/Keras](https://www.tensorflow.org/):** For building and training the Dual-Head CNN.
* **[Python-Chess](https://python-chess.readthedocs.io/):** For move generation, validation, and PGN parsing.
* **[Stockfish 16](https://stockfishchess.org/):** The "Teacher" engine for safety verification.
* **[Google Colab](https://colab.research.google.com/drive/1ECfvacFIn7o7KLRfMGHy9aXt6sGJuqyS?usp=sharing/):** Used for GPU-accelerated training of the model.
* **[Streamlit](https://beginnerchessai.streamlit.app/):** For the interactive frontend UI and visualization.
* **[Lichess Database](https://database.lichess.org/):** Source of millions of grandmaster games for training.
* **[NumPy](https://numpy.org/):** For high-performance matrix manipulation of board states.

---

## 🚀 Unique Contributions (My Input)

*Many AI projects simply "train a model on data." Here is how this project differs:*

### 1. The "Dual-Head" Tensor Strategy
Instead of treating chess moves as a single classification task (which would require ~4000 output classes for every possible move), I engineered a **Split-Head Architecture**:
* **Input**: 8x8x13 Board Matrix (12 pieces + valid moves).
* **Head 1 (64 outputs)**: Predicts the *Source Square* probability.
* **Head 2 (64 outputs)**: Predicts the *Target Square* probability.
* **Innovation**: This reduced the model complexity by **90%**, allowing for faster inference and more "human-like" patterns (e.g., recognizing *which* Knight to move, not just *where* a Knight should go).

### 2. The "Safety Filter" Algorithm
A raw neural network trained on human games will inevitably hallucinate or blunder. I wrote a custom **Hybrid Inference Function** in `app.py`:
* *Step A*: Stockfish calculates the top 5 mathematically "safe" moves.
* *Step B*: The Neural Network ranks those 5 moves based on "human probability."
* *Result*: The engine plays moves that are statistically sound (Stockfish) but stylistically human (Neural Net).

### 3. Bitboard-to-Matrix Transformation
I wrote the custom pre-processing pipeline to convert FEN strings into 3D NumPy arrays. This involved:
* Mapping piece types to integer channels.
* Handling "turn" perspective (flipping the board for Black/White).
* Optimizing the generator for memory-efficient training on Colab.

---

## 📂 Repository Structure
```
beginner-chess-ai/ 
│ 
├── app.py # The main application file containing UI, Hybrid Logic, and Heuristics 
├── my_chess_model_v2.keras # The trained Dual-Head CNN model (Saved from Colab) 
├── packages.txt # Linux-level dependencies (Stockfish installation) 
├── requirements.txt # Python dependencies (Streamlit, TensorFlow, Python-Chess) 
└── README.md # Project documentation
```
---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE). You are free to use, modify, and share this project with proper attribution.

---

## 🌟 About Me

**Sachin chaudhary**
*A Data Science & AI Enthusiast passionate about "Explainable AI."*

This project was built to solve the "Black Box" problem in AI chess coaches. By combining deep learning with rule-based verification, I created a system that doesn't just crush you—it teaches you.
