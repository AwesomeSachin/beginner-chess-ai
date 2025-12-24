import streamlit as st
import chess
import chess.pgn
import chess.engine
import numpy as np
import tensorflow as tf
import io
import os

import os

@st.cache_resource
def load_model():
    # 1. Get the current directory of app.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. DEBUG: Show us where we are and what is here
    st.write(f"📂 Current Working Directory: `{current_dir}`")
    files_in_dir = os.listdir(current_dir)
    st.write(f"📄 Files found here: `{files_in_dir}`")
    
    # 3. Construct the path
    model_path = os.path.join(current_dir, 'trap_model.h5')
    
    # 4. Check if file exists
    if not os.path.exists(model_path):
        st.error(f"❌ Error: 'trap_model.h5' was not found in {current_dir}.")
        return None
        
    # 5. Load
    try:
        return tf.keras.models.load_model(model_path)
    except Exception as e:
        st.error(f"⚠️ File found, but failed to load. It might be corrupt or an LFS pointer. Error: {e}")
        return None

import os  # Make sure this is imported at the top

@st.cache_resource
def load_model():
    # Get the absolute path to the directory where app.py is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Construct the full path to the model file
    model_path = os.path.join(current_dir, 'trap_model.h5')
    
    # Load the model using this absolute path
    return tf.keras.models.load_model(model_path)

# --- PAGE CONFIG ---
st.set_page_config(page_title="Chess Trap Detector", layout="wide")

st.title("♟️ The Chess Trap Detector")
st.write("Paste your game PGN below. This AI detects if you missed a 'Trap' — a move that looks safe but is actually a blunder.")

# --- LOAD RESOURCES ---
@st.cache_resource
def load_model():
    # Load the trained model
    return tf.keras.models.load_model('trap_model.h5')

@st.cache_resource
def load_engine():
    # Note: Stockfish setup on Streamlit Cloud is tricky. 
    # Usually, we need a static binary. For now, we will try to detect generic installation
    # OR you might need to upload a stockfish binary to your repo.
    # For this simple demo, we will try to use a basic check or just the AI model.
    return None 

model = load_model()

# --- HELPER: FEN TO MATRIX ---
def fen_to_matrix(fen):
    board = chess.Board(fen)
    matrix = np.zeros((8, 8, 12), dtype=int)
    piece_map = {
        'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,
        'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11
    }
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            row = 7 - (square // 8)
            col = square % 8
            layer = piece_map[piece.symbol()]
            matrix[row, col, layer] = 1
    return matrix

# --- INPUT SECTION ---
pgn_input = st.text_area("Paste PGN Text Here:", height=200)

if st.button("Analyze Game"):
    if pgn_input:
        pgn_io = io.StringIO(pgn_input)
        game = chess.pgn.read_game(pgn_io)
        
        if game:
            board = game.board()
            st.success(f"Game Loaded: {game.headers.get('White')} vs {game.headers.get('Black')}")
            
            # Iterate through moves
            move_count = 1
            for move in game.mainline_moves():
                board.push(move)
                fen = board.fen()
                
                # PREDICT WITH AI
                # Convert current board to matrix
                input_matrix = fen_to_matrix(fen)
                # Reshape for the model (1, 8, 8, 12)
                input_matrix = np.expand_dims(input_matrix, axis=0)
                
                # Get prediction (0 to 1)
                prediction = model.predict(input_matrix, verbose=0)[0][0]
                
                # If prediction is high (> 0.5), it's a "Trap" scenario
                # You can adjust this threshold
                if prediction > 0.8: 
                    st.markdown(f"---")
                    st.warning(f"⚠️ **Trap Opportunity Detected at Move {move_count}**")
                    st.image(f"https://fen-to-image.com/image/{fen}", width=300)
                    st.write(f"**AI Confidence:** {round(prediction * 100, 1)}% that this position contains a tricky trap.")
                
                move_count += 1
        else:
            st.error("Invalid PGN. Please check your text.")
