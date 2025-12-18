import streamlit as st
import chess
import chess.engine
import chess.svg
import chess.pgn
import io
import base64

# --- CONFIG ---
st.set_page_config(page_title="Deep Logic Chess (Pro)", layout="wide")
STOCKFISH_PATH = "/usr/games/stockfish"

# --- STATE ---
if 'board' not in st.session_state: st.session_state.board = chess.Board()
if 'game_moves' not in st.session_state: st.session_state.game_moves = []
if 'move_index' not in st.session_state: st.session_state.move_index = 0
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

# --- NEW LOGIC: MATERIAL CALCULATOR ---
def get_material_balance(board):
    # Standard Piece Values
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    white_mat = sum(len(board.pieces(pt, chess.WHITE)) * val for pt, val in values.items())
    black_mat = sum(len(board.pieces(pt, chess.BLACK)) * val for pt, val in values.items())
    return white_mat, black_mat

# --- NEW LOGIC: EXPLAINER ENGINE ---
def get_deep_explanation(board_before, move, eval_diff, engine):
    """
    Rebuilt from scratch to focus on CONSEQUENCES (Material changes, Threats).
    """
    board_after = board_before.copy()
    board_after.push(move)
    
    # 1. MATERIAL CHANGE CHECK (Did we lose/gain stuff?)
    w_before, b_before = get_material_balance(board_before)
    w_after, b_after = get_material_balance(board_after)
    
    # Perspective: Did the mover improve their material?
    if board_before.turn == chess.WHITE:
        mat_diff = w_after - w_before
    else:
        mat_diff = b_after - b_before

    # 2. CHECK FOR BLUNDERS (Huge Eval Drop > 1.5)
    if eval_diff > 1.5:
        # Case A: We moved into a square where we get eaten (Hanging Piece)
        if board_after.is_attacked_by(board_after.turn, move.to_square):
             # If we didn't capture anything valuable, it's a pure blunder
             if mat_diff <= 0:
                 return "Blunder. You simply hung a piece for free."
        
        # Case B: We allowed a forced mate
        if board_after.is_checkmate():
            return "Catastrophe. You allowed immediate checkmate."
            
        # Case C: Ask Engine "Why is this so bad?" (The Refutation)
        try:
            info = engine.analyse(board_after, chess.engine.Limit(time=0.1))
            opp_response = info["pv"][0]
            opp_piece = board_after.piece_at(opp_response.from_square)
            p_name = chess.piece_name(opp_piece.piece_type) if opp_piece else "piece"
            return f"Blunder. Opponent can reply with {board_after.san(opp_response)} and win material."
        except:
            return "Severe Mistake. You missed a critical tactical threat."

    # 3. CHECK FOR TACTICS (Good Moves)
    if board_before.is_capture(move):
        # Did we win material?
        if mat_diff > 0:
            return f"Winning Trade. You gained material (+{mat_diff})."
        elif mat_diff == 0:
             return "Trade. You exchanged pieces evenly."
        else:
             # Negative material difference on a capture = Bad Trade
             if eval_diff > 0.5:
                 return "Bad Trade. You gave up more value than you got."
             else:
                 return "Sacrifice? You gave up material for activity."

    # 4. POSITIONAL LOGIC (If no tactics involved)
    # Center Control
    if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5, chess.C4, chess.C5, chess.F4, chess.F5]:
        return "Central Control. Takes ownership of the most important squares."
    
    # Development (Knights/Bishops)
    piece_type = board_before.piece_type_at(move.from_square)
    if piece_type in [chess.KNIGHT, chess.BISHOP]:
        # Check if it moved forward
        rank_before = chess.square_rank(move.from_square)
        rank_after = chess.square_rank(move.to_square)
        if (board_before.turn == chess.WHITE and rank_after > rank_before) or \
           (board_before.turn == chess.BLACK and rank_after < rank_before):
            return "Development. Brings a piece into the fight."

    # Safety
    if board_before.is_castling(move):
        return "King Safety. Castling protects the king and connects rooks."

    # Passive Checks
    if eval_diff > 0.3:
        return "Inaccuracy. Passive play that gives the opponent time."

    return "Solid move. Improves position slightly."

