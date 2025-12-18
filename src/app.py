# =========================================================
# Deep Logic Chess (XAI Edition)
# Central Nervous System — app.py
# =========================================================

import streamlit as st
import chess
import chess.engine
import chess.svg
import chess.pgn
import io
import base64

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="Deep Logic Chess", layout="wide")

STOCKFISH_PATH = "/usr/games/stockfish"  # Streamlit Cloud compatible

# ML Weights (Learned in Colab)
W_CHECK   = 0.5792
W_CAPTURE = 0.1724
W_CENTER  = 0.0365

CENTER_SQUARES = [chess.E4, chess.D4, chess.E5, chess.D5]

# =========================================================
# SESSION STATE (MEMORY)
# =========================================================
if "board" not in st.session_state:
    st.session_state.board = chess.Board()

if "game_moves" not in st.session_state:
    st.session_state.game_moves = []

if "move_index" not in st.session_state:
    st.session_state.move_index = 0

if "feedback" not in st.session_state:
    st.session_state.feedback = None

# =========================================================
# HELPER: RENDER BOARD
# =========================================================
def render_board(board, arrow=None):
    arrows = []
    if arrow:
        arrows.append(chess.svg.Arrow(arrow.from_square, arrow.to_square, color="#4CAF50"))

    svg = chess.svg.board(
        board=board,
        size=520,
        arrows=arrows,
        lastmove=board.peek() if board.move_stack else None
    )

    b64 = base64.b64encode(svg.encode()).decode()
    return f"<img src='data:image/svg+xml;base64,{b64}'/>"

# =========================================================
# CORE ANALYSIS ENGINE
# =========================================================
def analyze_position(board):
    """
    1. Ask Stockfish for top moves
    2. Apply ML weights
    3. Return ranked candidates
    """

    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    info = engine.analyse(board, chess.engine.Limit(time=0.4), multipv=5)

    candidates = []

    best_raw = info[0]["score"].relative.score(mate_score=10000) or 0

    for line in info:
        move = line["pv"][0]
        raw = line["score"].relative.score(mate_score=10000) or 0

        bonus = 0
        board.push(move)

        if board.is_check():
            bonus += W_CHECK
        if board.is_capture(move):
            bonus += W_CAPTURE
        if move.to_square in CENTER_SQUARES:
            bonus += W_CENTER

        board.pop()

        final_score = (raw / 100) + bonus

        candidates.append({
            "move": move,
            "san": board.san(move),
            "raw": raw / 100,
            "score": final_score
        })

    engine.quit()

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates, best_raw / 100

# =========================================================
# EXPLANATION ENGINE (GOOD MOVE)
# =========================================================
def explain_good(board, move):
    reasons = []

    if board.is_capture(move):
        piece = board.piece_at(move.to_square)
        if piece:
            reasons.append(f"Captures {chess.piece_name(piece.piece_type)}.")

    board.push(move)
    if board.is_check():
        reasons.append("Gives check.")

    board.pop()

    if move.to_square in CENTER_SQUARES:
        reasons.append("Controls the center.")

    if board.is_castling(move):
        reasons.append("Castles for king safety.")

    if not reasons:
        reasons.append("Improves position.")

    return " ".join(reasons)

# =========================================================
# EXPLANATION ENGINE (BAD MOVE)
# =========================================================
def explain_bad(board, move, eval_drop):
    board_after = board.copy()
    board_after.push(move)

    # Hung piece detection
    if eval_drop > 1.0:
        if board_after.is_attacked_by(board_after.turn, move.to_square):
            if not board_after.is_attacked_by(not board_after.turn, move.to_square):
                return "Blunder. You left a piece hanging."

    if eval_drop > 0.7:
        return "Mistake. This move weakens your position."

    return "Inaccuracy. A passive move."

# =========================================================
# MOVE JUDGMENT
# =========================================================
def judge_move(board_before, played_move, best_eval, new_eval):
    diff = best_eval - new_eval

    if diff <= 0.2:
        return "✅ Excellent", "green", explain_good(board_before, played_move)
    elif diff <= 0.5:
        return "🆗 Good", "#2196F3", explain_good(board_before, played_move)
    elif diff <= 1.2:
        return "⚠️ Inaccuracy", "orange", explain_bad(board_before, played_move, diff)
    elif diff <= 2.5:
        return "❌ Mistake", "#FF5722", explain_bad(board_before, played_move, diff)
    else:
        return "😱 Blunder", "red", explain_bad(board_before, played_move, diff)

# =========================================================
# UI
# =========================================================
st.title("♟️ Deep Logic Chess (XAI Tutor)")

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("Load PGN")
    pgn_text = st.text_area("Paste PGN", height=120)

    if st.button("Load Game"):
        try:
            game = chess.pgn.read_game(io.StringIO(pgn_text))
            st.session_state.game_moves = list(game.mainline_moves())
            st.session_state.board = game.board()
            st.session_state.move_index = 0
            st.session_state.feedback = None
            st.rerun()
        except:
            st.error("Invalid PGN")

    if st.button("Reset Board"):
        st.session_state.board.reset()
        st.session_state.game_moves = []
        st.session_state.feedback = None
        st.rerun()

# ---------------- MAIN LAYOUT ----------------
col_board, col_info = st.columns([1.3, 1])

# ================= BOARD ==================
with col_board:
    candidates, best_eval = analyze_position(st.session_state.board)
    best_move = candidates[0]["move"] if candidates else None

    st.markdown(render_board(st.session_state.board, best_move), unsafe_allow_html=True)

    if st.session_state.game_moves:
        if st.button("Next ▶"):
            board_before = st.session_state.board.copy()
            move = st.session_state.game_moves[st.session_state.move_index]
            st.session_state.board.push(move)
            st.session_state.move_index += 1

            new_candidates, new_eval = analyze_position(st.session_state.board)

            label, color, text = judge_move(
                board_before,
                move,
                best_eval,
                new_eval
            )

            st.session_state.feedback = {
                "label": label,
                "color": color,
                "text": text
            }
            st.rerun()

# ================= INFO ==================
with col_info:
    st.subheader("Move Feedback")

    if st.session_state.feedback:
        f = st.session_state.feedback
        st.markdown(
            f"""
            <div style="background:{f['color']};
                        color:white;
                        padding:12px;
                        border-radius:8px;
                        text-align:center;">
                <h4>{f['label']}</h4>
                <p>{f['text']}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.info("Play a move to receive feedback.")

    st.divider()
    st.subheader("💡 Best Suggestion")

    if candidates:
        best = candidates[0]
        st.metric("Eval", f"{best['raw']:+.2f}")
        st.success(f"Best Move: {best['san']}")
        st.caption(explain_good(st.session_state.board, best["move"]))
