# ============================================
# Deep Logic Chess (XAI Edition)
# app.py
# ============================================

import streamlit as st
import chess
import chess.engine
import chess.svg
import base64
import io

# ============================================
# CONFIG
# ============================================

STOCKFISH_PATH = "/usr/games/stockfish"

# ML Weights learned in Google Colab
ML_WEIGHTS = {
    "check": 0.5792,
    "capture": 0.1724,
    "center": 0.0365
}

CENTER_SQUARES = [chess.D4, chess.E4, chess.D5, chess.E5]

# ============================================
# SESSION STATE (APP MEMORY)
# ============================================

if "board" not in st.session_state:
    st.session_state.board = chess.Board()

if "last_feedback" not in st.session_state:
    st.session_state.last_feedback = ""

if "last_feedback_color" not in st.session_state:
    st.session_state.last_feedback_color = "gray"

if "move_number" not in st.session_state:
    st.session_state.move_number = 1

# ============================================
# UTILITY FUNCTIONS
# ============================================

def render_board(board):
    """Render chess board as SVG inside Streamlit"""
    svg = chess.svg.board(board=board, size=400)
    b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}"/>'

def is_center_control(move):
    return move.to_square in CENTER_SQUARES

# ============================================
# STOCKFISH + ML ANALYSIS
# ============================================

def get_analysis(board):
    """
    Get top moves from Stockfish and re-rank them
    using ML weights trained on beginner games.
    """
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    info = engine.analyse(
        board,
        chess.engine.Limit(depth=12),
        multipv=9
    )

    moves = []

    for line in info:
        move = line["pv"][0]
        score = line["score"].pov(board.turn).score(mate_score=10000) / 100.0

        bonus = 0
        if board.gives_check(move):
            bonus += ML_WEIGHTS["check"]
        if board.is_capture(move):
            bonus += ML_WEIGHTS["capture"]
        if is_center_control(move):
            bonus += ML_WEIGHTS["center"]

        adjusted_score = score + bonus

        moves.append({
            "move": move,
            "raw_score": score,
            "adjusted_score": adjusted_score,
            "is_check": board.gives_check(move),
            "is_capture": board.is_capture(move),
            "is_center": is_center_control(move)
        })

    engine.quit()

    moves.sort(key=lambda x: x["adjusted_score"], reverse=True)
    return moves

# ============================================
# EXPLANATION ENGINE (XAI)
# ============================================

def explain_good_move(data):
    explanations = []

    if data["is_check"]:
        explanations.append("puts the opponent king in check")
    if data["is_capture"]:
        explanations.append("captures material")
    if data["is_center"]:
        explanations.append("improves central control")

    if not explanations:
        return "Solid move. Improves position without taking risks."

    return "Excellent move! It " + " and ".join(explanations) + "."

def explain_bad_move(eval_drop):
    if eval_drop > 1.5:
        return "Blunder. You lost significant material or position."
    elif eval_drop > 0.7:
        return "Mistake. This move weakens your position."
    else:
        return "Passive play. A stronger move was available."

# ============================================
# STREAMLIT UI
# ============================================

st.set_page_config(page_title="Deep Logic Chess (XAI)", layout="wide")

st.title("♟️ Deep Logic Chess — XAI Edition")
st.caption("A human-style chess tutor for beginners (Elo < 1500)")

left, right = st.columns([1, 1])

# --------------------------------------------
# LEFT: BOARD
# --------------------------------------------
with left:
    st.markdown(render_board(st.session_state.board), unsafe_allow_html=True)

    if st.button("Next ▶"):
        if not st.session_state.board.is_game_over():
            analysis = get_analysis(st.session_state.board)

            best_move = analysis[0]
            played_move = best_move["move"]

            st.session_state.board.push(played_move)

            # Compare top 2 moves for evaluation drop
            if len(analysis) > 1:
                eval_drop = analysis[0]["adjusted_score"] - analysis[1]["adjusted_score"]
            else:
                eval_drop = 0

            if eval_drop < 0.2:
                feedback = explain_good_move(best_move)
                color = "green"
            else:
                feedback = explain_bad_move(eval_drop)
                color = "red" if eval_drop > 1 else "orange"

            st.session_state.last_feedback = feedback
            st.session_state.last_feedback_color = color
            st.session_state.move_number += 1

# --------------------------------------------
# RIGHT: FEEDBACK
# --------------------------------------------
with right:
    st.subheader("🧠 Move Explanation")

    st.markdown(
        f"""
        <div style="
            padding: 16px;
            border-radius: 10px;
            background-color: {st.session_state.last_feedback_color};
            color: white;
            font-size: 18px;
        ">
            {st.session_state.last_feedback or "Click Next to begin analysis."}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")
    st.markdown("### 🔬 ML Weights (From Colab Training)")
    st.json(ML_WEIGHTS)

    st.markdown("""
    **Why this matters:**  
    These weights were learned from **20,000 beginner games**  
    and reflect *what actually wins games* at low Elo.
    """)

# ============================================
# FOOTER
# ============================================

st.markdown("---")
st.caption(
    "Deep Logic Chess | Explainable AI Project | "
    "Stockfish + ML + Streamlit"
)
