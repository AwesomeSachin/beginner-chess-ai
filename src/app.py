import streamlit as st
import chess
import chess.engine
import chess.svg
import chess.pgn
import io
import base64

# --- CONFIG ---
st.set_page_config(page_title="Deep Logic Chess (ML Edition)", layout="wide")
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

# --- LOGIC: POSITIVE EXPLANATION (For Good Moves) ---
def explain_good_move(board_before, move):
    """Explains WHY a good move is good."""
    board_after = board_before.copy()
    board_after.push(move)
    
    # 1. TACTICS - Captures
    if board_before.is_capture(move):
        victim = board_before.piece_at(move.to_square)
        if victim:
            return f"Captures the {chess.piece_name(victim.piece_type)} (Material Gain)."
        else:
            return "Recaptures material."
    
    # 2. DEFENSE - Escaping threats
    if board_before.is_attacked_by(not board_before.turn, move.from_square):
        return "Escapes a threat."
    
    # 3. THREATS - Creating attacks
    for sq in board_after.attacks(move.to_square):
        target = board_after.piece_at(sq)
        if target and target.color != board_before.turn:
            if target.piece_type == chess.QUEEN:
                return "Attacks the Queen!"
            elif target.piece_type == chess.ROOK:
                return "Attacks the Rook!"
    
    # 4. STRATEGY - Opening principles
    if board_before.fullmove_number < 12:
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            return "Fights for the center."
        elif board_before.is_castling(move):
            return "Castles for King safety."
        elif board_before.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]:
            return "Develops a piece to an active square."
    
    # Pawn structure
    if board_before.piece_type_at(move.from_square) == chess.PAWN:
        return "Improves pawn structure and takes space."
    
    return "A solid positional improvement."

# --- LOGIC: NEGATIVE EXPLANATION (For Bad Moves) ---
def explain_bad_move(board_before, played_move, best_move):
    """Explains WHAT WAS MISSED when a bad move is played."""
    
    # 1. Missed capture
    if board_before.is_capture(best_move) and not board_before.is_capture(played_move):
        victim = board_before.piece_at(best_move.to_square)
        if victim:
            return f"Missed capturing the {chess.piece_name(victim.piece_type)} (Material Loss)."
        return "Missed a tactical capture opportunity."
    
    # 2. Missed checkmate
    board_temp = board_before.copy()
    board_temp.push(best_move)
    if board_temp.is_checkmate():
        return "Missed a forced checkmate sequence!"
    
    # 3. Missed check
    if board_before.gives_check(best_move) and not board_before.gives_check(played_move):
        return "Missed a powerful checking move."
    
    # 4. Passive play
    return "Passive play. Allows the opponent to take the initiative."

# --- LOGIC: ML-WEIGHTED ANALYSIS ---
def get_analysis(board, engine_path):
    """Analyzes position using Stockfish + ML weights for beginner-friendly scoring."""
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return None, []
    
    # Get top 9 moves from Stockfish
    info = engine.analyse(board, chess.engine.Limit(time=0.4), multipv=9)
    candidates = []
    
    # ML WEIGHTS (from training on beginner games)
    w_check = 0.5792    # Checks are very important for beginners
    w_capture = 0.1724  # Captures are moderately important
    w_center = 0.0365   # Center control is less critical
    
    for line in info:
        move = line["pv"][0]
        score = line["score"].relative.score(mate_score=10000)
        if score is None: score = 0
        
        # Calculate beginner-friendly bonus
        bonus = 0
        
        # Check bonus
        if board.gives_check(move):
            bonus += w_check
        
        # Capture bonus
        if board.is_capture(move):
            bonus += w_capture
        
        # Center control bonus
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            bonus += w_center
        
        # COMBINED SCORE: Raw engine eval + ML beginner bonus
        final_score = (score / 100) + bonus
        
        candidates.append({
            "move": move,
            "san": board.san(move),
            "eval": final_score,
            "raw_eval": score / 100,
            "pv": line["pv"][:5],
            "explanation": explain_good_move(board, move)
        })
    
    engine.quit()
    
    # Sort by ML-weighted score (not just raw Stockfish eval)
    candidates.sort(key=lambda x: x['eval'], reverse=True)
    
    return candidates[0] if candidates else None, candidates

