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
    return tf.keras.models.load_model('my_chess_model_v2.keras')

try:
    model = load_my_model()
except:
    st.error("⚠️ Model file not found. Please upload 'my_chess_model_v2.keras'.")
    st.stop()

# --- SESSION STATE ---
if 'game_moves' not in st.session_state:
    st.session_state.game_moves = [] 
if 'move_index' not in st.session_state:
    st.session_state.move_index = -1 
if 'custom_pgn_loaded' not in st.session_state:
    st.session_state.custom_pgn_loaded = False

# --- HELPER FUNCTIONS ---

def get_current_board():
    board = chess.Board()
    for i in range(st.session_state.move_index + 1):
        if i < len(st.session_state.game_moves):
            board.push(st.session_state.game_moves[i])
    return board

def load_pgn(pgn_string):
    try:
        pgn = io.StringIO(pgn_string)
        game = chess.pgn.read_game(pgn)
        st.session_state.game_moves = list(game.mainline_moves())
        st.session_state.move_index = -1
        st.session_state.custom_pgn_loaded = True
        st.success(f"Game Loaded! Total moves: {len(st.session_state.game_moves)}")
    except:
        st.error("Invalid PGN format.")

# --- AI CORE LOGIC ---

def predict_move(board):
    """Single move prediction using your Neural Network"""
    # 1. Preprocess
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
    
    # 2. Predict
    pred = model.predict(input_data, verbose=0)
    pred_from = pred[0][0]
    pred_to = pred[1][0]
    
    # 3. Score Legal Moves
    best_move = None
    best_score = -1
    
    for move in board.legal_moves:
        score = pred_from[move.from_square] * pred_to[move.to_square]
        if score > best_score:
            best_score = score
            best_move = move
            
    return best_move

def get_continuation(board, depth=3):
    """Simulates the game forward to show a variation"""
    # Create a copy so we don't mess up the actual game
    temp_board = board.copy()
    sequence = []
    
    for _ in range(depth):
        if temp_board.is_game_over():
            break
        move = predict_move(temp_board)
        if move:
            sequence.append(move.san(temp_board)) # Store standard notation
            temp_board.push(move)
        else:
            break
            
    return " -> ".join(sequence)

def explain_move(board, move):
    explanation = []
    move_num = board.fullmove_number
    phase = "Opening" if move_num < 10 else "Middlegame"
    
    # Opening Logic
    if phase == "Opening":
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            explanation.append("🎯 **Control the Center:** Occupy the high ground.")
        elif board.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]:
             if move.from_square in [chess.B1, chess.G1, chess.B8, chess.G8]:
                explanation.append("🦄 **Development:** Getting pieces into the battle.")
        if board.is_castling(move):
            explanation.append("🏰 **Safety:** King safety is priority #1.")

    if board.is_capture(move):
        explanation.append("⚔️ **Capture:** A trade or capture was found.")
    
    if not explanation:
        explanation.append(f"💡 **Strategy:** AI identifies this as the best positional improvement.")
        
    return " ".join(explanation)

# --- UI LAYOUT ---

st.title("♟️ My AI Chess Engine")

# Sidebar
with st.sidebar:
    st.header("Controls")
    
    # Navigation
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("⏪ Start"):
            st.session_state.move_index = -1
            st.rerun()
    with c2:
        if st.button("⬅️ Prev"):
            if st.session_state.move_index >= 0:
                st.session_state.move_index -= 1
                st.rerun()
    with c3:
        if st.button("Next ➡️"):
            if st.session_state.move_index < len(st.session_state.game_moves) - 1:
                st.session_state.move_index += 1
                st.rerun()

    st.write("---")
    pgn_input = st.text_area("Paste PGN:")
    if st.button("Load PGN"):
        load_pgn(pgn_input)
        st.rerun()
        
    if st.button("Reset / Clear"):
        st.session_state.game_moves = []
        st.session_state.move_index = -1
        st.session_state.custom_pgn_loaded = False
        st.rerun()

# --- MAIN PAGE ---

board = get_current_board()
suggested_move = None
continuation_str = ""

# Only run AI if game is active
if not board.is_game_over():
    suggested_move = predict_move(board)
    if suggested_move:
        # Calculate continuation (Next 3 moves)
        continuation_str = get_continuation(board, depth=3)

col1, col2 = st.columns([1.5, 1])

with col1:
    # Draw Board
    arrows = []
    if suggested_move:
        arrows.append(chess.svg.Arrow(suggested_move.from_square, suggested_move.to_square, color="#0000cccc"))
        
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
    st.subheader("🤖 AI Analysis")
    
    if suggested_move:
        st.success(f"**Best Move:** {suggested_move.uci()}")
        st.info(f"**🔮 Continuation:** {continuation_str}...")
        
        reason = explain_move(board, suggested_move)
        st.markdown(f"**Why?** {reason}")
        
        if st.button(f"Play AI Suggestion ({suggested_move.uci()})"):
            st.session_state.game_moves = st.session_state.game_moves[:st.session_state.move_index+1] # Truncate future if diverting
            st.session_state.game_moves.append(suggested_move)
            st.session_state.move_index += 1
            st.rerun()
            
    else:
        if board.is_game_over():
            st.warning(f"Game Over: {board.result()}")

    st.write("---")
    st.write("### 🎮 Play Your Own Move")
    
    # 🕹️ MANUAL PLAY GRID
    legal_moves = [m for m in board.legal_moves]
    
    # Show buttons in a nice grid
    cols = st.columns(4)
    for i, move in enumerate(legal_moves):
        # We display SAN (e.g. "Nf3") on button, but use UCI (e2e4) for logic
        if cols[i % 4].button(move.san(), key=move.uci()):
            # Logic to play manual move
            st.session_state.game_moves = st.session_state.game_moves[:st.session_state.move_index+1] # Remove old future
            st.session_state.game_moves.append(move)
            st.session_state.move_index += 1
            st.rerun()

# --- HISTORY DISPLAY ---
st.write("---")
st.subheader("📜 Game History")
history_text = []
for i, move in enumerate(st.session_state.game_moves):
    num = (i // 2) + 1
    if i % 2 == 0:
        history_text.append(f"**{num}.** {move.san()}")
    else:
        history_text[-1] += f" {move.san()}"
        
st.text(" ".join(history_text))
