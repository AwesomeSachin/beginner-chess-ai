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
st.set_page_config(page_title="Pro Chess Analyst", layout="wide")

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

# --- HELPER 2: HYBRID PREDICTION (WITH BLUNDER GUARD) ---
def predict_move_hybrid(board):
    engine = get_stockfish_engine()
    if not engine: return None

    # 1. Ask Stockfish for Top 5 Moves
    limit = chess.engine.Limit(time=0.1)
    result = engine.analyse(board, limit, multipv=5)
    engine.quit()
    
    # 2. KILLER INSTINCT: Check for Mate or Winning Advantage
    best_info = result[0]
    if "score" in best_info:
        score = best_info["score"]
        if score.is_mate():
            mate_turns = None
            if hasattr(score, "mate"): mate_turns = score.mate()
            elif hasattr(score, "relative") and hasattr(score.relative, "mate"): mate_turns = score.relative.mate()
            if mate_turns is not None and mate_turns > 0:
                return best_info["pv"][0] # Force Mate

        # If winning by huge margin (> +6.0), just play best move
        val = score.relative.score(mate_score=10000)
        if val is not None and val > 600:
             return best_info["pv"][0]

    # 3. HYBRID SELECTION
    top_moves = [info["pv"][0] for info in result if "pv" in info]
    if not top_moves: return None
    
    # Get NN Predictions
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

    # 4. BLUNDER GUARD
    if best_hybrid_move and best_hybrid_move != top_moves[0]:
        best_eval = result[0]["score"].relative.score(mate_score=10000)
        hybrid_eval = -10000
        for info in result:
            if "pv" in info and info["pv"][0] == best_hybrid_move:
                hybrid_eval = info["score"].relative.score(mate_score=10000)
                break
        
        if best_eval is not None and hybrid_eval is not None:
            if (best_eval - hybrid_eval) > 150:
                return top_moves[0] # Override if too risky

    return best_hybrid_move if best_hybrid_move else top_moves[0]

# --- HELPER 3: QUALITY ANALYSIS ---
def analyze_move_quality(board_before, move_played):
    engine = get_stockfish_engine()
    if not engine: return ("Unknown", "grey", "Engine unavailable")

    limit = chess.engine.Limit(time=0.3)
    info_best = engine.analyse(board_before, limit)
    best_score = info_best["score"].relative.score(mate_score=10000)
    
    info_played = engine.analyse(board_before, limit, root_moves=[move_played])
    played_score = info_played["score"].relative.score(mate_score=10000)
    engine.quit()

    if best_score is None or played_score is None: return ("Unknown", "grey", "Score error")

    diff = best_score - played_score

    if diff <= 15: return ("🏆 Best Move", "green", "Perfect play.")
    if diff <= 50: return ("✅ Excellent", "lightgreen", "Strong move.")
    if diff <= 150: return ("⚠️ Inaccuracy", "orange", "Slightly passive.")
    if diff <= 300: return ("❌ Mistake", "darkorange", f"Eval drop: {diff/100:.1f}")
    return ("💀 Blunder", "red", f"Disastrous drop: {diff/100:.1f}")

# --- HELPER 4: EXPLANATION ---
def explain_move_heuristics(board, move):
    explanation = []
    
    # Check checks/captures first
    temp = board.copy()
    temp.push(move)
    if temp.is_checkmate(): return "🏆 **Checkmate:** This move wins the game!"
    if temp.is_check(): explanation.append("⚠️ **Check:** Force the King to move.")
    
    if board.is_capture(move): explanation.append("⚔️ **Capture:** Winning material or trading.")
    if board.is_castling(move): explanation.append("🏰 **Castle:** King safety improved.")
    
    # Positional
    if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
        explanation.append("🎯 **Center Control:** Occupying the high ground.")
    elif board.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]:
         if move.from_square in [chess.B1, chess.G1, chess.B8, chess.G8]:
            explanation.append("🦄 **Development:** Getting pieces into the battle.")

    if not explanation: return "💡 **Positional:** Improving piece activity."
    return " ".join(explanation)

def get_continuation(board, depth=3):
    temp = board.copy()
    sequence = []
    for _ in range(depth):
        if temp.is_game_over(): break
        move = predict_move_hybrid(temp)
        if move:
            sequence.append(temp.san(move))
            temp.push(move)
        else: break
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
    # --- ANALYSIS BADGE ---
    if st.session_state.move_index >= 0:
        last_played_move = st.session_state.game_moves[st.session_state.move_index]
        prev_board = get_previous_board()
        label, color, reason = analyze_move_quality(prev_board, last_played_move)
        
        st.markdown(f"### Last Move: **{prev_board.san(last_played_move)}**")
        st.markdown(f"""
        <div style="background-color: {color}; padding: 10px; border-radius: 5px; color: white; text-align: center; font-weight: bold;">
            {label}
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"Reason: {reason}")
        st.divider()

    # --- AI SUGGESTION (RESTORED FORMAT) ---
    st.subheader("🤖 AI Suggestion")
    if suggested_move:
        # 1. The Green Box for Best Move
        st.success(f"**Best Move:** {suggested_move.uci()}")
        
        # 2. The Blue Box for Continuation
        st.info(f"🔮 **Continuation:** {continuation_str}")
        
        # 3. The Text Explanation
        reason = explain_move_heuristics(board, suggested_move)
        st.write(f"**Why?** {reason}")
        
        # 4. Play Button
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

# --- HISTORY SECTION ---
st.divider()
st.subheader("📜 Game History")
hist_board = chess.Board()
history_text = []
for i, m in enumerate(st.session_state.game_moves):
    move_san = hist_board.san(m)
    hist_board.push(m)
    if i % 2 == 0:
        history_text.append(f"**{(i//2)+1}.** {move_san}")
    else:
        history_text[-1] += f" {move_san}"

st.markdown(" ".join(history_text))
