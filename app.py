import streamlit as st
import chess
import chess.engine
import chess.svg
import chess.pgn
import io
import base64

# --- CONFIG ---
st.set_page_config(page_title="Chess Game Reviewer", layout="wide")
STOCKFISH_PATH = "/usr/games/stockfish"

# --- SESSION STATE INITIALIZATION ---
if 'game_moves' not in st.session_state: st.session_state.game_moves = [] # List of moves from PGN
if 'current_index' not in st.session_state: st.session_state.current_index = 0 # Current move number
if 'board' not in st.session_state: st.session_state.board = chess.Board()
if 'analysis_cache' not in st.session_state: st.session_state.analysis_cache = {} # Store analysis to avoid re-running

# --- HELPER: RENDER BOARD ---
def render_board(board, arrows=[]):
    """Renders board as SVG image."""
    board_svg = chess.svg.board(
        board=board, 
        size=450,
        arrows=arrows,
        lastmove=board.peek() if board.move_stack else None,
        colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
    )
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="100%" />'

# --- LOGIC: CLASSIFICATION SYSTEM ---
def classify_move(played_eval, best_eval, move_num):
    """
    Returns (Label, Color) based on centipawn loss.
    """
    diff = best_eval - played_eval
    
    # 1. Book Moves (Approximate: Opening phase + low error)
    if move_num <= 10 and diff < 0.3:
        return "📖 Book Move", "gray"
        
    # 2. Brilliance (Simple Heuristic: You found the only winning move)
    # (Real brilliance requires sacrifice detection, this is a simplified version)
    if diff < 0.05 and best_eval > 2.0:
        return "🔥 Brilliant!", "#2196F3" # Blue
        
    # 3. Standard Classification
    if diff < 0.2: return "✅ Best Move", "green"
    if diff < 0.5: return "🆗 Good / Excellent", "#8BC34A" # Light Green
    if diff < 1.0: return "⚠️ Inaccuracy", "#FFC107" # Orange
    if diff < 2.0: return "❌ Mistake", "#FF9800" # Dark Orange
    return "😱 Blunder", "red"

# --- LOGIC: BEGINNER ENGINE ---
def get_beginner_plan(board, engine_path):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return None

    # Get Top 3 moves to find the "Simple" one
    info = engine.analyse(board, chess.engine.Limit(time=0.4), multipv=3)
    candidates = []
    
    for line in info:
        move = line["pv"][0]
        score = line["score"].relative.score(mate_score=10000)
        if score is None: score = 0
        
        # Beginner Heuristics
        beginner_bonus = 0
        board.push(move)
        if board.is_check(): beginner_bonus += 2.0
        if board.is_capture(move): beginner_bonus += 1.0
        # Strategic Center Control
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]: beginner_bonus += 0.5
        board.pop()
        
        final_score = (score/100) + beginner_bonus
        candidates.append({"move": move, "san": board.san(move), "score": final_score, "pv": line["pv"][:4]})
    
    engine.quit()
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[0] if candidates else None

# --- UI LAYOUT ---
st.title("♟️ Game Review & Analysis")

# 1. SIDEBAR: LOAD GAME
with st.sidebar:
    st.header("1. Paste Game")
    pgn_input = st.text_area("Paste PGN here:", height=200)
    
    if st.button("Load Game Review"):
        if pgn_input:
            pgn_io = io.StringIO(pgn_input)
            try:
                game = chess.pgn.read_game(pgn_io)
                st.session_state.game_moves = list(game.mainline_moves())
                st.session_state.current_index = 0
                st.session_state.board = game.board() # Reset to start
                st.session_state.analysis_cache = {} # Clear cache
                st.success(f"Loaded {len(st.session_state.game_moves)} moves!")
                st.rerun()
            except:
                st.error("Invalid PGN.")

# 2. MAIN AREA
if st.session_state.game_moves:
    col_board, col_analysis = st.columns([1, 1.2])

    # --- BOARD CONTROLS ---
    with col_board:
        # Reconstruct board to current index
        review_board = chess.Board()
        for i in range(st.session_state.current_index):
            review_board.push(st.session_state.game_moves[i])
            
        st.markdown(render_board(review_board), unsafe_allow_html=True)
        
        # Navigation Buttons
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("◀ Prev") and st.session_state.current_index > 0:
                st.session_state.current_index -= 1
                st.rerun()
        with c3:
            if st.button("Next ▶") and st.session_state.current_index < len(st.session_state.game_moves):
                st.session_state.current_index += 1
                st.rerun()
                
        st.caption(f"Move {st.session_state.current_index} of {len(st.session_state.game_moves)}")

    # --- ANALYSIS PANEL ---
    with col_analysis:
        st.header("Move Feedback")
        
        if st.session_state.current_index > 0:
            # We analyze the move that was JUST played (current_index - 1)
            played_move = st.session_state.game_moves[st.session_state.current_index - 1]
            
            # Use a temporary board state BEFORE that move
            temp_board = chess.Board()
            for i in range(st.session_state.current_index - 1):
                temp_board.push(st.session_state.game_moves[i])
            
            st.subheader(f"You played: **{temp_board.san(played_move)}**")
            
            # --- RUN ANALYSIS (Cached for speed) ---
            cache_key = f"{st.session_state.current_index}"
            if cache_key not in st.session_state.analysis_cache:
                with st.spinner("Analyzing move quality..."):
                    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
                    
                    # 1. Best Eval (Before Move)
                    info = engine.analyse(temp_board, chess.engine.Limit(time=0.1))
                    best_eval = info["score"].relative.score(mate_score=10000) / 100
                    
                    # 2. Played Eval (After Move)
                    temp_board.push(played_move)
                    info_after = engine.analyse(temp_board, chess.engine.Limit(time=0.1))
                    played_eval = info_after["score"].relative.score(mate_score=10000) / 100 # Opponent view
                    played_eval = -played_eval # Flip back to our view
                    temp_board.pop()
                    
                    # 3. Beginner Plan
                    beginner_rec = get_beginner_plan(temp_board, STOCKFISH_PATH)
                    
                    engine.quit()
                    
                    st.session_state.analysis_cache[cache_key] = {
                        "best_eval": best_eval,
                        "played_eval": played_eval,
                        "beginner_rec": beginner_rec
                    }
            
            # --- DISPLAY RESULTS ---
            data = st.session_state.analysis_cache[cache_key]
            label, color = classify_move(data["played_eval"], data["best_eval"], st.session_state.current_index)
            
            # 1. Classification Badge
            st.markdown(f"""
            <div style="background-color: {color}; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; font-size: 20px;">
                {label}
            </div>
            """, unsafe_allow_html=True)
            
            # 2. Evaluations
            c_a, c_b = st.columns(2)
            c_a.metric("Eval (Before)", f"{data['best_eval']:+.2f}")
            c_b.metric("Eval (After)", f"{data['played_eval']:+.2f}")
            
            st.divider()
            
            # 3. Beginner Plan Comparison
            rec = data['beginner_rec']
            if rec and rec['san'] != temp_board.san(played_move):
                st.info(f"💡 **Beginner Engine Plan:** {rec['san']}")
                plan_str = temp_board.variation_san(rec['pv'])
                st.write(f"**The Plan:** {plan_str}")
                st.caption("This plan is simpler or more forcing than what you played.")
            else:
                st.success("Your move matched the Beginner Engine's plan!")
                
        else:
            st.info("Start of game. Press Next to review moves.")
else:
    st.info("👈 Paste a PGN in the sidebar to start reviewing!")
            
