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
if 'feedback_data' not in st.session_state: st.session_state.feedback_data = None 

# --- HELPER: RENDER BOARD ---
def render_board(board, arrows=[]):
    board_svg = chess.svg.board(
        board=board, 
        size=550, # Optimized size to prevent scrolling
        arrows=arrows,
        lastmove=board.peek() if board.move_stack else None,
        colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
    )
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="100%" style="display:block; margin-bottom:10px;" />'

# --- LOGIC: DEEP EXPLANATION GENERATOR (Restored V9 Logic) ---
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
            narrative.append(f"Captures the {chess.piece_name(victim.piece_type).capitalize()} (Material Gain).")
        else:
            narrative.append("Recaptures material.")

    # 2. DID WE SAVE A PIECE? (Defensive Logic)
    was_attacked = board_before.is_attacked_by(not board_before.turn, move.from_square)
    if was_attacked:
        narrative.append("Escapes a threat! The piece was under attack.")

    # 3. DID WE CREATE A THREAT? (Aggressive Logic)
    new_threats = []
    for sq in board_after.attacks(move.to_square):
        target = board_after.piece_at(sq)
        if target and target.color != board_before.turn: # Enemy piece
            if target.piece_type == chess.QUEEN: new_threats.append("Queen")
            elif target.piece_type == chess.ROOK: new_threats.append("Rook")
    
    if new_threats:
        narrative.append(f"Creates a direct threat on the {new_threats[0]}!")

    # 4. OPENING CONCEPTS
    if board_before.fullmove_number < 10:
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

    # 6. PAWN LOGIC
    if not narrative and board_before.piece_type_at(move.from_square) == chess.PAWN:
        # Check if pawn is pushing deep (Rank 6 or 7)
        rank = chess.square_rank(move.to_square)
        if (board_before.turn == chess.WHITE and rank >= 5) or (board_before.turn == chess.BLACK and rank <= 2):
            narrative.append("Pushing the pawn closer to promotion!")
        else:
            narrative.append("Improves pawn structure and takes space.")

    # Fallback
    if not narrative:
        return "A solid positional improvement, improving piece coordination."
        
    return " ".join(narrative)

# --- LOGIC: ANALYSIS ---
def get_analysis(board, engine_path):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return None, []
    
    # Analyze Top 9 moves for the grid
    info = engine.analyse(board, chess.engine.Limit(time=0.4), multipv=9)
    candidates = []
    
    for line in info:
        move = line["pv"][0]
        score = line["score"].relative.score(mate_score=10000)
        if score is None: score = 0
        
        candidates.append({
            "move": move,
            "san": board.san(move),
            "eval": score/100,
            "pv": line["pv"][:5],
            "explanation": explain_move(board, move) 
        })
    
    engine.quit()
    return candidates[0] if candidates else None, candidates

def judge_move(current_eval, best_eval, board_before, move):
    diff = best_eval - (-current_eval)
    if diff <= 0.2: label, color = "✅ Excellent", "green"
    elif diff <= 0.7: label, color = "🆗 Good", "blue"
    elif diff <= 1.5: label, color = "⚠️ Inaccuracy", "orange"
    elif diff <= 3.0: label, color = "❌ Mistake", "#FF5722"
    else: label, color = "😱 Blunder", "red"
    
    explanation = explain_move(board_before, move)
    return {"label": label, "color": color, "text": explanation}

# --- UI START ---
st.title("♟️ Deep Logic Chess Analyst")

# SIDEBAR
with st.sidebar:
    st.header("Load Game")
    pgn_txt = st.text_area("Paste PGN:", height=100)
    if st.button("Load & Reset"):
        if pgn_txt:
            try:
                pgn_io = io.StringIO(pgn_txt)
                game = chess.pgn.read_game(pgn_io)
                st.session_state.game_moves = list(game.mainline_moves())
                st.session_state.board = game.board()
                st.session_state.move_index = 0
                st.session_state.feedback_data = None
                st.session_state.last_best_eval = 0.35 
                st.rerun()
            except:
                st.error("Invalid PGN")
    if st.button("🗑️ Clear Board"):
        st.session_state.board.reset()
        st.session_state.game_moves = []
        st.session_state.feedback_data = None
        st.rerun()

# LAYOUT CONFIG
col_main, col_info = st.columns([1.5, 1.2])

# AUTO-ANALYSIS
with st.spinner("Processing..."):
    best_plan, candidates = get_analysis(st.session_state.board, STOCKFISH_PATH)

arrows = []
if best_plan:
    m1 = best_plan['move']
    arrows.append(chess.svg.Arrow(m1.from_square, m1.to_square, color="#4CAF50"))

