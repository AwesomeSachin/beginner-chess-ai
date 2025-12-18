# app.py
"""
Deep Logic Chess (XAI Edition) - Streamlit app

Features:
- Uses Stockfish engine (via UCI) to get top moves.
- Applies ML "weights" learned offline (checks/captures/center) to re-rank Stockfish suggestions,
  making moves that are more "beginner-friendly" score higher.
- Produces natural-language feedback for played moves (green/orange/red banners).
- Renders chessboard as SVG and keeps session state.

Prerequisites:
- Stockfish binary accessible (default path: /usr/bin/stockfish).
  Set env var STOCKFISH_PATH to override.
- Python packages: streamlit, chess (python-chess)
"""

import os
import sys
import io
import base64
import textwrap
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

import streamlit as st
import chess
import chess.svg
import chess.engine

# -----------------------
# Hardcoded ML Weights (from your Colab "Brain")
# -----------------------
ML_WEIGHTS = {
    "checks": 0.5792,
    "captures": 0.1724,
    "center": 0.0365
}

# Center squares (classical central 4)
CENTER_SQUARES = {chess.E4, chess.D4, chess.E5, chess.D5}

# Stockfish path (override with env var if needed)
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/bin/stockfish")


# -----------------------
# Utility functions
# -----------------------
def svg_board_to_html(svg_text: str, width: int = 420) -> str:
    """Return embeddable HTML for chessboard SVG."""
    # Ensure proper xml header for embedding
    svg_bytes = svg_text.encode("utf-8")
    b64 = base64.b64encode(svg_bytes).decode("utf-8")
    html = f'<img src="data:image/svg+xml;base64,{b64}" width="{width}"/>'
    return html


def cp_to_score(cp_or_mate: chess.engine.PovScore) -> float:
    """
    Convert engine score (pov score dict) into pawn units.
    If a mate is reported, return a large value with sign for preference.
    """
    if cp_or_mate is None:
        return 0.0
    if cp_or_mate.is_mate():
        mate_in = cp_or_mate.mate()
        # Represent mate as a large score; sign indicates side
        # Positive for mate for side to move, negative for being mated.
        return 1000.0 if mate_in > 0 else -1000.0
    else:
        # cp is centipawns
        return cp_or_mate.score() / 100.0


def board_score_from_engine(board: chess.Board, info: Dict[str, Any]) -> float:
    """Extract score from engine analyse info dict and convert to pawn units from White POV."""
    # 'score' key contains a PovScore (score relative to the side to move?)
    # Python-chess returns a PovScore from White POV if using engine.analyse on board.
    pov = info.get("score", None)
    if pov is None:
        return 0.0
    return cp_to_score(pov)


# -----------------------
# ML-augmented evaluation & explanation
# -----------------------
@dataclass
class CandidateMove:
    move: chess.Move
    san: str
    stockfish_score: float  # pawns from White POV
    ml_bonus: float
    combined_score: float  # score adjusted to be perspective-correct for side-to-move
    is_check: bool
    is_capture: bool
    center_control: bool


def extract_features_after_move(board: chess.Board, move: chess.Move) -> Tuple[bool, bool, bool]:
    """
    Given a board and a move, return (is_check, is_capture, center_control) *after* the move is applied.
    center_control: True if destination is in center or the moving side attacks any center square afterwards.
    """
    b2 = board.copy()
    b2.push(move)
    is_check = b2.is_check()
    is_capture = board.is_capture(move)
    # center_control if move lands on central square OR the moving side attacks any of the center squares after the move
    dest = move.to_square
    center_control = (dest in CENTER_SQUARES) or any(
        b2.is_attacked_by(b2.turn, sq) for sq in CENTER_SQUARES
    )
    return is_check, is_capture, center_control


def get_engine_candidates(engine: chess.engine.SimpleEngine, board: chess.Board, multipv: int = 9, depth: int = 16) -> List[Dict[str, Any]]:
    """
    Ask engine for multipv analysis (top N moves). Returns list of info dicts.
    If engine doesn't support multipv or fails, tries fallback to single best move.
    """
    try:
        # For engines that support multipv, this returns a list of dicts
        info_list = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
        # python-chess returns a list for multipv; if single dict returned, wrap it
        if isinstance(info_list, dict):
            return [info_list]
        return info_list
    except Exception:
        # Fallback: ask for single best move
        try:
            info = engine.analyse(board, chess.engine.Limit(depth=depth))
            return [info]
        except Exception:
            return []