# --- ANALYSIS LOOP ---
def get_analysis(board, engine_path):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return None, []
    
    # 1. Get Best Move First (The Benchmark)
    best_info = engine.analyse(board, chess.engine.Limit(time=0.4))
    best_score_val = best_info["score"].relative.score(mate_score=10000) or 0
    best_move_san = board.san(best_info["pv"][0])

    # 2. Get Top Candidates
    info = engine.analyse(board, chess.engine.Limit(time=0.4), multipv=9)
    candidates = []
    
    for line in info:
        move = line["pv"][0]
        score = line["score"].relative.score(mate_score=10000)
        if score is None: score = 0
        
        # --- YOUR ML LOGIC (Still Valid!) ---
        # We keep this to rank moves, but we use the NEW logic to explain them.
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
        
        # Calculate Diff for Feedback
        diff = (best_score_raw - score) / 100 if 'best_score_raw' in locals() else 0

        # Generate Explanation using NEW ENGINE
        explanation = get_deep_explanation(board, move, diff, engine)

        # Determine Label
        if diff <= 0.2:
            label, color = "✅ Excellent", "green"
        elif diff <= 0.6:
            label, color = "🆗 Good", "blue"
        elif diff <= 1.5:
            label, color = "⚠️ Inaccuracy", "orange"
        else:
            label, color = "❌ Mistake", "red"

        candidates.append({
            "move": move,
            "san": board.san(move),
            "score": final_score,
            "eval": score/100,
            "label": label,
            "color": color,
            "explanation": explanation
        })

    engine.quit()
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[0] if candidates else None, candidates

# --- UI START ---
st.title("♟️ Deep Logic Chess (Pro Logic)")

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
with st.spinner("Analyzing position..."):
    # We need to pass the current best score to the loop, so let's grab it inside get_analysis
    # Note: To save time, we do it all in one function now.
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
                    # Auto-sync logic
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
                    # CAPTURE STATE BEFORE MOVE
                    board_before = st.session_state.board.copy()
                    
                    # PLAY MOVE
                    move = st.session_state.game_moves[st.session_state.move_index]
                    st.session_state.board.push(move)
                    st.session_state.move_index += 1
                    
                    # ANALYZE AFTER
                    # To judge the move, we compare it to what Stockfish WOULD have done
                    temp_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
                    
                    # 1. What was the eval of the BEST move available?
                    best_info = temp_engine.analyse(board_before, chess.engine.Limit(time=0.1))
                    best_eval = best_info["score"].relative.score(mate_score=10000) or 0
                    
                    # 2. What is the eval of the move WE PLAYED?
                    # We have to force analyze the specific move
                    board_test = board_before.copy()
                    board_test.push(move)
                    curr_info = temp_engine.analyse(board_test, chess.engine.Limit(time=0.1))
                    # Note: The eval of board_after is from opponent perspective, so we negate
                    curr_eval = -curr_info["score"].relative.score(mate_score=10000) or 0
                    
                    diff = (best_eval - curr_eval) / 100
                    
                    # GET EXPLANATION
                    expl = get_deep_explanation(board_before, move, diff, temp_engine)
                    
                    # SET FEEDBACK
                    if diff <= 0.2:
                        lbl, clr = "✅ Excellent", "green"
                    elif diff <= 0.6:
                        lbl, clr = "🆗 Good", "blue"
                    elif diff <= 1.5:
                        lbl, clr = "⚠️ Inaccuracy", "orange"
                    else:
                        lbl, clr = "❌ Mistake", "red"
                        
                    st.session_state.feedback_data = {"label": lbl, "color": clr, "text": expl}
                    temp_engine.quit()
                    st.rerun()
            else:
                if st.button("Sync ⏩", use_container_width=True):
                    st.session_state.board = game_board_at_index
                    if st.session_state.move_index < len(st.session_state.game_moves):
                        move = st.session_state.game_moves[st.session_state.move_index]
                        st.session_state.board.push(move)
                        st.session_state.move_index += 1
                        st.session_state.feedback_data = None
                    st.rerun()

# === RIGHT: FEEDBACK PANEL ===
with col_info:
    
    # 1. FEEDBACK BANNER (Instant Feedback on Last Move)
    if st.session_state.feedback_data:
        data = st.session_state.feedback_data
        st.markdown(f"""
        <div style="background-color: {data['color']}; color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 style="margin:0; text-align: center;">{data['label']}</h3>
            <p style="margin:0; text-align: center; font-size: 16px; margin-top:8px; font-weight: 500;">{data['text']}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Make a move to see the deep analysis.")

    # 2. SUGGESTION
    st.subheader("💡 Best Plan")
    if best_plan:
        c_eval, c_move = st.columns([1, 2])
        c_eval.metric("Eval", f"{best_plan['eval']:+.2f}")
        c_move.success(f"**Recommends:** {best_plan['san']}")
        st.caption(f"Logic: {best_plan['explanation']}")

    st.divider()

    # 3. ALTERNATIVES
    st.subheader("Other Options")
    if candidates:
        cols = st.columns(3)
        for i, cand in enumerate(candidates[:9]): 
            col = cols[i % 3]
            with col:
                if st.button(f"{cand['san']}", key=f"move_{i}", use_container_width=True):
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback_data = {
                        "label": cand['label'], 
                        "color": cand['color'], 
                        "text": cand['explanation']
                    }
                    st.rerun()
                
                st.markdown(f"""
                <div style='text-align:center; font-size:12px; margin-top:-10px; margin-bottom:10px;'>
                    <span style='color:{cand['color']}; font-weight:bold;'>{cand['label'].split(' ')[1]}</span>
                </div>
                """, unsafe_allow_html=True)