# === LEFT: BOARD ===
with col_main:
    # 1. THE BOARD IMAGE
    st.markdown(render_board(st.session_state.board, arrows), unsafe_allow_html=True)
    
    # 2. NAVIGATION BUTTONS (Immediately below board)
    if st.session_state.game_moves:
        c1, c2, c3 = st.columns([0.8, 2, 0.8])
        
        # Sync Logic
        game_board_at_index = chess.Board()
        for i in range(st.session_state.move_index):
            game_board_at_index.push(st.session_state.game_moves[i])
        on_track = (game_board_at_index.fen() == st.session_state.board.fen())

        with c1:
             if st.button("◀ Undo", use_container_width=True):
                if st.session_state.board.move_stack:
                    st.session_state.board.pop()
                    if on_track and st.session_state.move_index > 0: 
                        st.session_state.move_index -= 1
                    
                    # Auto-fix index if we undo back into the line
                    undo_fen = st.session_state.board.fen()
                    temp = chess.Board()
                    if temp.fen() == undo_fen:
                        st.session_state.move_index = 0
                    else:
                        for i, m in enumerate(st.session_state.game_moves):
                            temp.push(m)
                            if temp.fen() == undo_fen:
                                st.session_state.move_index = i + 1
                                break
                    st.session_state.feedback_data = None
                    st.rerun()

        with c3:
            if on_track:
                if st.button("Next ▶", use_container_width=True) and st.session_state.move_index < len(st.session_state.game_moves):
                    # Capture State
                    board_before = st.session_state.board.copy()
                    expected_eval = best_plan['eval'] if best_plan else 0
                    
                    move = st.session_state.game_moves[st.session_state.move_index]
                    st.session_state.board.push(move)
                    st.session_state.move_index += 1
                    
                    new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                    curr_eval = new_best['eval'] if new_best else 0
                    
                    st.session_state.feedback_data = judge_move(curr_eval, expected_eval, board_before, move)
                    st.rerun()
            else:
                if st.button("Sync ⏩", use_container_width=True):
                    # Resume
                    st.session_state.board = game_board_at_index
                    if st.session_state.move_index < len(st.session_state.game_moves):
                        move = st.session_state.game_moves[st.session_state.move_index]
                        resume_best, _ = get_analysis(game_board_at_index, STOCKFISH_PATH)
                        exp_eval = resume_best['eval'] if resume_best else 0
                        st.session_state.board.push(move)
                        st.session_state.move_index += 1
                        new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                        curr_eval = new_best['eval'] if new_best else 0
                        st.session_state.feedback_data = judge_move(curr_eval, exp_eval, game_board_at_index, move)
                    st.rerun()
    else:
        if st.button("◀ Undo Last", use_container_width=True):
            if st.session_state.board.move_stack:
                st.session_state.board.pop()
                st.session_state.feedback_data = None
                st.rerun()

# === RIGHT: INFO PANEL ===
with col_info:
    
    # 1. COMPACT FEEDBACK BANNER (Right Side Top)
    if st.session_state.feedback_data:
        data = st.session_state.feedback_data
        st.markdown(f"""
        <div style="background-color: {data['color']}; color: white; padding: 10px; border-radius: 6px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h4 style="margin:0; text-align: center;">{data['label']}</h4>
            <p style="margin:0; text-align: center; font-size: 14px; margin-top:4px;">{data['text']}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background-color: #f0f2f6; color: #333; padding: 10px; border-radius: 6px; margin-bottom: 10px; text-align: center;">
            <p style="margin:0; font-size: 14px;">Make a move to see feedback.</p>
        </div>
        """, unsafe_allow_html=True)

    # 2. ENGINE SUGGESTION
    st.subheader("💡 Engine Suggestion")
    if best_plan:
        c_eval, c_move = st.columns([1, 2])
        c_eval.metric("Eval", f"{best_plan['eval']:+.2f}")
        c_move.success(f"**Best:** {best_plan['san']}")
        
        st.markdown(f"**Reason:** {best_plan['explanation']}")
        st.caption(f"Line: {st.session_state.board.variation_san(best_plan['pv'])}")
    
    st.divider()

    # 3. PLAYABLE MOVES (9 Moves Grid)
    st.subheader("Explore Alternative Moves")
    if candidates:
        # Row 1
        cols1 = st.columns(3)
        for i, cand in enumerate(candidates[:3]):
            with cols1[i]:
                if st.button(f"{cand['san']}", key=f"top_{i}", use_container_width=True):
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback_data = {
                        "label": "✅ Best Move" if i==0 else "🆗 Good Alt",
                        "color": "green" if i==0 else "blue",
                        "text": cand['explanation']
                    }
                    st.rerun()
                st.markdown(f"<div style='text-align:center; font-size:12px; color:gray; margin-top:-10px; margin-bottom:10px;'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)

        # Row 2
        cols2 = st.columns(3)
        for i, cand in enumerate(candidates[3:6]):
            idx = i + 3
            with cols2[i]:
                if st.button(f"{cand['san']}", key=f"mid_{idx}", use_container_width=True):
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback_data = {"label": "🆗 Playable", "color": "blue", "text": cand['explanation']}
                    st.rerun()
                st.markdown(f"<div style='text-align:center; font-size:12px; color:gray; margin-top:-10px; margin-bottom:10px;'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)
                
        # Row 3
        cols3 = st.columns(3)
        for i, cand in enumerate(candidates[6:9]):
            idx = i + 6
            with cols3[i]:
                if st.button(f"{cand['san']}", key=f"low_{idx}", use_container_width=True):
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback_data = {"label": "⚠️ Risky", "color": "orange", "text": cand['explanation']}
                    st.rerun()
                st.markdown(f"<div style='text-align:center; font-size:12px; color:gray; margin-top:-10px; margin-bottom:10px;'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)
