# Beginner AI Chess Coach: A Hybrid Neuro-Symbolic Engine

Welcome to the **Beginner AI Chess Coach** repository! 🚀  
This project demonstrates a **Hybrid AI** solution that combines the raw calculation power of Stockfish with the intuition of a Deep Learning Neural Network. Unlike traditional engines that simply calculate the "best" move, this AI is designed to teach beginners by suggesting natural, human-like moves and explaining the *strategic principles* behind them.

---

## 🏗️ System Architecture

The architecture follows a **Hybrid Teacher-Student** workflow:

1.  **Data Ingestion Layer**: Raw game data (PGN) is streamed from the [Lichess Open Database](https://database.lichess.org/), parsed into move sequences, and converted into 8x8x13 **Bitboard Tensors**.
2.  **Deep Learning Model (The Student)**: A Custom Convolutional Neural Network (CNN) trained to mimic human move patterns (intuition).
3.  **Validation Layer (The Teacher)**: Stockfish 16 acts as a gatekeeper, filtering out blunders to ensure the AI only suggests "safe" moves.
4.  **Heuristic Logic Layer**: A rule-based system that interprets the board state to generate natural language explanations (e.g., "Control the Center," "Develop Knights").
5.  **Application Layer**: A Streamlit web interface for interactive analysis.

---

## 📖 Project Overview

This project involves:

1.  **Data Engineering**: Building a pipeline to process complex PGN files and convert chess positions into machine-readable tensors.
2.  **Deep Learning (CNN)**: Designing and training a Dual-Head Neural Network to predict both *Source* and *Target* squares.
3.  **Hybrid Logic Integration**: merging rule-based engines (Stockfish) with probabilistic models (Neural Networks).
4.  **UI/UX Development**: Creating an interactive coaching interface that supports PGN loading, move visualization (arrows), and manual play.

🎯 **Target Audience**: Beginners looking to understand *why* a move is good, rather than just memorizing lines.

---

## 🛠️ Tech Stack & Tools

* **[Python 3.10+](https://www.python.org/):** Core logic and scripting.
* **[TensorFlow / Keras](https://www.tensorflow.org/):** Building and training the Convolutional Neural Network.
* **[Streamlit](https://streamlit.io/):** Interactive web application framework.
* **[Stockfish](https://stockfishchess.org/):** Open-source chess engine used for move validation.
* **[Python-Chess](https://python-chess.readthedocs.io/):** Library for move generation, validation, and PGN handling.
* **[Google Colab](https://colab.research.google.com/):** Cloud environment used for training the model on the Lichess dataset.
* **[NumPy](https://numpy.org/):** Matrix operations for board representation.

---

## 🚀 Project Details & "My Input"

### 1. Data Engineering (My Contribution)
Instead of using a pre-cleaned CSV, I built a custom data pipeline:
* **Source:** Streamed compressed PGN data from Lichess (ZStandard compression).
* **Transformation:** Converted FEN strings into **One-Hot Encoded Matrices** (8x8x13).
    * *Why 13 channels?* 6 piece types for White + 6 for Black + 1 for Empty squares.
* **Scale:** Processed ~2,000 high-quality games to extract move patterns.

### 2. The Model Architecture (The "Brain")
I designed a **Dual-Head CNN** to solve the unique problem of chess moves:
* **Input:** 8x8x13 Board Representation.
* **Hidden Layers:** 2x Convolutional Layers (64 & 128 filters) + BatchNormalization + Relu Activation.
* **Output Head 1:** Softmax distribution (64 units) for the **From Square**.
* **Output Head 2:** Softmax distribution (64 units) for the **To Square**.
* **Rationale:** Splitting the prediction allows the model to learn *piece selection* and *destination logic* independently.

### 3. The Hybrid Logic (The "Innovation")
A raw neural network often makes illegal or "blundering" moves. To solve this, I implemented a **Teacher-Student Filter**:
* **Step 1:** Stockfish generates the top 5 *technically safe* moves.
* **Step 2:** My Neural Network evaluates those 5 moves and picks the one with the highest "Human Probability" score.
* **Result:** The engine plays safely (thanks to Stockfish) but in a human style (thanks to the Neural Network).

---

## 📂 Repository Structure
