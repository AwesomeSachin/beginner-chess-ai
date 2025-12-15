import streamlit as st
import chess
import chess.engine
import chess.svg
import chess.pgn
import io
import base64

# --- CONFIG ---
st.set_page_config(page_title="Chess Master Dashboard", layout="wide")
STOCKFISH_PATH = "/usr/games/stockfish"

# --- STATE MANAGEMENT ---
if 'board' not in st.session_state: st.session_state.board = chess.Board()
if 'game_moves' not in st.session_state: st.session_state.game_moves = []
if 'move_index' not in st.session_state: st.session_state.move_index = 0
if 'last_best_eval' not in st.session_state: st.session_state.last_best_eval = 0.35 # Start eval
if 'feedback' not in st.session_state: st.session_state.feedback = None # Stores "Blunder", "Good" etc.

# --- HELPER: RENDER BOARD ---
def render_board(board, arrows=[]):
    board_svg = chess.svg.board(
        board=board, 
        size=500,
        arrows=arrows,
        lastmove=board.peek() if board.move_stack else None,
        colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
    )
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="100%" />'

# --- LOGIC: ANALYSIS & FEEDBACK ---
def get_analysis(board, engine_path):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return None, []
    
    # Analyze Top 3 moves
    info = engine.analyse(board, chess.engine.Limit(time=0.4), multipv=3)
    candidates = []
    
    for line in info:
        move = line["pv"][0]
        score = line["score"].relative.score(mate_score=10000)
        if score is None: score = 0
        
        # Beginner Logic Bonus
        bonus = 0
        board.push(move)
        if board.is_check(): bonus += 0.5
        if board.is_capture(move): bonus += 0.3
        board.pop()
        
        candidates.append({
            "move": move,
            "san": board.san(move),
            "eval": score/100,
            "score": (score/100) + bonus, # Custom score
            "pv": line["pv"][:5]
        })
    
    engine.quit()
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    # Store the BEST eval of this position for the NEXT move's comparison
    if candidates:
        st.session_state.last_best_eval = candidates[0]['eval']
        
    return candidates[0] if candidates else None, candidates

def generate_feedback(current_board_eval):
    """Compares the current position's value vs what it SHOULD have been."""
    # We expected 'last_best_eval'. 
    # But now we are at 'current_board_eval' (from perspective of player who just moved).
    # Since we analyze from side-to-move, we must flip perspective.
    
    diff = st.session_state.last_best_eval - (-current_board_eval)
    
    # Classification Logic
    if diff <= 0.2: return "✅ Excellent", "green"
    if diff <= 0.6: return "🆗 Good", "blue"
    if diff <= 1.5: return "⚠️ Inaccuracy", "orange"
    if diff <= 3.0: return "❌ Mistake", "#FF5722" # Dark Orange
    return "😱 Blunder", "red"

# --- UI START ---
st.title("♟️ Chess Master Dashboard")

# SIDEBAR: PGN
with st.sidebar:
    st.header("Load Game")
    pgn_txt = st.text_area("Paste PGN:", height=150)
    if st.button("Load & Reset"):
        if pgn_txt:
            try:
                pgn_io = io.StringIO(pgn_txt)
                game = chess.pgn.read_game(pgn_io)
                st.session_state.game_moves = list(game.mainline_moves())
                st.session_state.board = game.board()
                st.session_state.move_index = 0
                st.session_state.feedback = None
                st.rerun()
            except:
                st.error("Invalid PGN")
    
    st.divider()
    if st.button("🗑️ Clear Board (Free Play)"):
        st.session_state.board.reset()
        st.session_state.game_moves = []
        st.session_state.feedback = None
        st.rerun()

# LAYOUT
col_main, col_info = st.columns([1.5, 1.2])

# 1. RUN ANALYSIS (Runs on every refresh to generate arrows/buttons)
with st.spinner("Analyzing..."):
    best_plan, candidates = get_analysis(st.session_state.board, STOCKFISH_PATH)

# Auto-Arrows for the Best Plan
arrows = []
if best_plan:
    m1 = best_plan['move']
    arrows.append(chess.svg.Arrow(m1.from_square, m1.to_square, color="#4CAF50")) # Green
    if len(best_plan['pv']) > 1:
        m2 = best_plan['pv'][1]
        arrows.append(chess.svg.Arrow(m2.from_square, m2.to_square, color="#2196F3")) # Blue

# === LEFT: BOARD ===
with col_main:
    # Feedback Banner
    if st.session_state.feedback:
        label, color = st.session_state.feedback
        st.markdown(f"""
        <div style="background-color: {color}; color: white; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 10px;">
            <h3 style="margin:0;">{label}</h3>
        </div>
        """, unsafe_allow_html=True)
    
    # Render Board
    st.markdown(render_board(st.session_state.board, arrows), unsafe_allow_html=True)
    
    # Navigation Buttons (PGN Mode)
    if st.session_state.game_moves:
        c1, c2, c3 = st.columns([1,2,1])
        with c3:
            if st.button("Next Move ▶", use_container_width=True) and st.session_state.move_index < len(st.session_state.game_moves):
                # 1. Get ready to judge
                before_eval = best_plan['eval'] if best_plan else 0
                st.session_state.last_best_eval = before_eval
                
                # 2. Make Move
                move = st.session_state.game_moves[st.session_state.move_index]
                st.session_state.board.push(move)
                st.session_state.move_index += 1
                
                # 3. Analyze NEW position to generate feedback
                new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                current_eval = new_best['eval'] if new_best else 0
                
                # 4. Generate Feedback
                st.session_state.feedback = generate_feedback(current_eval)
                st.rerun()
                
        with c1:
            if st.button("◀ Undo"):
                if st.session_state.board.move_stack:
                    st.session_state.board.pop()
                    if st.session_state.move_index > 0: st.session_state.move_index -= 1
                    st.session_state.feedback = None
                    st.rerun()
                    
    else:
        if st.button("◀ Undo Last Move"):
            if st.session_state.board.move_stack:
                st.session_state.board.pop()
                st.session_state.feedback = None
                st.rerun()

# === RIGHT: INFO PANEL ===
with col_info:
    # 1. METRICS
    st.subheader("Analysis")
    if best_plan:
        st.metric("Current Eval", f"{best_plan['eval']:+.2f}")
        st.info(f"**Best Plan:** {st.session_state.board.variation_san(best_plan['pv'])}")
    
    st.divider()
    
    # 2. CLICKABLE MOVES (One Row)
    st.subheader("Play Recommended Move")
    st.caption("Click a move below to play it:")
    
    if candidates:
        # Create 3 columns for horizontal layout
        cols = st.columns(len(candidates[:3])) 
        
        for i, cand in enumerate(candidates[:3]):
            with cols[i]:
                # THE BUTTON
                if st.button(f"{cand['san']}", key=f"btn_{i}", use_container_width=True):
                    # 1. Logic for Free Play Feedback
                    st.session_state.last_best_eval = candidates[0]['eval'] # The best possible
                    
                    # 2. Make Move
                    st.session_state.board.push(cand['move'])
                    
                    # 3. Judge it (Since we clicked the best/good move, it should be green/blue)
                    st.session_state.feedback = ("✅ Best Move" if i==0 else "🆗 Good Alt", "green" if i==0 else "blue")
                    st.rerun()
                
                # Evaluation text below button
                st.markdown(f"<div style='text-align:center; color:gray; font-size:12px'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)
