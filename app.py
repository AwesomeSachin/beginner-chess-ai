import streamlit as st
import chess
import chess.engine
import chess.svg
import chess.pgn
import io
import base64

# --- CONFIG ---
st.set_page_config(page_title="Deep Logic Chess", layout="wide")
STOCKFISH_PATH = "/usr/games/stockfish"

# --- STATE ---
if 'board' not in st.session_state: st.session_state.board = chess.Board()
if 'game_moves' not in st.session_state: st.session_state.game_moves = []
if 'move_index' not in st.session_state: st.session_state.move_index = 0
if 'last_best_eval' not in st.session_state: st.session_state.last_best_eval = 0.35
if 'feedback_data' not in st.session_state: st.session_state.feedback_data = None # Stores label, color, AND explanation

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

# --- LOGIC: DEEP EXPLANATION GENERATOR ---
def explain_move(board_before, move):
    """
    Compares state BEFORE and AFTER the move to find the LOGICAL reason.
    """
    narrative = []
    board_after = board_before.copy()
    board_after.push(move)
    
    # 1. DID WE CAPTURE?
    if board_before.is_capture(move):
        victim = board_before.piece_at(move.to_square)
        if victim:
            narrative.append(f"Captures the {victim.symbol().upper()} (Material Gain).")
        else:
            narrative.append("Recaptures material.")

    # 2. DID WE SAVE A PIECE? (Defensive Logic)
    # Check if the moving piece was under attack on its old square
    was_attacked = board_before.is_attacked_by(not board_before.turn, move.from_square)
    if was_attacked:
        narrative.append("Escapes a threat! The piece was under attack.")

    # 3. DID WE CREATE A THREAT? (Aggressive Logic)
    # Check what we are attacking NOW that we weren't before
    new_threats = []
    for sq in board_after.attacks(move.to_square):
        target = board_after.piece_at(sq)
        if target and target.color != board_before.turn: # Enemy piece
            if target.piece_type == chess.QUEEN: new_threats.append("Queen")
            elif target.piece_type == chess.ROOK: new_threats.append("Rook")
    
    if new_threats:
        narrative.append(f"Creates a direct threat on the {new_threats[0]}!")

    # 4. OPENING CONCEPTS (Early Game)
    if board_before.fullmove_number < 8:
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5, chess.C4, chess.C5]:
            narrative.append("Fights for central control.")
        elif board_before.piece_type_at(move.from_square) == chess.KNIGHT:
            narrative.append("Develops the Knight to an active square.")
        elif board_before.is_castling(move):
            narrative.append("Castles for King Safety.")

    # 5. CHECK / MATE
    if board_after.is_checkmate():
        return "CHECKMATE! The game is won."
    if board_after.is_check():
        narrative.append("Delivers Check, forcing a response.")

    # 6. PAWN LOGIC (If no big tactics found)
    if not narrative and board_before.piece_type_at(move.from_square) == chess.PAWN:
        if board_before.is_passed(move.to_square):
            narrative.append("Creates a dangerous Passed Pawn!")
        else:
            narrative.append("Improves pawn structure and takes space.")

    # Fallback if move is subtle
    if not narrative:
        return "A quiet positional move improving piece coordination."
        
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
        
        candidates.append({
            "move": move,
            "san": board.san(move),
            "eval": score/100,
            "score": score/100,
            "pv": line["pv"][:5],
            "explanation": explain_move(board, move) # Generate explanation for future moves
        })
    
    engine.quit()
    return candidates[0] if candidates else None, candidates

def judge_move(current_eval, best_eval, board_before, move):
    """Returns Label, Color, AND Detailed Explanation."""
    diff = best_eval - (-current_eval) # Flip perspective
    
    # 1. Determine Label
    if diff <= 0.2: label, color = "✅ Excellent", "green"
    elif diff <= 0.7: label, color = "🆗 Good", "blue"
    elif diff <= 1.5: label, color = "⚠️ Inaccuracy", "orange"
    elif diff <= 3.0: label, color = "❌ Mistake", "#FF5722"
    else: label, color = "😱 Blunder", "red"

    # 2. Get Logic Explanation
    explanation = explain_move(board_before, move)
    
    return {"label": label, "color": color, "text": explanation}

# --- UI START ---
st.title("♟️ Deep Logic Chess Analyst")

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
                st.session_state.feedback_data = None
                st.session_state.last_best_eval = 0.35 # Reset eval
                st.rerun()
            except:
                st.error("Invalid PGN")
    if st.button("🗑️ Clear Board"):
        st.session_state.board.reset()
        st.session_state.game_moves = []
        st.session_state.feedback_data = None
        st.rerun()

# LAYOUT
col_main, col_info = st.columns([1.6, 1.2])

