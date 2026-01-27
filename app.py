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
STOCKFISH_PATH = "/usr/games/stockfish"

# --- LOAD MODEL ---
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
        return None

# --- HELPER 2: ANALYZE MOVE QUALITY (BLUNDER/BEST/ETC) ---
def analyze_move_quality(board_before, move_played):
    """
    Compares the played move against the engine's best move to determine quality.
    Returns: (Label, Color, Explanation)
    """
    engine = get_stockfish_engine()
    if not engine: return ("Unknown", "grey", "Engine not available")

    # 1. Analyze the position BEFORE the move (to find the BEST possible score)
    # We look deeper (time=0.3) for accuracy
    limit = chess.engine.Limit(time=0.3)
    
    # Get best move evaluation
    info_best = engine.analyse(board_before, limit)
    best_score_val = info_best["score"].relative.score(mate_score=10000)
    
    # 2. Analyze the ACTUAL move played
    # We restrict search to just the move played
    info_played = engine.analyse(board_before, limit, root_moves=[move_played])
    played_score_val = info_played["score"].relative.score(mate_score=10000)
    
    engine.quit()

    # Calculate Difference (How much value did we lose?)
    # If best was 500 and we played 500, diff is 0.
    # If best was 500 and we played 0 (blunder), diff is 500.
    diff = best_score_val - played_score_val

    # 3. Categorize
    label = "Good"
    color = "blue"
    reason = "Solid play."

    # Logic for categories
    if diff <= 10: 
        label = "🏆 Best Move"
        color = "green"
        reason = "Perfect! You found the engine's top choice."
    elif diff <= 50:
        label = "✅ Excellent"
        color = "lightgreen"
        reason = "Very strong move, almost perfect."
    elif diff <= 150:
        label = "⚠️ Inaccuracy"
        color = "orange"
        reason = "Slightly passive or imprecise."
    elif diff <= 300:
        label = "❌ Mistake"
        color = "darkorange"
        reason = f"You lost advantage (Eval drop: {diff/100:.1f})."
    else:
        label = "💀 Blunder"
        color = "red"
        reason = f"Disastrous! You lost significant material or the game (Eval drop: {diff/100:.1f})."
        
    # Check for Brilliant (Hard to code perfectly, but generally if you sacrifice material for a gain)
    # Simple check: If you captured a piece of higher value but eval stayed high? 
    # For beginner AI, we stick to Eval Diff.
    
    return label, color, reason

# --- HELPER 3: HYBRID PREDICTION ---
def predict_move_hybrid(board):
    engine = get_stockfish_engine()
    if not engine: return None

    limit = chess.engine.Limit(time=0.1)
    result = engine.analyse(board, limit, multipv=5)
    engine.quit()
    
    # Check for Forced Mate
    for info in result:
        if "score" in info and info["score"].is_mate():
            if info["score"].relative.mate() > 0: return info["pv"][0]

    top_moves = [info["pv"][0] for info in result if "pv" in info]
    if not top_moves: return None
    if len(top_moves) == 1: return top_moves[0] 

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
        score = pred_from[move.from_square] * pred_to[move.to_square]
        if score > best_hybrid_score:
            best_hybrid_score = score
            best_hybrid_move = move
            
    return best_hybrid_move if best_hybrid_move else top_moves[0]

# --- HELPER 4: EXPLANATION ---
def explain_move_heuristics(board, move):
    explanation = []
    if board.is_capture(move): explanation.append("⚔️ Capture")
    if board.gives_check(move): explanation.append("⚠️ Check")
    if board.is_castling(move): explanation.append("🏰 Castle")
    
    if not explanation: return "Positional Move"
    return ", ".join(explanation)

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

# --- HELPER 5: NAVIGATION ---
def get_current_board():
    board = chess.Board()
    for i in range(st.session_state.move_index + 1):
        if i < len(st.session_state.game_moves):
            board.push(st.session_state.game_moves[i])
    return board

def get_previous_board():
    board = chess.Board()
    for i in range(st.session_state.move_index):
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
        st.success(f"Loaded {len(st.session_state.game_moves)} moves.")
    except:
        st.error("Invalid PGN.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎮 Controls")
    c1, c2 = st.columns(2)
    if c1.button("⏪ Start"): 
        st.session_state.move_index = -1
        st.rerun()
    if c2.button("⬅️ Prev"): 
        if st.session_state.move_index >= 0:
            st.session_state.move_index -= 1
            st.rerun()
            
    c3, c4 = st.columns(2)
    if c3.button("Next ➡️"): 
        if st.session_state.move_index < len(st.session_state.game_moves) - 1:
            st.session_state.move_index += 1
            st.rerun()
    if c4.button("End ⏩"): 
        st.session_state.move_index = len(st.session_state.game_moves) - 1
        st.rerun()
        
    st.divider()
    pgn_input = st.text_area("PGN Input")
    if st.button("Load PGN"): load_pgn(pgn_input)
    if st.button("Reset"):
        st.session_state.game_moves = []
        st.session_state.move_index = -1
        st.session_state.custom_pgn_loaded = False
        st.rerun()

# --- MAIN UI ---
st.title("♟️ Pro Chess Analyst")

board = get_current_board()
suggested_move = None
continuation_str = ""

if not board.is_game_over():
    suggested_move = predict_move_hybrid(board)
    if suggested_move:
        continuation_str = get_continuation(board, depth=3)

col1, col2 = st.columns([1.5, 1])

with col1:
    arrows = []
    if suggested_move:
        arrows.append(chess.svg.Arrow(suggested_move.from_square, suggested_move.to_square, color="#0000cccc"))
    last_move = st.session_state.game_moves[st.session_state.move_index] if st.session_state.move_index >= 0 else None
    
    board_svg = chess.svg.board(board=board, arrows=arrows, lastmove=last_move, size=500)
    st.image(f"data:image/svg+xml;base64,{base64.b64encode(board_svg.encode('utf-8')).decode('utf-8')}")

with col2:
    # --- 🔍 MOVE QUALITY ANALYSIS ---
    if st.session_state.move_index >= 0:
        last_played_move = st.session_state.game_moves[st.session_state.move_index]
        prev_board = get_previous_board()
        
        # Determine Quality
        label, color, reason = analyze_move_quality(prev_board, last_played_move)
        
        st.markdown(f"### Last Move: **{prev_board.san(last_played_move)}**")
        
        # Display Badge
        st.markdown(f"""
        <div style="background-color: {color}; padding: 10px; border-radius: 5px; color: white; text-align: center; font-weight: bold; font-size: 20px;">
            {label}
        </div>
        """, unsafe_allow_html=True)
        
        st.write(f"**Analysis:** {reason}")
        st.divider()
    # -------------------------------

    st.subheader("🤖 AI Advice")
    if suggested_move:
        st.success(f"**Best Move:** {suggested_move.uci()}")
        st.caption(f"Line: {continuation_str}")
        st.write(f"**Type:** {explain_move_heuristics(board, suggested_move)}")
        
        if st.button(f"Play {board.san(suggested_move)}"):
            st.session_state.game_moves = st.session_state.game_moves[:st.session_state.move_index+1]
            st.session_state.game_moves.append(suggested_move)
            st.session_state.move_index += 1
            st.rerun()

    st.write("---")
    legal_moves = [m for m in board.legal_moves]
    cols = st.columns(4)
    for i, move in enumerate(legal_moves):
        if cols[i % 4].button(board.san(move), key=move.uci()):
            st.session_state.game_moves = st.session_state.game_moves[:st.session_state.move_index+1]
            st.session_state.game_moves.append(move)
            st.session_state.move_index += 1
            st.rerun()