def get_analysis(engine: chess.engine.SimpleEngine, board: chess.Board, multipv: int = 9, depth: int = 16) -> List[CandidateMove]:
    """
    Main logic: get top engine moves, compute features, compute ML bonus, and produce combined scores.
    Returns CandidateMove list sorted by combined_score descending (best for the side to move first).
    """
    infos = get_engine_candidates(engine, board, multipv=multipv, depth=depth)
    candidates: List[CandidateMove] = []

    # We need the engine's score for each candidate. For multipv results, python-chess provides 'pv' and 'score'
    for info in infos:
        pv = info.get("pv", None)
        if not pv:
            continue
        move = pv[0]
        san = board.san(move)
        sf_score = board_score_from_engine(board, info)  # pawns from White POV

        # Extract features after applying move
        is_check, is_capture, center_control = extract_features_after_move(board, move)

        # ML bonus: sum(weights * feature)
        ml_bonus = (ML_WEIGHTS["checks"] * float(is_check)
                    + ML_WEIGHTS["captures"] * float(is_capture)
                    + ML_WEIGHTS["center"] * float(center_control))

        # Convert stockfish score to "from side-to-move perspective"
        # Engine score is in White POV; for consistency, we compute side_to_move_multiplier
        multiplier = 1.0 if board.turn == chess.WHITE else -1.0
        combined_score = multiplier * sf_score + ml_bonus  # positive is better for side to move

        candidate = CandidateMove(
            move=move,
            san=san,
            stockfish_score=sf_score,
            ml_bonus=ml_bonus,
            combined_score=combined_score,
            is_check=is_check,
            is_capture=is_capture,
            center_control=center_control
        )
        candidates.append(candidate)

    # Sort by combined_score descending (best for side to move first)
    candidates.sort(key=lambda c: c.combined_score, reverse=True)
    return candidates


# -----------------------
# Explanation generation
# -----------------------
def explain_good_move(candidate: CandidateMove) -> str:
    """Generate human-like positive feedback for a good move."""
    parts = []
    if candidate.is_capture:
        parts.append("Captures material.")
    if candidate.is_check:
        parts.append("Gives check.")
    if candidate.center_control:
        parts.append("Improves control of the center.")
    if not parts:
        parts.append("Quiet developing move — helps your position.")
    ml_line = f"(ML boost: +{candidate.ml_bonus:.3f})"
    sf_line = f"(Stockfish eval: {candidate.stockfish_score:+.2f} pawns from White POV)"
    return " ".join(parts) + " " + ml_line + " " + sf_line


def explain_bad_move(eval_drop_pawns: float) -> str:
    """
    Generate criticism message for a move that drops evaluation by eval_drop_pawns (pawns).
    - >1.0 pawn => Blunder
    - 0.5 - 1.0 => Mistake
    - 0.15 - 0.5 => Inaccuracy / Passive
    - <0.15 => Fine
    """
    if eval_drop_pawns > 1.0:
        return f"Blunder! The move loses more than {eval_drop_pawns:.2f} pawns of advantage."
    elif eval_drop_pawns > 0.5:
        return f"Mistake — it drops the evaluation by {eval_drop_pawns:.2f} pawns."
    elif eval_drop_pawns > 0.15:
        return f"Questionable / passive: evaluation drops by {eval_drop_pawns:.2f} pawns."
    else:
        return f"Small inaccuracy — evaluation change is {eval_drop_pawns:.2f} pawns (acceptable)."


# -----------------------
# Session state initialization helpers
# -----------------------
def init_session_state():
    if "board" not in st.session_state:
        st.session_state.board = chess.Board()
    if "history" not in st.session_state:
        st.session_state.history = []
    if "last_feedback" not in st.session_state:
        st.session_state.last_feedback = None
    if "weights" not in st.session_state:
        st.session_state.weights = ML_WEIGHTS.copy()


