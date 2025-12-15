import streamlit as st
import chess
import chess.engine
import chess.svg
import chess.pgn
import io
import base64

# --- CONFIG ---
st.set_page_config(page_title="Gotham-Style Analyst", layout="wide")
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
        size=550,
        arrows=arrows,
        lastmove=board.peek() if board.move_stack else None,
        colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
    )
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="100%" />'

# --- LOGIC: GOTHAM NARRATIVE GENERATOR ---
def generate_narrative(board, move):
    """Generates a 'YouTuber-style' explanation for the move."""
    narrative = []
    
    # 1. Opening specifics
    if board.fullmove_number < 3:
        if move.uci() == "e2e4": return "Best by test! Controlling the center and opening lines for the Queen/Bishop."
        if move.uci() == "d2d4": return "Solid and controlling. Stops Black from playing e5 easily."
        if move.uci() == "g1f3": return "Developing the Knight to a natural square. Flexible."

    # 2. Check & Capture
    if board.gives_check(move):
        narrative.append("Forcing move! The King must respond.")
    if board.is_capture(move):
        if board.piece_type_at(move.to_square) == chess.QUEEN:
            narrative.append("Capturing the Queen! Huge material swing.")
        else:
            narrative.append("Trading material or capturing a loose piece.")

    # 3. Piece Activity
    piece_type = board.piece_type_at(move.from_square)
    if piece_type == chess.KNIGHT:
        if move.to_square in [chess.C3, chess.F3, chess.C6, chess.F6]:
            narrative.append("Developing the Knight to its best square.")
        else:
            narrative.append("Maneuvering the Knight to an outpost.")
            
    if piece_type == chess.BISHOP:
        if "g2" in move.uci() or "b2" in move.uci() or "g7" in move.uci() or "b7" in move.uci():
            narrative.append("Fianchetto! The Bishop becomes a sniper on the long diagonal.")
        else:
            narrative.append("Activating the Bishop to control open diagonals.")

    if board.is_castling(move):
        narrative.append("Safety first! Tucking the King away and connecting Rooks.")

    # 4. Threats (Simple Lookahead)
    board.push(move)
    if board.is_checkmate():
        board.pop()
        return "GAME OVER. Checkmate!"
    
    # Check if we attack high value targets
    for sq in board.attacks(move.to_square):
        target = board.piece_at(sq)
        if target and target.color != board.turn and target.piece_type == chess.QUEEN:
            narrative.append("Attacking the Queen! They have to move it.")
            break
    board.pop()
    
    if not narrative:
        return "A solid positional improvement, improving piece coordination."
        
    return " ".join(narrative)

# --- LOGIC: ANALYSIS ---
def get_analysis(board, engine_path):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return None, []
    
    info = engine.analyse(board, chess.engine.Limit(time=0.4), multipv=3)
    candidates = []
    
    for line in info:
        move = line["pv"][0]
        score = line["score"].relative.score(mate_score=10000)
        if score is None: score = 0
        
        # Beginner Bonus
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
            "narrative": generate_narrative(board, move) # NEW Narrative
        })
    
    engine.quit()
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
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
st.title("♟️ Gotham-Style Chess Analyst")

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
col_main, col_info = st.columns([1.6, 1.2])

# ANALYSIS
with st.spinner("Thinking..."):
    best_plan, candidates = get_analysis(st.session_state.board, STOCKFISH_PATH)

# ARROWS
arrows = []
if best_plan:
    m1 = best_plan['move']
    arrows.append(chess.svg.Arrow(m1.from_square, m1.to_square, color="#4CAF50"))
    if len(best_plan['pv']) > 1:
        m2 = best_plan['pv'][1]
        arrows.append(chess.svg.Arrow(m2.from_square, m2.to_square, color="#2196F3"))

# === LEFT: BOARD ===
with col_main:
    st.markdown(render_board(st.session_state.board, arrows), unsafe_allow_html=True)
    
    # NAVIGATION & SYNC LOGIC
    if st.session_state.game_moves:
        c1, c2, c3 = st.columns([1,2,1])
        
        # LOGIC: Are we currently ON the game path?
        # We check by seeing if the board matches what the game expects at move_index
        on_track = True
        temp_board = chess.Board()
        for i in range(st.session_state.move_index):
            temp_board.push(st.session_state.game_moves[i])
            
        if temp_board.fen() != st.session_state.board.fen():
            on_track = False

        with c3:
            # IF ON TRACK: Show "Next Move"
            if on_track:
                if st.button("Next Move ▶", use_container_width=True) and st.session_state.move_index < len(st.session_state.game_moves):
                    # Prepare Eval
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
            
            # IF OFF TRACK: Show "Resume Game" (The Fix!)
            else:
                if st.button("⏩ Resume Game Line", use_container_width=True):
                    # Force Reset Board to Sync Point
                    st.session_state.board = temp_board
                    # Play the move we were supposed to play
                    if st.session_state.move_index < len(st.session_state.game_moves):
                        move = st.session_state.game_moves[st.session_state.move_index]
                        st.session_state.board.push(move)
                        st.session_state.move_index += 1
                    st.session_state.feedback = None # Reset feedback on resume
                    st.rerun()

        with c1:
            if st.button("◀ Undo"):
                if st.session_state.board.move_stack:
                    st.session_state.board.pop()
                    # Only decrement index if we are on track or undoing into track
                    if on_track and st.session_state.move_index > 0:
                         st.session_state.move_index -= 1
                    st.session_state.feedback = None
                    st.rerun()
    else:
        if st.button("◀ Undo Last Move"):
            if st.session_state.board.move_stack:
                st.session_state.board.pop()
                st.session_state.feedback = None
                st.rerun()

# === RIGHT: INFO ===
with col_info:
    
    # 1. FEEDBACK
    if st.session_state.feedback:
        label, color = st.session_state.feedback
        st.markdown(f"""
        <div style="background-color: {color}; color: white; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
            <h2 style="margin:0;">{label}</h2>
        </div>
        """, unsafe_allow_html=True)

    # 2. EXPLANATION (GOTHAM STYLE)
    st.subheader("💡 Analysis")
    if best_plan:
        c1, c2 = st.columns(2)
        c1.metric("Eval", f"{best_plan['eval']:+.2f}")
        c2.metric("Best Move", best_plan['san'])
        
        # RICH NARRATIVE
        st.info(f"**Engine says:** {best_plan['narrative']}")
        st.caption(f"Line: {st.session_state.board.variation_san(best_plan['pv'])}")
    
    st.divider()

    # 3. PLAYABLE MOVES
    st.subheader("Play Recommended Move")
    if candidates:
        cols1 = st.columns(3)
        for i, cand in enumerate(candidates[:3]):
            with cols1[i]:
                # If we click this, we DEVIATE from the PGN (if loaded)
                if st.button(f"{cand['san']}", key=f"top_{i}", use_container_width=True):
                    st.session_state.last_best_eval = candidates[0]['eval']
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback = ("✅ Best Move" if i==0 else "🆗 Alternative", "green" if i==0 else "blue")
                    st.rerun()
                st.markdown(f"<div style='text-align:center; font-size:12px; color:gray'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)
