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

# --- NEW: MOVE QUALITY ANALYZER (Blunder/Best/Etc.) ---
def analyze_move_quality(board_before, move_played):
    """
    Compares the 'Best Move' score vs 'Played Move' score to assign a label.
    """
    engine = get_stockfish_engine()
    if not engine: return "N/A", "grey"

    # 1. Get score of the Best Possible Move
    limit = chess.engine.Limit(time=0.1)
    best_info = engine.analyse(board_before, limit)
    best_score_val = best_info["score"].relative.score(mate_score=10000)
    
    # 2. Get score of the Move Actually Played
    # We restrict search to ONLY the move played
    played_info = engine.analyse(board_before, limit, root_moves=[move_played])
    played_score_val = played_info["score"].relative.score(mate_score=10000)
    
    engine.quit()

    # 3. Calculate Difference (Centipawns)
    # Note: If best_score is mate, numbers are huge (10000). 
    diff = best_score_val - played_score_val

    # 4. Assign Label
    if diff < 15:
        return "🌟 Best Move", "green"
    elif diff < 50:
        return "✅ Good Move", "blue" # Slightly inferior but fine
    elif diff < 100:
        return "⚠️ Inaccuracy", "orange" # Noticeable drop
    elif diff < 250:
        return "❌ Mistake", "orange" # Bad
    else:
        return "💀 Blunder", "red" # Game losing

# --- HELPER 2: HYBRID PREDICTION ---
def predict_move_hybrid(board):
    engine = get_stockfish_engine()
    if not engine: return None

    # 1. Ask Stockfish for analysis
    limit = chess.engine.Limit(time=0.1)
    result = engine.analyse(board, limit, multipv=5)
    engine.quit()
    
    # 2. Killer Instinct (Mate)
    for info in result:
        if "score" in info and info["score"].is_mate():
            # Handle version differences
            mate_turns = None
            if hasattr(info["score"], "mate"): mate_turns = info["score"].mate()
            elif hasattr(info["score"], "relative") and hasattr(info["score"].relative, "mate"): 
                mate_turns = info["score"].relative.mate()
            
            if mate_turns is not None and mate_turns > 0:
                return info["pv"][0]

    # 3. Hybrid Selection
    top_moves = [info["pv"][0] for info in result if "pv" in info]
    if not top_moves: return None
    if len(top_moves) == 1: return top_moves[0] 

    # Prepare Data
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
    """Generates heuristic text explanation."""
    explanation = []
    temp_board = board.copy()
    temp_board.push(move)
    if temp_board.is_checkmate(): return "🏆 **Checkmate:** Wins the game immediately!"
    
    if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
        explanation.append("🎯 **Center:** Controls key central squares.")
    elif board.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]:
        if move.from_square in [chess.B1, chess.G1, chess.B8, chess.G8]:
            explanation.append("🦄 **Development:** Improves piece activity.")
    
    if board.is_castling(move): explanation.append("🏰 **Safety:** Protects the King.")
    if board.is_capture(move): explanation.append("⚔️ **Capture:** Wins material.")
    if board.gives_check(move): explanation.append("⚠️ **Check:** Forces opponent to react.")

    if not explanation: explanation.append(f"💡 **Positional:** Improves structure.")
    return " ".join(explanation)

# --- HELPER 4: NAVIGATION & PGN ---
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
        st.success(f"Loaded! {len(st.session_state.game_moves)} moves.")
    except:
        st.error("Invalid PGN.")

# --- SIDEBAR UI ---
with st.sidebar:
    st.header("🎮 Controls")
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
    
    st.divider()
    pgn_input = st.text_area("Paste PGN:", height=100)
    if st.button("📥 Load PGN"):
        load_pgn(pgn_input)
        st.rerun()
    if st.button("🗑️ Reset"):
        st.session_state.game_moves = []
        st.session_state.move_index = -1
        st.session_state.custom_pgn_loaded = False
        st.rerun()

# --- MAIN UI ---
st.title("♟️ Hybrid AI Coach")

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
        
    last_move = None
    if st.session_state.move_index >= 0 and st.session_state.game_moves:
        last_move = st.session_state.game_moves[st.session_state.move_index]

    board_svg = chess.svg.board(board=board, arrows=arrows, lastmove=last_move, size=500)
    st.image(f"data:image/svg+xml;base64,{base64.b64encode(board_svg.encode('utf-8')).decode('utf-8')}")

with col2:
    # --- EVALUATION PANEL ---
    if st.session_state.move_index >= 0:
        last_played_move = st.session_state.game_moves[st.session_state.move_index]
        prev_board = get_previous_board() 
        
        # 1. Get Classification (Blunder/Best/Mistake)
        label, color = analyze_move_quality(prev_board, last_played_move)
        
        # 2. Get Explanation
        feedback = explain_move(prev_board, last_played_move)
        
        # Display
        st.markdown(f"### Last Move: :{color}[{label}]")
        st.info(f"**Move:** {prev_board.san(last_played_move)} \n\n {feedback}")
        st.divider()
    # -----------------------

    st.subheader("🤖 AI Suggestion")
    
    if suggested_move:
        st.success(f"**Best Move:** {suggested_move.uci()}")
        st.caption(f"🔮 Line: {continuation_str}")
        st.write(f"**Why?** {explain_move(board, suggested_move)}")
        
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
    st.write("**Manual Play:**")
    legal_moves = [m for m in board.legal_moves]
    cols = st.columns(4)
    for i, move in enumerate(legal_moves):
        if cols[i % 4].button(board.san(move), key=move.uci()):
            st.session_state.game_moves = st.session_state.game_moves[:st.session_state.move_index+1]
            st.session_state.game_moves.append(move)
            st.session_state.move_index += 1
            st.rerun()

st.divider()
st.text("History: " + " ".join([chess.Board().san(m) for m in st.session_state.game_moves]))
