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

# --- LOGIC: EXPLANATION ENGINE ---
def get_move_concept(board, move):
    """Returns a short concept string for a specific move."""
    board_after = board.copy()
    board_after.push(move)
    
    if board.is_capture(move): return "Material Gain"
    if board_after.is_checkmate(): return "Checkmate"
    if board_after.is_check(): return "Attacking the King"
    
    # Opening Concepts
    if board.fullmove_number < 10:
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]: return "Center Control"
        if board.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]: return "Development"
        if board.is_castling(move): return "King Safety"
    
    # Threats
    for sq in board_after.attacks(move.to_square):
        target = board_after.piece_at(sq)
        if target and target.color != board.turn and target.piece_type == chess.QUEEN:
            return "Attacking the Queen"
            
    return "Positional Improvement"

def explain_move_context(board_before, move, is_best_move=True, opponent_reply=None):
    """
    Generates a narrative based on whether the move was Good or Bad.
    """
    # 1. IF IT WAS A BAD MOVE (Inaccuracy/Mistake)
    if not is_best_move:
        reasons = []
        if opponent_reply:
            reasons.append(f"This allows the opponent to play **{board_before.san(opponent_reply)}**.")
            
            # Check if opponent reply is dangerous
            board_after = board_before.copy()
            board_after.push(move)
            if board_after.is_capture(opponent_reply):
                reasons.append("You might lose material!")
            elif board_after.gives_check(opponent_reply):
                reasons.append("Exposes your King to check.")
            else:
                reasons.append("Gives away the advantage.")
        else:
            reasons.append("This is too passive compared to the best plan.")
            
        return " ".join(reasons)

    # 2. IF IT WAS A GOOD MOVE (Standard Explanation)
    narrative = []
    board_after = board_before.copy()
    board_after.push(move)
    
    if board_before.is_capture(move):
        victim = board_before.piece_at(move.to_square)
        name = chess.piece_name(victim.piece_type).capitalize() if victim else "piece"
        narrative.append(f"Captures the {name}.")
    
    elif board_after.is_check():
        narrative.append("Delivers a forcing check.")
        
    elif board_before.fullmove_number < 8 and move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
        narrative.append("Fighting for the center.")
        
    elif board_before.is_castling(move):
        narrative.append("Safety first!")
        
    else:
        narrative.append("Solid improvement.")
        
    return " ".join(narrative)

# --- LOGIC: ANALYSIS ---
def get_analysis(board, engine_path):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return None, []
    
    # Analyze Top 9 moves
    info = engine.analyse(board, chess.engine.Limit(time=0.4), multipv=9)
    candidates = []
    
    for line in info:
        move = line["pv"][0]
        score = line["score"].relative.score(mate_score=10000)
        if score is None: score = 0
        
        # We only generate the "Good" explanation here for the list
        candidates.append({
            "move": move,
            "san": board.san(move),
            "eval": score/100,
            "pv": line["pv"][:5],
            "concept": get_move_concept(board, move)
        })
    
    engine.quit()
    return candidates[0] if candidates else None, candidates

def judge_move(current_eval, best_eval, board_before, move, best_plan_move, best_plan_concept, opponent_reply):
    diff = best_eval - (-current_eval) # Flip perspective
    
    # Logic: If diff is high, it's bad.
    if diff <= 0.25:
        label, color = "✅ Excellent", "green"
        text = explain_move_context(board_before, move, is_best_move=True)
    elif diff <= 0.7:
        label, color = "🆗 Good", "blue"
        text = explain_move_context(board_before, move, is_best_move=True)
    else:
        # IT IS A MISTAKE
        if diff <= 1.5: label, color = "⚠️ Inaccuracy", "orange"
        elif diff <= 3.0: label, color = "❌ Mistake", "#FF5722"
        else: label, color = "😱 Blunder", "red"
        
        # Generate the "Why it's bad" text
        bad_reason = explain_move_context(board_before, move, is_best_move=False, opponent_reply=opponent_reply)
        
        # Combine: Why bad + What was better
        text = f"{bad_reason} <br><b>Better was:</b> {board_before.san(best_plan_move)} ({best_plan_concept})."

    return {"label": label, "color": color, "text": text}

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
with st.spinner("Analyzing..."):
    best_plan, candidates = get_analysis(st.session_state.board, STOCKFISH_PATH)

arrows = []
if best_plan:
    m1 = best_plan['move']
    arrows.append(chess.svg.Arrow(m1.from_square, m1.to_square, color="#4CAF50"))

