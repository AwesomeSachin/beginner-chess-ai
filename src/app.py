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
        size=550,
        arrows=arrows,
        lastmove=board.peek() if board.move_stack else None,
        colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
    )
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="100%" style="display:block; margin-bottom:10px;" />'

# --- LOGIC 1: POSITIVE EXPLANATION (Good Moves) ---
def explain_good_move(board_before, move):
    narrative = []
    board_after = board_before.copy()
    board_after.push(move)
    
    # 1. TACTICS
    if board_before.is_capture(move):
        victim = board_before.piece_at(move.to_square)
        if victim: narrative.append(f"Captures {chess.piece_name(victim.piece_type)}.")
        else: narrative.append("Recaptures material.")

    # 2. DEFENSE
    if board_before.is_attacked_by(not board_before.turn, move.from_square):
        narrative.append("Escapes a threat.")

    # 3. THREATS
    new_threats = []
    for sq in board_after.attacks(move.to_square):
        target = board_after.piece_at(sq)
        if target and target.color != board_before.turn:
            if target.piece_type == chess.QUEEN: new_threats.append("Queen")
            elif target.piece_type == chess.ROOK: new_threats.append("Rook")
    if new_threats: narrative.append(f"Attacks the {new_threats[0]}!")

    # 4. STRATEGY
    if not narrative:
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            narrative.append("Controls the center.")
        elif board_before.is_castling(move):
            narrative.append("Castles for safety.")
        elif board_before.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]:
            narrative.append("Active development.")
        elif board_before.piece_type_at(move.from_square) == chess.PAWN:
             rank = chess.square_rank(move.to_square)
             if (board_before.turn == chess.WHITE and rank >= 4) or (board_before.turn == chess.BLACK and rank <= 3):
                 narrative.append("Takes space.")

    if not narrative: return "Solid improvement."
    return " ".join(narrative)

# --- LOGIC 2: NEGATIVE EXPLANATION (Bad Moves) ---
def explain_bad_move(board_before, played_move, best_move, engine):
    """Checks WHY the move is bad by looking at opponent response."""
    
    # 1. BLUNDER CHECK (Hanging Piece)
    board_after = board_before.copy()
    board_after.push(played_move)
    
    # Did we just hang a piece?
    if board_after.is_attacked_by(not board_after.turn, played_move.to_square):
        if not board_before.is_capture(played_move): # If it wasn't a trade
            # Is it defended?
            if not board_after.is_attacked_by(board_after.turn, played_move.to_square):
                 return "Blunder. You moved to a square where the piece can be taken for free."

    # 2. WHAT DOES THE OPPONENT DO NOW?
    # Ask engine for opponent's best response
    try:
        info = engine.analyse(board_after, chess.engine.Limit(time=0.1))
        opp_resp = info["pv"][0]
        opp_san = board_after.san(opp_resp)
        
        # If opponent captures something
        if board_after.is_capture(opp_resp):
            return f"Mistake. Allows opponent to capture with {opp_san}."
        
        # If opponent takes center
        if opp_resp.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            return f"Passive. Allows opponent to take the center with {opp_san}."
            
        return f"Inaccuracy. Allows opponent to play {opp_san} and seize the initiative."
    except:
        return "Mistake. Weakens your position."

# --- LOGIC: JUDGE MOVE (Determines Color/Label) ---
def get_move_feedback(diff, board_before, move, best_move_obj, engine):
    
    # 1. ASSIGN LABEL & COLOR
    if diff <= 0.2:
        label, color = "✅ Excellent", "green"
        text = explain_good_move(board_before, move)
    elif diff <= 0.5:
        label, color = "🆗 Good", "blue"
        text = explain_good_move(board_before, move)
    elif diff <= 1.2:
        label, color = "⚠️ Inaccuracy", "orange"
        text = explain_bad_move(board_before, move, best_move_obj, engine)
    elif diff <= 2.5:
        label, color = "❌ Mistake", "#FF5722"
        text = explain_bad_move(board_before, move, best_move_obj, engine)
    else:
        label, color = "😱 Blunder", "red"
        text = "Severe Error. Likely hung a piece or missed a mate."
        
    return {"label": label, "color": color, "text": text}

