import streamlit as st
import chess
import chess.pgn
import chess.svg
import chess.engine
import numpy as np
import tensorflow as tf
import io
import base64
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="Beginner AI Chess Coach", layout="wide")

# --- PATH TO STOCKFISH ---
# On Streamlit Cloud (Linux), Stockfish is usually here after apt-install
STOCKFISH_PATH = "/usr/games/stockfish"

# If running locally on Windows, you might need to change this path
# STOCKFISH_PATH = r"C:\path\to\your\stockfish.exe"

# --- LOAD YOUR MODEL ---
@st.cache_resource
def load_my_model():
    return tf.keras.models.load_model('my_chess_model_v2.keras')

try:
    model = load_my_model()
except:
    st.error("⚠️ Model file not found. Please upload 'my_chess_model_v2.keras'.")
    st.stop()

# --- HELPER FUNCTIONS ---

def get_stockfish_engine():
    """Initializes Stockfish engine."""
    try:
        # Check if custom path exists, otherwise try system command
        path = STOCKFISH_PATH if os.path.exists(STOCKFISH_PATH) else "stockfish"
        engine = chess.engine.SimpleEngine.popen_uci(path)
        return engine
    except Exception as e:
        st.error(f"Stockfish not found at {STOCKFISH_PATH}. Please ensure it is installed.")
        return None

def predict_move_hybrid(board):
    """
    HYBRID LOGIC: 
    1. Stockfish generates Top 5 SAFE moves.
    2. Neural Network picks the 'most human' one from that safe list.
    """
    engine = get_stockfish_engine()
    if not engine:
        return None

    # 1. Ask Stockfish for Top 5 Moves (Time limit 0.1s for speed)
    result = engine.analyse(board, chess.engine.Limit(time=0.1), multipv=5)
    engine.quit()

    top_moves = [info["pv"][0] for info in result]
    
    # If only one legal move or fewer, just return the best one
    if len(top_moves) == 0: return None
    if len(top_moves) == 1: return top_moves[0]

    # 2. Prepare Data for Neural Network Ranking
    # We need to see which of these 5 moves the NN gives the highest probability
    
    # Preprocess board once
    pieces = {'p': 1, 'n': 2, 'b': 3, 'r': 4, 'q': 5, 'k': 6,
              'P': 7, 'N': 8, 'B': 9, 'R': 10, 'Q': 11, 'K': 12}
    foo = []
    for cell in board.epd().split(' ')[0]:
        if cell.isdigit():
            for i in range(int(cell)): foo.append(0)
        elif cell == '/': continue
        else: foo.append(pieces[cell])
    
    matrix = np.array(foo).reshape(8, 8)
    matrix_one_hot = (np.arange(13) == matrix[..., None]).astype(np.float32)
    input_data = np.expand_dims(matrix_one_hot, axis=0)
    
    # Get NN Predictions
    pred = model.predict(input_data, verbose=0)
    pred_from = pred[0][0] # Source square probs
    pred_to = pred[1][0]   # Target square probs

    # 3. Score the Stockfish Moves using NN
    best_hybrid_move = None
    best_hybrid_score = -1

    for move in top_moves:
        # Score = Probability that NN would have chosen this move
        # We multiply Source Prob * Target Prob
        score = pred_from[move.from_square] * pred_to[move.to_square]
        
        # We prefer the move the NN likes the most, BUT it must be in Stockfish's top 5
        if score > best_hybrid_score:
            best_hybrid_score = score
            best_hybrid_move = move
            
    # Fallback: If NN is confused (score 0), just take Stockfish's #1 choice
    if best_hybrid_move is None:
        best_hybrid_move = top_moves[0]
        
    return best_hybrid_move

def get_continuation(board, depth=3):
    temp_board = board.copy()
    sequence = []
    for _ in range(depth):
        if temp_board.is_game_over(): break
        move = predict_move_hybrid(temp_board) # Use Hybrid here too!
        if move:
            sequence.append(temp_board.san(move))
            temp_board.push(move)
        else:
            break
    return " -> ".join(sequence)

def explain_move(board, move):
    explanation = []
    # Simple logic to generate text
    if board.is_capture(move):
        explanation.append("⚔️ **Capture:** Capturing material is good if safe.")
    if board.gives_check(move):
        explanation.append("⚠️ **Check:** Force the King to move.")
    if board.is_castling(move):
        explanation.append("🏰 **Safety:** Castling connects Rooks and safeguards the King.")
        
    move_rank = move.to_square // 8
    if move_rank == 3 or move_rank == 4: # Center ranks (approx)
         explanation.append("🎯 **Center Control:** Fighting for the middle of the board.")
         
    if not explanation:
        explanation.append("💡 **Positional:** A solid move to improve piece activity.")
    return " ".join(explanation)

# --- APP LOGIC (Simplified for clarity) ---

if 'game_moves' not in st.session_state: st.session_state.game_moves = []
if 'move_index' not in st.session_state: st.session_state.move_index = -1

# [Insert Load PGN / Reset Logic from previous version here if needed]
# For brevity, I am keeping the core UI logic below

def get_board():
    board = chess.Board()
    for i in range(st.session_state.move_index + 1):
        if i < len(st.session_state.game_moves):
            board.push(st.session_state.game_moves[i])
    return board

board = get_board()
suggested_move = None
continuation_str = ""

if not board.is_game_over():
    # USES HYBRID ENGINE NOW
    suggested_move = predict_move_hybrid(board)
    if suggested_move:
        continuation_str = get_continuation(board, depth=3)

# --- UI DRAWING ---
col1, col2 = st.columns([1.5, 1])
with col1:
    arrows = [chess.svg.Arrow(suggested_move.from_square, suggested_move.to_square, color="#0000cccc")] if suggested_move else []
    last_move = st.session_state.game_moves[st.session_state.move_index] if st.session_state.move_index >= 0 else None
    
    st.image(f"data:image/svg+xml;base64,{base64.b64encode(chess.svg.board(board, arrows=arrows, lastmove=last_move, size=500).encode('utf-8')).decode('utf-8')}")

with col2:
    st.title("♟️ Hybrid AI Coach")
    st.caption("Powered by Stockfish (Safety) + Neural Network (Style)")
    
    if suggested_move:
        st.success(f"**Suggestion:** {suggested_move.uci()}")
        st.info(f"**Line:** {continuation_str}")
        st.write(explain_move(board, suggested_move))
        
        if st.button(f"Play {board.san(suggested_move)}"):
            st.session_state.game_moves = st.session_state.game_moves[:st.session_state.move_index+1]
            st.session_state.game_moves.append(suggested_move)
            st.session_state.move_index += 1
            st.rerun()

    st.write("---")
    st.write("**Play Your Own Move:**")
    cols = st.columns(4)
    for i, m in enumerate(board.legal_moves):
        if cols[i%4].button(board.san(m), key=m.uci()):
            st.session_state.game_moves = st.session_state.game_moves[:st.session_state.move_index+1]
            st.session_state.game_moves.append(m)
            st.session_state.move_index += 1
            st.rerun()

    # Manual Controls
    st.write("---")
    c1, c2 = st.columns(2)
    if c1.button("⬅️ Undo"):
        if st.session_state.move_index >= 0:
            st.session_state.move_index -= 1
            st.rerun()
    if c2.button("🔄 Reset"):
        st.session_state.game_moves = []
        st.session_state.move_index = -1
        st.rerun()
