import streamlit as st
import chess
import chess.pgn
import chess.svg
import numpy as np
import tensorflow as tf
import io
import base64

# --- CONFIGURATION ---
st.set_page_config(page_title="Beginner AI Chess Coach", layout="wide")

# --- LOAD MODEL (V2) ---
@st.cache_resource
def load_my_model():
    # Ensure you upload 'my_chess_model_v2.keras'
    return tf.keras.models.load_model('my_chess_model_v2.keras')

try:
    model = load_my_model()
except:
    st.error("⚠️ Model file not found. Please upload 'my_chess_model_v2.keras'.")
    st.stop()

# --- SESSION STATE MANAGEMENT ---
if 'game_moves' not in st.session_state:
    st.session_state.game_moves = []  # List of moves in the loaded game
if 'move_index' not in st.session_state:
    st.session_state.move_index = -1  # -1 means start of game (no moves played)
if 'custom_pgn_loaded' not in st.session_state:
    st.session_state.custom_pgn_loaded = False

# --- HELPER FUNCTIONS ---

def get_current_board():
    """Reconstructs the board based on the current move index."""
    board = chess.Board()
    # Play moves up to the current index
    for i in range(st.session_state.move_index + 1):
        if i < len(st.session_state.game_moves):
            board.push(st.session_state.game_moves[i])
    return board

def load_pgn(pgn_string):
    try:
        pgn = io.StringIO(pgn_string)
        game = chess.pgn.read_game(pgn)
        
        # Reset state
        st.session_state.game_moves = list(game.mainline_moves())
        st.session_state.move_index = -1 # Start at beginning
        st.session_state.custom_pgn_loaded = True
        st.success(f"Game Loaded! Total moves: {len(st.session_state.game_moves)}")
    except:
        st.error("Invalid PGN format.")

# --- AI ENGINE LOGIC ---

def get_ai_suggestion(board):
    """Predicts move using the V2 Dual-Head Model"""
    # 1. Preprocess Board
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
    
    # 2. Get Prediction (Two Heads: From and To)
    pred = model.predict(input_data, verbose=0)
    pred_from = pred[0][0] # Probability distribution for Source Square
    pred_to = pred[1][0]   # Probability distribution for Target Square
    
    # 3. Find Best Legal Move
    best_move = None
    best_score = -1
    
    for move in board.legal_moves:
        # Score = Prob(From) * Prob(To)
        score = pred_from[move.from_square] * pred_to[move.to_square]
        
        if score > best_score:
            best_score = score
            best_move = move
            
    return best_move

def explain_move(board, move):
    """Generates beginner-friendly explanation"""
    explanation = []
    
    # Phase Detection
    move_num = board.fullmove_number
    phase = "Opening" if move_num < 10 else "Middlegame"
    if move_num > 30: phase = "Endgame"
    
    # Logic
    if phase == "Opening":
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            explanation.append("🎯 **Center Control:** Fighting for the high ground.")
        elif board.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]:
             if move.from_square in [chess.B1, chess.G1, chess.B8, chess.G8]: # Only if moving FROM start
                explanation.append("🦄 **Development:** Good active piece development.")
        if board.is_castling(move):
            explanation.append("🏰 **Safety:** King is safe, Rooks are connected.")

    if board.is_capture(move):
        explanation.append("⚔️ **Capture:** Winning material or trading.")
    
    if not explanation:
        explanation.append(f"💡 **Positional:** {phase} move to improve structure.")
        
    return " ".join(explanation)

# --- UI LAYOUT ---

st.title("♟️ AI Chess Tutor (Navigation Fixed)")

# Sidebar
with st.sidebar:
    st.header("Game Controls")
    
    # Navigation Buttons
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⏪ Start"):
            st.session_state.move_index = -1
            st.rerun()
        if st.button("⬅️ Prev"):
            if st.session_state.move_index >= 0:
                st.session_state.move_index -= 1
                st.rerun()
    with c2:
        if st.button("Next ➡️"):
            if st.session_state.move_index < len(st.session_state.game_moves) - 1:
                st.session_state.move_index += 1
                st.rerun()
        if st.button("End ⏩"):
            st.session_state.move_index = len(st.session_state.game_moves) - 1
            st.rerun()
            
    st.markdown("---")
    pgn_input = st.text_area("Paste PGN here:")
    if st.button("Load PGN"):
        load_pgn(pgn_input)
        st.rerun()
        
    if st.button("Reset Analysis"):
        st.session_state.game_moves = []
        st.session_state.move_index = -1
        st.session_state.custom_pgn_loaded = False
        st.rerun()

# --- MAIN DISPLAY ---

# 1. Get Board State
board = get_current_board()

# 2. Get AI Suggestion (Only if game is not over)
suggested_move = None
if not board.is_game_over():
    suggested_move = get_ai_suggestion(board)

col1, col2 = st.columns([1.5, 1])

with col1:
    # Draw Board with Arrow
    arrows = []
    if suggested_move:
        arrows.append(chess.svg.Arrow(suggested_move.from_square, suggested_move.to_square, color="#0000cccc"))
        
    # Highlight last move played
    last_move = None
    if st.session_state.move_index >= 0 and st.session_state.game_moves:
        last_move = st.session_state.game_moves[st.session_state.move_index]

    board_svg = chess.svg.board(
        board=board, 
        arrows=arrows,
        lastmove=last_move,
        size=500
    )
    st.image(f"data:image/svg+xml;base64,{base64.b64encode(board_svg.encode('utf-8')).decode('utf-8')}")

with col2:
    st.subheader(f"Move: {st.session_state.move_index + 1}")
    
    # Show PGN Navigation status
    if st.session_state.custom_pgn_loaded:
        st.info("📂 Reviewing Loaded Game")
    else:
        st.info("🆕 Free Analysis Mode")

    # AI Output
    if suggested_move:
        st.success(f"**AI Suggests:** {suggested_move.uci()}")
        reason = explain_move(board, suggested_move)
        st.markdown(reason)
        
        # Play Button (Only works in Free Analysis mode usually, but allowed here)
        if st.button(f"Play {suggested_move.uci()}"):
            # If we are in "Free Analysis" mode (no PGN loaded), we append to history
            st.session_state.game_moves.append(suggested_move)
            st.session_state.move_index += 1
            st.rerun()
            
    # Show History (Last 5 moves)
    st.write("---")
    st.write("**Recent Moves:**")
    history_text = ""
    start_idx = max(0, st.session_state.move_index - 4)
    for i in range(start_idx, st.session_state.move_index + 1):
        move_san = st.session_state.game_moves[i]
        history_text += f"{i+1}. {move_san}  \n"
    st.text(history_text)
