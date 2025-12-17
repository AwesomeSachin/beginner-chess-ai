# Deep Logic Chess: An Explainable AI (XAI) Project

Welcome to the **Deep Logic Chess** repository! 🚀  
This project demonstrates a **hybrid Machine Learning and Heuristic AI** solution designed to teach chess to beginners. Unlike traditional engines that simply calculate the "best" move, this system uses a trained Logistic Regression model to **rank moves based on human learnability** and generates natural language explanations (XAI) for every decision.

---

## 🧠 System Architecture

The architecture follows a **Generator-Discriminator** pattern enhanced with an XAI (Explainable AI) layer:

1. **Candidate Generation (Stockfish)**: The raw calculation engine generates the top legal moves based on deep search.
2. **Feature Engineering Layer**: Extract cognitive features relevant to beginners (e.g., *Is this a check?*, *Does this control the center?*, *Is it a tactical capture?*).
3. **ML Ranking Model**: A trained **Logistic Regression** classifier (trained on 20,000+ Lichess games) assigns a "Learnability Score" to re-rank moves.
4. **Narrative Engine**: Translates the board state and move logic into "Gotham-style" natural language feedback.

---

## 📖 Project Overview

This project involves:

1. **Big Data Engineering**: Streaming and processing over **500,000 moves** from the Lichess Open Database to create a custom training dataset.
2. **Machine Learning**: Training a supervised model to quantify the importance of Tactical vs. Positional play for <1500 Elo players.
3. **Software Engineering**: Building a responsive, state-aware web application using **Streamlit**.
4. **Explainable AI (XAI)**: Converting complex engine evaluations into instant, color-coded feedback (e.g., "Mistake: Missed a tactical capture").

🎯 **Why this matters:** Standard engines are "Black Boxes"—they give you the answer but not the *why*. This project bridges the gap between raw calculation and human understanding.

---

## 🛠️ Important Links & Tools:

- **[Live Demo App](https://beginnerchessai.streamlit.app/):** Interact with the live AI.
- **[Google Colab Notebook](https://colab.research.google.com/drive/1C2gJaQZedg_ivRwI6jVpdt47uuQp5l4G?usp=sharing):** View the full training pipeline, data extraction, and model evaluation code.
- **[Lichess Open Database](https://database.lichess.org/):** The source of the 20,000 beginner games used for training.
- **[Stockfish Engine](https://stockfishchess.org/):** The backend calculation engine.
- **[Streamlit Documentation](https://docs.streamlit.io/):** The framework used for the frontend UI.

---

## 🚀 Project Requirements

### 1. Data Pipeline & Machine Learning
#### Objective
To prove mathematically that beginner players benefit more from tactical simplicity than deep positional play.

#### Specifications
- **Data Source**: Lichess PGN Stream (Filtered for Elo < 1500).
- **Feature Extraction**: Extracted features: `Is_Check`, `Is_Capture`, `Center_Control`, `Queen_Movement`.
- **Model**: Logistic Regression.
- **Results**: Discovered that **Checks (w=0.57)** are 15x more weighted than **Center Control (w=0.03)** for beginner wins.

### 2. Application Development (The "Deep Logic" Engine)
#### Objective
Develop a UI that provides instant, context-aware feedback on every move without crashing or losing state.

#### Features implemented
- **Auto-Sync Logic**: Seamlessly handles deviations from loaded PGN games.
- **Visual Arrows**: Automatically visualizes the engine's plan on the board.
- **Move Classification**: Instantly labels moves as "Brilliant", "Good", "Inaccuracy", or "Blunder".
- **Natural Language Generation**: Generates explanations like *"Captures the Bishop"* or *"Escapes a threat"* instead of raw numbers.

---

## 📊 Analytics & Insights

The project includes generated reports proving the model's efficacy:

- **Feature Importance Graph**: Shows the learned weights of different chess concepts.
- **Confusion Matrix**: Evaluates the accuracy of the model in predicting winning moves.
- **Complexity Comparison**: Demonstrates how the "Deep Logic" filter reduces the cognitive load compared to raw Stockfish.

---

## 📂 Repository Structure

```text
deep-logic-chess/
│
├── .streamlit/
│   └── config.toml             # UI configuration (Theme, Wide Mode)
│
├── assets/                     # Generated graphs and visuals
│   ├── graph1_feature_imp.png  # Feature Importance Bar Chart
│   ├── graph2_confusion.png    # Model Confusion Matrix
│   └── graph3_complexity.png   # Complexity Comparison Graph
│
├── data/                       # Data processing files
│   ├── lichess_beginner.csv    # The extracted dataset (sample)
│   └── train_model.py          # Script used to train the ML model
│
├── src/                        # Source code
│   └── app.py                  # MAIN APPLICATION CODE (Streamlit + Logic)
│
├── requirements.txt            # Python dependencies (streamlit, chess, scikit-learn)
├── packages.txt                # System dependencies (stockfish)
├── runtime.txt                 # Python runtime version
├── README.md                   # Project documentation
└── LICENSE                     # MIT License


## 🛡️ License

This project is licensed under the [MIT License](LICENSE). You are free to use, modify, and share this project with proper attribution.

## 🌟 About Me
I'm Sachin Choudhary Machine Learning Enthusiast & Data Analysist I built this project to solve the frustration beginners face when using professional chess engines. By combining Big Data analysis with Game Theory, I created an engine that speaks the language of the player.
