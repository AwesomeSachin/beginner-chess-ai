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
# Adjust this if you are running locally on Windows (e.g., r"C:\stockfish\stockfish.exe")
# For Streamlit Cloud (Linux), this default usually works if installed via packages.txt
STOCKFISH_PATH = "/usr/games/stockfish"

# --- LOAD YOUR NEURAL NETWORK ---
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

# --- HELPER 1: STOCKFISH ENGINE ---
def get_stockfish_engine():
    try:
        path = STOCKFISH_PATH if os.path.exists(STOCKFISH_PATH) else "stockfish"
        return chess.engine.SimpleEngine.popen_uci(path)
    except:
        st.error(f"Stockfish engine not found. Ensure it is installed in packages.txt.")
        return None

# --- HELPER 2: HYBRID PREDICTION (The "Brain") ---
def predict_move_hybrid(board):
    """
    1. Stockfish gets top 5 SAFE moves.
    2. Neural Network picks the most HUMAN/Instructive one.
    """
    engine = get_stockfish_engine()
    if not engine: return None

    # 1. Stockfish filters blunders (Time limit 0.1s)
    result = engine.analyse(board, chess.engine.Limit(time=0.1), multipv=5)
    engine.quit()
    
    top_moves = [info["pv"][0] for info in result if "pv" in info]
    
    if not top_moves: return None
    if len(top_moves) == 1: return top_moves[0] # Only one good move

    # 2. Neural Network Evaluates "Style"
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
    
    pred = model.predict(input_data, verbose=0)
    pred_from = pred[0][0]
    pred_to = pred[1][0]

    best_hybrid_move = None
    best_hybrid_score = -1

    for move in top_moves:
        # Score = Probability NN assigns to this safe move
        score = pred_from[move.from_square] * pred_to[move.to_square]
        if score > best_hybrid_score:
            best_hybrid_score = score
            best_hybrid_move = move
            
    return best_hybrid_move if best_hybrid_move else top_moves[0]

# --- HELPER 3: CONTINUATION & EXPLANATION ---
def get_continuation(board, depth=3):
    temp_board = board.copy()
    sequence = []
    for _ in range(depth):
        if temp_board.is_game_over(): break
        move = predict_move_hybrid(temp_board)
        if move:
            sequence.append(temp_board.san(move))
            temp_board.push(move)
        else:
            break
    return " -> ".join(sequence)

def explain_move(board, move):
    explanation = []
    phase = "Opening" if board.fullmove_number < 10 else "Middlegame"
    
    if phase == "Opening":
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            explanation.append("🎯 **Center Control:** Taking the high ground.")
        elif board.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]:
             if move.from_square in [chess.B1, chess.G1, chess.B8, chess.G8]:
                explanation.append("🦄 **Development:** Getting pieces into the game.")
        if board.is_castling(move):
            explanation.append("🏰 **Safety:** King is tucked away safely.")

    if board.is_capture(move):
        explanation.append("⚔️ **Capture:** A safe material gain or trade.")
    
    if not explanation:
        explanation.append(f"💡 **Positional:** Improving piece activity and structure.")
        
    return " ".join(explanation)

# --- HELPER 4: NAVIGATION & PGN ---
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
        st.success(f"Loaded! {len(st.session_state.game_moves)} moves.")
    except:
        st.error("Invalid PGN.")

# --- SIDEBAR UI (The Left Side System) ---
with st.sidebar:
    st.header("🎮 Game Controls")
    
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
    st.subheader("📋 Load Game")
    pgn_input = st.text_area("Paste PGN here (Lichess/Chess.com):", height=100)
    if st.button("📥 Load PGN"):
        load_pgn(pgn_input)
        st.rerun()
        
    if st.button("🗑️ Reset Board"):
        st.session_state.game_moves = []
        st.session_state.move_index = -1
        st.session_state.custom_pgn_loaded = False
        st.rerun()

# --- MAIN PAGE UI ---
st.title("♟️ Hybrid AI Chess Coach")

board = get_current_board()
suggested_move = None
continuation_str = ""

# AI Calculation (Only if active game)
if not board.is_game_over():
    suggested_move = predict_move_hybrid(board)
    if suggested_move:
        continuation_str = get_continuation(board, depth=3)

col1, col2 = st.columns([1.5, 1])

with col1:
    # Draw Board with Arrows
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
    st.subheader(f"Move: {st.session_state.move_index + 1}")
    
    if suggested_move:
        st.success(f"**AI Suggests:** {suggested_move.uci()}")
        st.info(f"**🔮 Continuation:** {continuation_str}")
        
        reason = explain_move(board, suggested_move)
        st.markdown(f"**Why?** {reason}")
        
        if st.button(f"▶️ Play {board.san(suggested_move)}"):
            st.session_state.game_moves = st.session_state.game_moves[:st.session_state.move_index+1]
            st.session_state.game_moves.append(suggested_move)
            st.session_state.move_index += 1
            st.rerun()
            
    elif board.is_game_over():
        st.warning(f"Game Over: {board.result()}")
    else:
        st.warning("Thinking...")

    st.write("---")
    st.write("**Manual Play (Click to move):**")
    
    # Manual Buttons Grid
    legal_moves = [m for m in board.legal_moves]
    cols = st.columns(4)
    for i, move in enumerate(legal_moves):
        if cols[i % 4].button(board.san(move), key=move.uci()):
            st.session_state.game_moves = st.session_state.game_moves[:st.session_state.move_index+1]
            st.session_state.game_moves.append(move)
            st.session_state.move_index += 1
            st.rerun()

# --- HISTORY ---
st.write("---")
st.subheader("📜 History")
hist_board = chess.Board()
history_text = []
for i, m in enumerate(st.session_state.game_moves):
    move_str = hist_board.san(m)
    hist_board.push(m)
    if i % 2 == 0: history_text.append(f"**{(i//2)+1}.** {move_str}")
    else: history_text[-1] += f" {move_str}"
st.text(" ".join(history_text))