def judge_move(current_eval, best_eval, board_before, played_move, best_move_obj):
    """Judges the quality of a move and provides context-aware feedback."""
    diff = best_eval - current_eval
    
    # DECISION TREE FOR FEEDBACK
    if diff <= 0.2:
        label, color = "✅ Excellent", "green"
        text = explain_good_move(board_before, played_move)
    elif diff <= 0.7:
        label, color = "🆗 Good", "blue"
        text = explain_good_move(board_before, played_move)
    elif diff <= 1.5:
        label, color = "⚠️ Inaccuracy", "orange"
        text = explain_bad_move(board_before, played_move, best_move_obj)
    elif diff <= 3.0:
        label, color = "❌ Mistake", "#FF5722"
        text = explain_bad_move(board_before, played_move, best_move_obj)
    else:
        label, color = "😱 Blunder", "red"
        text = explain_bad_move(board_before, played_move, best_move_obj)
    
    return {"label": label, "color": color, "text": text}

# --- UI START ---
st.title("♟️ Deep Logic Chess (ML Edition)")

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
                    st.session_state.feedback_data = None
                    st.rerun()
        
        with c3:
            if on_track:
                if st.button("Next ▶", use_container_width=True) and st.session_state.move_index < len(st.session_state.game_moves):
                    board_before = st.session_state.board.copy()
                    expected_eval = best_plan['eval'] if best_plan else 0
                    best_move_obj = best_plan['move'] if best_plan else None
                    
                    move = st.session_state.game_moves[st.session_state.move_index]
                    st.session_state.board.push(move)
                    st.session_state.move_index += 1
                    
                    new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                    curr_eval = new_best['eval'] if new_best else 0
                    
                    st.session_state.feedback_data = judge_move(curr_eval, expected_eval, board_before, move, best_move_obj)
                    st.rerun()
            else:
                if st.button("Sync ⏩", use_container_width=True):
                    st.session_state.board = game_board_at_index
                    st.session_state.feedback_data = None
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
    st.subheader("💡 Engine Suggestion (ML-Weighted)")
    if best_plan:
        c_eval, c_move = st.columns([1, 2])
        c_eval.metric("Score", f"{best_plan['eval']:+.2f}")
        c_move.success(f"**Best:** {best_plan['san']}")
        
        st.markdown(f"**Reason:** {best_plan['explanation']}")
        st.caption(f"Line: {st.session_state.board.variation_san(best_plan['pv'])}")
        
        st.divider()
    
    # 3. ALTERNATIVE MOVES
    st.subheader("Explore Alternative Moves")
    if candidates:
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
        
        cols2 = st.columns(3)
        for i, cand in enumerate(candidates[3:6]):
            idx = i + 3
            with cols2[i]:
                if st.button(f"{cand['san']}", key=f"mid_{idx}", use_container_width=True):
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback_data = {"label": "🆗 Playable", "color": "blue", "text": cand['explanation']}
                    st.rerun()
                st.markdown(f"<div style='text-align:center; font-size:12px; color:gray; margin-top:-10px; margin-bottom:10px;'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)
        
        cols3 = st.columns(3)
        for i, cand in enumerate(candidates[6:9]):
            idx = i + 6
            with cols3[i]:
                if st.button(f"{cand['san']}", key=f"low_{idx}", use_container_width=True):
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback_data = {"label": "⚠️ Risky", "color": "orange", "text": cand['explanation']}
                    st.rerun()
                st.markdown(f"<div style='text-align:center; font-size:12px; color:gray; margin-top:-10px; margin-bottom:10px;'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)