# AUTO-ANALYSIS (Current Board)
with st.spinner("Analyzing..."):
    best_plan, candidates = get_analysis(st.session_state.board, STOCKFISH_PATH)

# ARROWS
arrows = []
if best_plan:
    m1 = best_plan['move']
    arrows.append(chess.svg.Arrow(m1.from_square, m1.to_square, color="#4CAF50"))

# === LEFT: BOARD ===
with col_main:
    # FEEDBACK BANNER (Shows Result of PREVIOUS move)
    if st.session_state.feedback_data:
        data = st.session_state.feedback_data
        st.markdown(f"""
        <div style="background-color: {data['color']}; color: white; padding: 15px; border-radius: 8px; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h2 style="margin:0; text-align: center;">{data['label']}</h2>
            <hr style="margin: 5px 0; border-color: rgba(255,255,255,0.3);">
            <p style="margin:0; text-align: center; font-size: 16px;"><b>Reason:</b> {data['text']}</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown(render_board(st.session_state.board, arrows), unsafe_allow_html=True)
    
    # NAVIGATION & SYNC
    if st.session_state.game_moves:
        c1, c2, c3 = st.columns([1,2,1])
        
        # Check Sync
        temp_board = chess.Board()
        for i in range(st.session_state.move_index):
            temp_board.push(st.session_state.game_moves[i])
        on_track = (temp_board.fen() == st.session_state.board.fen())

        with c3:
            if on_track:
                if st.button("Next Move ▶", use_container_width=True) and st.session_state.move_index < len(st.session_state.game_moves):
                    # Capture State BEFORE Move
                    board_before = st.session_state.board.copy()
                    expected_eval = best_plan['eval'] if best_plan else 0
                    
                    # Make Move
                    move = st.session_state.game_moves[st.session_state.move_index]
                    st.session_state.board.push(move)
                    st.session_state.move_index += 1
                    
                    # Analyze AFTER
                    new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                    current_eval = new_best['eval'] if new_best else 0
                    
                    # Generate Feedback
                    st.session_state.feedback_data = judge_move(current_eval, expected_eval, board_before, move)
                    st.rerun()
            else:
                if st.button("⏩ Resume Game Line", use_container_width=True):
                    # Sync Logic
                    st.session_state.board = temp_board
                    if st.session_state.move_index < len(st.session_state.game_moves):
                        move = st.session_state.game_moves[st.session_state.move_index]
                        
                        # We need to analyze 'temp_board' to get the expected eval for proper judging
                        resume_best, _ = get_analysis(temp_board, STOCKFISH_PATH)
                        exp_eval = resume_best['eval'] if resume_best else 0
                        
                        st.session_state.board.push(move)
                        st.session_state.move_index += 1
                        
                        # Analyze result
                        new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                        curr_eval = new_best['eval'] if new_best else 0
                        
                        st.session_state.feedback_data = judge_move(curr_eval, exp_eval, temp_board, move)
                    st.rerun()

        with c1:
            if st.button("◀ Undo"):
                if st.session_state.board.move_stack:
                    st.session_state.board.pop()
                    if on_track and st.session_state.move_index > 0: st.session_state.move_index -= 1
                    st.session_state.feedback_data = None
                    st.rerun()
    else:
        if st.button("◀ Undo Last Move"):
            if st.session_state.board.move_stack:
                st.session_state.board.pop()
                st.session_state.feedback_data = None
                st.rerun()

# === RIGHT: INFO ===
with col_info:
    
    st.subheader("💡 Engine Suggestion (Next)")
    if best_plan:
        st.metric("Eval", f"{best_plan['eval']:+.2f}")
        st.info(f"**Best Move:** {best_plan['san']}")
        st.write(f"**Why:** {best_plan['explanation']}")
    
    st.divider()

    st.subheader("Play Recommended Move")
    if candidates:
        cols1 = st.columns(3)
        for i, cand in enumerate(candidates[:3]):
            with cols1[i]:
                if st.button(f"{cand['san']}", key=f"top_{i}", use_container_width=True):
                    # Capture State
                    board_before = st.session_state.board.copy()
                    expected_eval = candidates[0]['eval']
                    
                    # Make Move
                    st.session_state.board.push(cand['move'])
                    
                    # Feedback (Since we clicked a candidate, we know it's good)
                    # We just use the candidate's own explanation
                    st.session_state.feedback_data = {
                        "label": "✅ Best Move" if i==0 else "🆗 Good Alternative",
                        "color": "green" if i==0 else "blue",
                        "text": cand['explanation']
                    }
                    st.rerun()
                st.markdown(f"<div style='text-align:center; font-size:12px; color:gray'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)