# === LEFT: BOARD ===
with col_main:
    # 1. THE BOARD
    st.markdown(render_board(st.session_state.board, arrows), unsafe_allow_html=True)
    
    # 2. NAVIGATION
    if st.session_state.game_moves:
        c1, c2, c3 = st.columns([0.8, 2, 0.8])
        
        # Sync Logic
        game_board_at_index = chess.Board()
        for i in range(st.session_state.move_index):
            game_board_at_index.push(st.session_state.game_moves[i])
        on_track = (game_board_at_index.fen() == st.session_state.board.fen())

        with c3:
            if on_track:
                if st.button("Next Move ▶", use_container_width=True) and st.session_state.move_index < len(st.session_state.game_moves):
                    # Capture PRE-MOVE Data
                    board_before = st.session_state.board.copy()
                    # Store what the engine RECOMMENDED (The "Best Move")
                    optimal_move = best_plan['move'] if best_plan else None
                    optimal_concept = best_plan['concept'] if best_plan else "Improvement"
                    expected_eval = best_plan['eval'] if best_plan else 0
                    
                    # Make the ACTUAL move
                    move = st.session_state.game_moves[st.session_state.move_index]
                    st.session_state.board.push(move)
                    st.session_state.move_index += 1
                    
                    # Analyze POST-MOVE to see the consequences
                    new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                    current_eval = new_best['eval'] if new_best else 0
                    
                    # What is the opponent's best reply now?
                    opponent_reply = new_best['move'] if new_best else None
                    
                    # Judge
                    st.session_state.feedback_data = judge_move(
                        current_eval, expected_eval, board_before, move, 
                        optimal_move, optimal_concept, opponent_reply
                    )
                    st.rerun()
            else:
                if st.button("Sync ⏩", use_container_width=True):
                    # Resume
                    st.session_state.board = game_board_at_index
                    if st.session_state.move_index < len(st.session_state.game_moves):
                        move = st.session_state.game_moves[st.session_state.move_index]
                        
                        # Recalculate context for sync
                        resume_best, _ = get_analysis(game_board_at_index, STOCKFISH_PATH)
                        opt_move = resume_best['move']
                        opt_con = resume_best['concept']
                        exp_eval = resume_best['eval']
                        
                        st.session_state.board.push(move)
                        st.session_state.move_index += 1
                        
                        new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                        curr_eval = new_best['eval'] if new_best else 0
                        op_reply = new_best['move'] if new_best else None

                        st.session_state.feedback_data = judge_move(
                            curr_eval, exp_eval, game_board_at_index, move, 
                            opt_move, opt_con, op_reply
                        )
                    st.rerun()

        with c1:
             if st.button("◀ Undo", use_container_width=True):
                if st.session_state.board.move_stack:
                    st.session_state.board.pop()
                    if on_track and st.session_state.move_index > 0: 
                        st.session_state.move_index -= 1
                    
                    # Auto-Fix Index Logic
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
        <div style="background-color: {data['color']}; color: white; padding: 12px; border-radius: 6px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h4 style="margin:0; text-align: center;">{data['label']}</h4>
            <div style="margin-top:8px; text-align: center; font-size: 14px; line-height: 1.4;">
                {data['text']}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background-color: #f0f2f6; color: #333; padding: 12px; border-radius: 6px; margin-bottom: 10px; text-align: center;">
            <p style="margin:0; font-size: 14px;">Make a move to see feedback.</p>
        </div>
        """, unsafe_allow_html=True)

    # 2. ENGINE SUGGESTION
    st.subheader("💡 Best Plan")
    if best_plan:
        c_eval, c_move = st.columns([1, 2])
        c_eval.metric("Eval", f"{best_plan['eval']:+.2f}")
        c_move.success(f"**{best_plan['san']}** ({best_plan['concept']})")
        st.caption(f"Continuation: {st.session_state.board.variation_san(best_plan['pv'])}")
    
    st.divider()

    # 3. PLAYABLE MOVES GRID
    st.subheader("Alternatives")
    if candidates:
        cols1 = st.columns(3)
        for i, cand in enumerate(candidates[:3]):
            with cols1[i]:
                if st.button(f"{cand['san']}", key=f"top_{i}", use_container_width=True):
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback_data = {
                        "label": "✅ Best Move" if i==0 else "🆗 Good Alt",
                        "color": "green" if i==0 else "blue",
                        "text": f"Correct! {cand['concept']}."
                    }
                    st.rerun()
                st.markdown(f"<div style='text-align:center; font-size:12px; color:gray; margin-top:-10px; margin-bottom:10px;'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)

        cols2 = st.columns(3)
        for i, cand in enumerate(candidates[3:6]):
            idx = i + 3
            with cols2[i]:
                if st.button(f"{cand['san']}", key=f"mid_{idx}", use_container_width=True):
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback_data = {"label": "🆗 Playable", "color": "blue", "text": f"Reasonable. {cand['concept']}."}
                    st.rerun()
                st.markdown(f"<div style='text-align:center; font-size:12px; color:gray; margin-top:-10px; margin-bottom:10px;'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)
                
        cols3 = st.columns(3)
        for i, cand in enumerate(candidates[6:9]):
            idx = i + 6
            with cols3[i]:
                if st.button(f"{cand['san']}", key=f"low_{idx}", use_container_width=True):
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback_data = {"label": "⚠️ Risky", "color": "orange", "text": "This might be passive or inaccurate."}
                    st.rerun()
                st.markdown(f"<div style='text-align:center; font-size:12px; color:gray; margin-top:-10px; margin-bottom:10px;'>{cand['eval']:+.2f}</div>", unsafe_allow_html=True)