# -----------------------
# UI Helpers
# -----------------------
def render_board_ui(board: chess.Board):
    """Render the board SVG into the Streamlit page using components.html"""
    svg = chess.svg.board(board=board, size=420)
    html = svg_board_to_html(svg, width=420)
    st.markdown(html, unsafe_allow_html=True)


def colored_banner(message: str, color: str = "green"):
    """
    Show a colored message banner. color: 'green', 'orange', 'red', or 'blue'
    """
    color_map = {
        "green": "#d4f8d4",
        "orange": "#fff4d6",
        "red": "#ffd6d6",
        "blue": "#d6eaff"
    }
    bg = color_map.get(color, "#d6eaff")
    st.markdown(f'<div style="background:{bg}; padding:12px; border-radius:6px;">{message}</div>', unsafe_allow_html=True)


# -----------------------
# App main
# -----------------------
def main():
    st.set_page_config(page_title="Deep Logic Chess — XAI Tutor", layout="wide")
    st.title("Deep Logic Chess — XAI Edition")
    st.write("Human-like explanations for beginner chess moves. (Weights from offline Colab are hardcoded.)")

    init_session_state()

    # Try to initialize engine
    engine = None
    engine_error = None
    try:
        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        # Ask engine to use MultiPV if available (some engines ignore configure)
        try:
            engine.configure({"MultiPV": 9})
        except Exception:
            pass
    except Exception as e:
        engine_error = str(e)

    # Left: board and move input. Right: feedback and engine analysis
    col1, col2 = st.columns([1.1, 1])

    with col1:
        st.subheader("Board")
        render_board_ui(st.session_state.board)

        # Move input area: user may enter SAN or UCI
        with st.form("move_form", clear_on_submit=False):
            move_input = st.text_input("Enter your move (SAN or UCI), or leave blank and click 'Next ▶' for engine move", "")
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                play_button = st.form_submit_button("Play Move")
            with c2:
                next_button = st.form_submit_button("Next ▶ (Engine move)")
            with c3:
                reset_button = st.form_submit_button("Reset Position")

        # Actions
        if reset_button:
            st.session_state.board = chess.Board()
            st.session_state.history = []
            st.session_state.last_feedback = None
            st.experimental_rerun()

        # If engine missing, warn but still allow manual play
        if engine_error:
            st.warning(f"Stockfish engine not available at '{STOCKFISH_PATH}'. Some analysis features will be disabled. Error: {engine_error}")

        if play_button:
            user_move_text = move_input.strip()
            if not user_move_text:
                st.warning("Enter a move in SAN (e.g., Nf3) or UCI (e2e4) to play, or click Next ▶ to let engine move.")
            else:
                board = st.session_state.board
                try:
                    # Try SAN first, then UCI
                    try:
                        mv = board.parse_san(user_move_text)
                    except Exception:
                        mv = chess.Move.from_uci(user_move_text)
                        if mv not in board.legal_moves:
                            raise ValueError("Illegal move")
                    board.push(mv)
                    st.session_state.history.append(mv.uci())
                    # Analyze the move if engine available
                    if engine:
                        # Compare to engine best (unmodified) to compute eval drop
                        # Get best engine move and its eval from the position BEFORE the move
                        pre_board = board.copy()
                        pre_board.pop()  # remove user's move, so pre_board is before the move
                        try:
                            best_infos = get_engine_candidates(engine, pre_board, multipv=1, depth=16)
                            best_eval = board_score_from_engine(pre_board, best_infos[0]) if best_infos else 0.0
                        except Exception:
                            best_eval = 0.0
                        # Now get eval for the played move (we can ask engine to evaluate resulting position)
                        try:
                            eval_after_list = engine.analyse(board, chess.engine.Limit(depth=12))
                            eval_after = board_score_from_engine(pre_board, eval_after_list)  # careful: info is from pre_board context
                            # But better to get 'score' from eval_after_list directly (it is from perspective of side to move on pre_board)
                            eval_move = cp_to_score(eval_after_list.get("score")) if eval_after_list.get("score") else 0.0
                        except Exception:
                            eval_move = 0.0

                        # Convert white POV to side-to-move perspective before the move
                        multiplier = 1.0 if pre_board.turn == chess.WHITE else -1.0
                        best_for_side = multiplier * best_eval
                        move_for_side = multiplier * eval_move
                        eval_drop = best_for_side - move_for_side

                        # Create message
                        feedback_msg = explain_bad_move(eval_drop) if eval_drop > 0.15 else "Good move."
                        st.session_state.last_feedback = {
                            "type": "user_move",
                            "message": feedback_msg,
                            "eval_drop": eval_drop
                        }
                    else:
                        st.session_state.last_feedback = {"type": "user_move", "message": "Move played. Engine analysis unavailable."}

                except Exception as e:
                    st.error(f"Couldn't parse or play move: {e}")

        if next_button:
            if not engine:
                st.warning("Engine not available. Cannot play engine move.")
            else:
                board = st.session_state.board
                try:
                    # Get ML-augmented candidates and play the top one
                    candidates = get_analysis(engine, board, multipv=9, depth=18)
                    if not candidates:
                        # fallback to engine best single move
                        info = engine.analyse(board, chess.engine.Limit(depth=18))
                        mv = info["pv"][0]
                        board.push(mv)
                        st.session_state.history.append(mv.uci())
                        st.session_state.last_feedback = {"type": "engine_move", "message": "Engine played (no candidates)." }
                    else:
                        top = candidates[0]
                        board.push(top.move)
                        st.session_state.history.append(top.move.uci())
                        # feedback for engine move: explain why it's chosen
                        expl = explain_good_move(top)
                        st.session_state.last_feedback = {"type": "engine_move", "message": f"Engine (ML-augmented) played {top.san}. {expl}"}
                except Exception as e:
                    st.error(f"Engine failed to provide move: {e}")

        st.markdown("---")
        st.subheader("Move history (PGN-like):")
        history_str = " ".join([chess.Move.from_uci(u).uci() for u in st.session_state.history])
        st.code(history_str if history_str else "No moves yet.")

    # Right column: Analysis & explanations
    with col2:
        st.subheader("Feedback / Analysis")

        if st.session_state.last_feedback:
            fb = st.session_state.last_feedback
            if fb.get("type") == "engine_move":
                colored_banner(f"Engine move: {fb.get('message')}", color="blue")
            elif fb.get("type") == "user_move":
                # choose banner color based on eval_drop
                ed = fb.get("eval_drop", 0.0)
                if ed > 1.0:
                    color = "red"
                elif ed > 0.5:
                    color = "orange"
                else:
                    color = "green"
                colored_banner(f"User move analysis: {fb.get('message')}", color=color)
        else:
            st.info("No feedback yet. Play a move or click Next ▶ (Engine move).")

        st.markdown("### Engine candidates (with ML re-ranking)")
        if engine:
            try:
                candidates = get_analysis(engine, st.session_state.board, multipv=9, depth=14)
                if not candidates:
                    st.write("No candidates available from engine.")
                else:
                    # Show a compact table of top candidates
                    rows = []
                    for c in candidates[:9]:
                        # Stockfish score from White POV, show converted for side to move
                        multiplier = 1.0 if st.session_state.board.turn == chess.WHITE else -1.0
                        sf_for_side = multiplier * c.stockfish_score
                        rows.append({
                            "Move": c.san,
                            "SF_score(pawns side-TO-move)": f"{sf_for_side:+.2f}",
                            "ML_bonus": f"+{c.ml_bonus:.3f}",
                            "Combined": f"{c.combined_score:+.3f}",
                            "Capture": c.is_capture,
                            "Check": c.is_check,
                            "Center": c.center_control
                        })
                    # Use st.table to render
                    import pandas as pd
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.error(f"Failed to compute candidates: {e}")
        else:
            st.warning("Stockfish not available — cannot produce candidates.")

        st.markdown("---")
        st.subheader("ML Weights (from Colab)")
        st.write(f"Checks: {ML_WEIGHTS['checks']:.4f}, Captures: {ML_WEIGHTS['captures']:.4f}, Center: {ML_WEIGHTS['center']:.4f}")

        st.markdown("### Tips (XAI)")
        st.write(textwrap.dedent("""
            - The app re-ranks Stockfish moves by adding a small ML bonus for moves that are checks, captures, or improve center control.
            - This helps the tutor prefer moves that are easier for beginners to spot and learn from.
            - Explanations are intentionally short and actionable.
        """))

    # Ensure engine is closed before exit
    if engine:
        try:
            engine.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
