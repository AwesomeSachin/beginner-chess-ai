# ============================================================
# Deep Logic Chess (XAI Edition)
# app.py — Central Nervous System
# ============================================================

import streamlit as st
import chess
import chess.engine
import chess.svg
import base64
import io

# ============================================================
# CONFIGURATION
# ============================================================

STOCKFISH_PATH = "/usr/games/stockfish"

# ---- ML Weights learned from Google Colab (BEGINNER <1500) ----
ML_WEIGHTS = {
    "check": 0.5792,
    "capture": 0.1724,
    "center": 0.0365
}

CENTER_SQUARES = [chess.D4, chess.D5, chess.E4, chess.E5]

# ============================================================
# SESSION STATE (APP MEMORY)
# ============================================================

if "board" not in st.session_state:
    st.session_state.board = chess.Board()

if "history" not in st.session_state:
    st.session_state.history = []

if "feedback" not in st.session_state:
    st.session_state.feedback = None

if "best_move" not in st.session_state:
    st.session_state.best_move = None

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def render_board(board, arrows=None):
    """Convert board state to SVG and render in Streamlit"""
    svg = chess.svg.board(board, arrows=arrows, size=420)
    b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    st.markdown(f'<img src="data:image/svg+xml;base64,{b64}"/>',
                unsafe_allow_html=True)


def is_check(board, move):
    board.push(move)
    result = board.is_check()
    board.pop()
    return result


def is_capture(board, move):
    return board.is_capture(move)


def controls_center(move):
    return move.to_square in CENTER_SQUARES


# ============================================================
# STOCKFISH + ML ANALYSIS ENGINE
# ============================================================

def get_analysis(board):
    """
    Returns a ranked list of moves after injecting ML weights
    """
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    info = engine.analyse(
        board,
        chess.engine.Limit(depth=14),
        multipv=9
    )

    scored_moves = []

    for item in info:
        move = item["pv"][0]
        score = item["score"].white().score(mate_score=10000) / 100

        bonus = 0.0

        if is_check(board, move):
            bonus += ML_WEIGHTS["check"]

        if is_capture(board, move):
            bonus += ML_WEIGHTS["capture"]

        if controls_center(move):
            bonus += ML_WEIGHTS["center"]

        scored_moves.append({
            "move": move,
            "raw_score": score,
            "final_score": score + bonus
        })

    engine.quit()

    scored_moves.sort(key=lambda x: x["final_score"], reverse=True)
    return scored_moves


# ============================================================
# EXPLANATION LOGIC (XAI)
# ============================================================

def explain_good_move(board, move):
    explanations = []

    if is_capture(board, move):
        explanations.append("Captures material")

    if is_check(board, move):
        explanations.append("Checks the king")

    if controls_center(move):
        explanations.append("Improves center control")

    if not explanations:
        explanations.append("Solid improving move")

    return " & ".join(explanations)


def explain_bad_move(board, move, best_move):
    board.push(move)
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    reply = engine.analyse(board, chess.engine.Limit(depth=12))
    engine.quit()
    board.pop()

    if reply["score"].white().score(mate_score=10000) < -200:
        return "Blunder. You left a piece en prise."

    return "Inaccurate. Missed a stronger continuation."


# ============================================================
# MOVE JUDGMENT ENGINE
# ============================================================

def judge_move(board, played_move):
    analysis = get_analysis(board)

    best = analysis[0]
    best_move = best["move"]
    best_score = best["final_score"]

    played_score = None
    for item in analysis:
        if item["move"] == played_move:
            played_score = item["final_score"]
            break

    if played_score is None:
        played_score = best_score - 1.5

    diff = best_score - played_score

    if diff < 0.2:
        return ("good", explain_good_move(board, played_move), best_move)

    elif diff < 1.0:
        return ("ok", "Playable, but not optimal.", best_move)

    else:
        return ("bad", explain_bad_move(board, played_move, best_move), best_move)


# ============================================================
# STREAMLIT UI
# ============================================================

st.set_page_config(page_title="Deep Logic Chess (XAI)", layout="wide")

st.title("♟️ Deep Logic Chess — Explainable AI Tutor")
st.caption("Stockfish + Human ML Logic (Beginner <1500 Elo)")

# ------------------------------------------------------------
# SIDEBAR (PGN LOADER)
# ------------------------------------------------------------

st.sidebar.header("📄 Load Game (PGN)")
pgn_text = st.sidebar.text_area("Paste PGN here")

if st.sidebar.button("Load PGN"):
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    board = game.board()
    for move in game.mainline_moves():
        board.push(move)
    st.session_state.board = board
    st.session_state.history = []
    st.session_state.feedback = None

# ------------------------------------------------------------
# MAIN LAYOUT
# ------------------------------------------------------------

col1, col2 = st.columns([1.1, 0.9])

with col1:
    arrows = []
    if st.session_state.best_move:
        arrows = [(st.session_state.best_move.from_square,
                   st.session_state.best_move.to_square)]
    render_board(st.session_state.board, arrows)

    c1, c2 = st.columns(2)

    if c1.button("▶ Next Move"):
        analysis = get_analysis(st.session_state.board)
        move = analysis[0]["move"]

        verdict, explanation, best_move = judge_move(
            st.session_state.board, move
        )

        st.session_state.board.push(move)
        st.session_state.feedback = (verdict, explanation)
        st.session_state.best_move = best_move

    if c2.button("⏪ Undo"):
        if st.session_state.board.move_stack:
            st.session_state.board.pop()
            st.session_state.feedback = None
            st.session_state.best_move = None

# ------------------------------------------------------------
# FEEDBACK PANEL
# ------------------------------------------------------------

with col2:
    st.subheader("🧠 AI Feedback")

    if st.session_state.feedback:
        verdict, explanation = st.session_state.feedback

        if verdict == "good":
            st.success(f"✅ Excellent! {explanation}")

        elif verdict == "ok":
            st.warning(f"⚠️ {explanation}")

        else:
            st.error(f"❌ {explanation}")

    st.subheader("📌 Why this works")
    st.markdown("""
- **Checks** are rewarded most (0.57)
- **Captures** matter (0.17)
- **Positional play** matters least at beginner level
- Stockfish calculates
- ML *re-ranks* moves for humans
""")

# ============================================================
# END OF FILE
# ============================================================
