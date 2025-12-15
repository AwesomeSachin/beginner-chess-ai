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
if 'last_best_eval' not in st.session_state: st.session_state.last_best_eval = 0.35
if 'feedback' not in st.session_state: st.session_state.feedback = None

# --- HELPER: RENDER BOARD ---
def render_board(board, arrows=[]):
    board_svg = chess.svg.board(
        board=board, 
        size=550, # Slightly larger for better visibility
        arrows=arrows,
        lastmove=board.peek() if board.move_stack else None,
        colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
    )
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="100%" />'

# --- LOGIC: CONCEPT DETECTION ---
def detect_concept(board, move):
    """Returns a simple string explaining the chess concept."""
    # 1. Tactics
    if board.is_capture(move): return "⚔️ Material Gain / Trade"
    if board.gives_check(move): return "🔥 King Attack (Check)"
    
    # 2. Opening / Strategy
    if board.fullmove_number < 15:
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]: return "🎯 Center Control"
        if board.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]: return "🐴 Piece Development"
        if board.is_castling(move): return "🛡️ King Safety (Castling)"
    
    # 3. Endgame / Structure
    if board.piece_type_at(move.from_square) == chess.PAWN: return "♟️ Pawn Structure / Space"
    if board.piece_type_at(move.from_square) == chess.KING: return "👑 King Activity"
    
    return "🧠 Positional Improvement"

# --- LOGIC: ANALYSIS ---
def get_analysis(board, engine_path):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return None, []
    
    # Analyze Top 5 moves (More depth for the list)
    info = engine.analyse(board, chess.engine.Limit(time=0.5), multipv=5)
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
            "score": (score/100) + bonus,
            "pv": line["pv"][:5],
            "concept": detect_concept(board, move) # Add Concept
        })
    
    engine.quit()
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    # Update expected eval for feedback calculation
    if candidates:
        st.session_state.last_best_eval = candidates[0]['eval']
        
    return candidates[0] if candidates else None, candidates

def generate_feedback(current_board_eval):
    diff = st.session_state.last_best_eval - (-current_board_eval)
    if diff <= 0.2: return "✅ Excellent", "green"
    if diff <= 0.6: return "🆗 Good", "blue"
    if diff <= 1.5: return "⚠️ Inaccuracy", "orange"
    if diff <= 3.0: return "❌ Mistake", "#FF5722"
    return "😱 Blunder", "red"

# --- UI START ---
st.title("♟️ Chess Master Dashboard")

# SIDEBAR
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
    if st.button("🗑️ Clear Board"):
        st.session_state.board.reset()
        st.session_state.game_moves = []
        st.session_state.feedback = None
        st.rerun()

# LAYOUT
col_main, col_info = st.columns([1.6, 1.2]) # Wider board column

# AUTO-ANALYSIS
with st.spinner("Processing..."):
    best_plan, candidates = get_analysis(st.session_state.board, STOCKFISH_PATH)

# ARROWS
arrows = []
if best_plan:
    m1 = best_plan['move']
    arrows.append(chess.svg.Arrow(m1.from_square, m1.to_square, color="#4CAF50"))
    if len(best_plan['pv']) > 1:
        m2 = best_plan['pv'][1]
        arrows.append(chess.svg.Arrow(m2.from_square, m2.to_square, color="#2196F3"))

# === LEFT COLUMN: BOARD ===
with col_main:
    st.markdown(render_board(st.session_state.board, arrows), unsafe_allow_html=True)
    
    # Navigation
    if st.session_state.game_moves:
        c1, c2, c3 = st.columns([1,2,1])
        with c3:
            if st.button("Next Move ▶", use_container_width=True) and st.session_state.move_index < len(st.session_state.game_moves):
                # Update State
                before_eval = best_plan['eval'] if best_plan else 0
                st.session_state.last_best_eval = before_eval
                
                # Make Move
                move = st.session_state.game_moves[st.session_state.move_index]
                st.session_state.board.push(move)
                st.session_state.move_index += 1
                
                # Feedback
                new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                current_eval = new_best['eval'] if new_best else 0
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

# === RIGHT COLUMN: INFO PANEL (Ordered as Requested) ===
with col_info:
    
    # 1. FEEDBACK (TOP)
    if st.session_state.feedback:
        label, color = st.session_state.feedback
        st.markdown(f"""
        <div style="background-color: {color}; color: white; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h2 style="margin:0;">{label}</h2>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Placeholder so layout doesn't jump
        st.info("Make a move to see feedback.")

    # 2. ANALYSIS & CONCEPT (MIDDLE)
    st.subheader("🔍 Analysis")
    if best_plan:
        c1, c2 = st.columns(2)
        c1.metric("Evaluation", f"{best_plan['eval']:+.2f}")
        c2.metric("Best Move", best_plan['san'])
        
        # THE NEW CONCEPT SECTION
        st.markdown(f"**Strategy:** `{best_plan['concept']}`")
        
        st.info(f"**Plan:** {st.session_state.board.variation_san(best_plan['pv'])}")
    
    st.divider()

    # 3. PLAY RECOMMENDED MOVE (BOTTOM)
    st.subheader("Play Recommended Move")
    st.caption("Click any button to play the best moves (Ranked):")
    
    if candidates:
        # We display the top 6 moves in a grid (3 per row)
        # You can increase [:6] to show more
        
        # Row 1
        cols1 = st.columns(3)
        for i, cand in enumerate(candidates[:3]):
            with cols1[i]:
                if st.button(f"{i+1}. {cand['san']}", key=f"top_{i}", use_container_width=True):
                    st.session_state.last_best_eval = candidates[0]['eval']
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback = ("✅ Best Move" if i==0 else "🆗 Good Alt", "green" if i==0 else "blue")
                    st.rerun()
                st.markdown(f"<div style='text-align:center; font-size:12px; color:gray'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)

        # Row 2 (Moves 4-6)
        if len(candidates) > 3:
            cols2 = st.columns(3)
            for i, cand in enumerate(candidates[3:6]):
                idx = i + 3
                with cols2[i]:
                    if st.button(f"{idx+1}. {cand['san']}", key=f"sub_{idx}", use_container_width=True):
                        st.session_state.last_best_eval = candidates[0]['eval']
                        st.session_state.board.push(cand['move'])
                        st.session_state.feedback = ("🆗 Playable", "blue")
                        st.rerun()
                    st.markdown(f"<div style='text-align:center; font-size:12px; color:gray'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)