# --- MAIN ANALYSIS ENGINE ---
def get_analysis(board, engine_path):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return None, []
    
    # Analyze Top 9 moves
    info = engine.analyse(board, chess.engine.Limit(time=0.4), multipv=9)
    candidates = []
    
    # Identify BEST move details
    if info:
        best_score_raw = info[0]["score"].relative.score(mate_score=10000) or 0
        best_move_obj = info[0]["pv"][0]
    else:
        best_score_raw = 0
        best_move_obj = None

    for line in info:
        move = line["pv"][0]
        score = line["score"].relative.score(mate_score=10000)
        if score is None: score = 0
        
        # --- ML WEIGHTS ---
        w_check = 0.5792
        w_capture = 0.1724
        w_center = 0.0365
        
        bonus = 0
        board.push(move)
        if board.is_check(): bonus += w_check
        if board.is_capture(move): bonus += w_capture
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]: bonus += w_center
        board.pop()
        
        final_score = (score/100) + bonus
        
        # --- PRE-CALCULATE FEEDBACK FOR BUTTONS ---
        # We calculate the label NOW so the button matches the text
        diff = (best_score_raw - score) / 100
        feedback = get_move_feedback(diff, board, move, best_move_obj, engine)

        candidates.append({
            "move": move,
            "san": board.san(move),
            "eval": score/100,
            "score": final_score,
            "pv": line["pv"][:5],
            "feedback": feedback # Store the correct label/color
        })
    
    engine.quit()
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    return candidates[0] if candidates else None, candidates

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

# LAYOUT
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
    st.markdown(render_board(st.session_state.board, arrows), unsafe_allow_html=True)
    
    # NAVIGATION
    if st.session_state.game_moves:
        c1, c2, c3 = st.columns([0.8, 2, 0.8])
        
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
                    # Data Capture
                    board_before = st.session_state.board.copy()
                    expected_eval = best_plan['eval'] if best_plan else 0
                    best_move_obj = best_plan['move'] if best_plan else None
                    
                    move = st.session_state.game_moves[st.session_state.move_index]
                    st.session_state.board.push(move)
                    st.session_state.move_index += 1
                    
                    # RUN TEMP ENGINE FOR FEEDBACK
                    # We need the engine instance to explain bad moves
                    temp_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
                    
                    # Analyze Result
                    new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                    curr_eval = new_best['eval'] if new_best else 0
                    
                    # Calculate Diff
                    diff = expected_eval - (-curr_eval)
                    
                    st.session_state.feedback_data = get_move_feedback(diff, board_before, move, best_move_obj, temp_engine)
                    temp_engine.quit()
                    st.rerun()
            else:
                if st.button("Sync ⏩", use_container_width=True):
                    # Resume
                    st.session_state.board = game_board_at_index
                    if st.session_state.move_index < len(st.session_state.game_moves):
                        move = st.session_state.game_moves[st.session_state.move_index]
                        
                        resume_best, _ = get_analysis(game_board_at_index, STOCKFISH_PATH)
                        exp_eval = resume_best['eval'] if resume_best else 0
                        best_mv = resume_best['move'] if resume_best else None
                        
                        st.session_state.board.push(move)
                        st.session_state.move_index += 1
                        
                        temp_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
                        new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                        curr_eval = new_best['eval'] if new_best else 0
                        
                        diff = exp_eval - (-curr_eval)
                        st.session_state.feedback_data = get_move_feedback(diff, game_board_at_index, move, best_mv, temp_engine)
                        temp_engine.quit()
                    st.rerun()
    else:
        if st.button("◀ Undo Last", use_container_width=True):
            if st.session_state.board.move_stack:
                st.session_state.board.pop()
                st.session_state.feedback_data = None
                st.rerun()

# === RIGHT: INFO PANEL ===
with col_info:
    
    # 1. FEEDBACK BANNER
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
        
        # Engine explanation uses the Good Logic (always positive for suggestions)
        st.markdown(f"**Reason:** {explain_good_move(st.session_state.board, best_plan['move'])}")
        st.caption(f"Line: {st.session_state.board.variation_san(best_plan['pv'])}")
    
    st.divider()

    # 3. ALTERNATIVE MOVES
    st.subheader("Explore Alternative Moves")
    if candidates:
        # Create grid
        cols = st.columns(3)
        for i, cand in enumerate(candidates[:9]): # Top 9 moves
            col = cols[i % 3] # Cycle through columns
            
            with col:
                # DYNAMIC LABELING: Use the pre-calculated feedback
                fb = cand['feedback']
                
                # Button Text: Move SAN
                if st.button(f"{cand['san']}", key=f"move_{i}", use_container_width=True):
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback_data = fb
                    st.rerun()
                
                # Label under button (Colored based on quality)
                st.markdown(f"""
                <div style='text-align:center; font-size:12px; margin-top:-10px; margin-bottom:10px;'>
                    <span style='color:{fb['color']}; font-weight:bold;'>{fb['label']}</span> ({cand['eval']:+.2f})
                </div>
                """, unsafe_allow_html=True)
