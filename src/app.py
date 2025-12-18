import streamlit as st
import chess
import chess.engine
import chess.svg
import chess.pgn
import io
import base64

# --- CONFIG ---
st.set_page_config(page_title="Deep Logic Chess - XAI Edition", layout="wide")
STOCKFISH_PATH = "/usr/games/stockfish"

# --- ML WEIGHTS FROM COLAB TRAINING ---
# These weights were learned from 20,000 beginner games (<1500 Elo)
# They represent the TRUE importance of each concept for beginner success
ML_WEIGHTS = {
    'check': 0.5792,      # Checks are CRITICAL for beginners (highest weight)
    'capture': 0.1724,    # Captures matter, but less than checks
    'center': 0.0365      # Center control barely matters at beginner level
}

# --- SESSION STATE (APP'S MEMORY) ---
if 'board' not in st.session_state:
    st.session_state.board = chess.Board()
if 'game_moves' not in st.session_state:
    st.session_state.game_moves = []
if 'move_index' not in st.session_state:
    st.session_state.move_index = 0
if 'last_best_eval' not in st.session_state:
    st.session_state.last_best_eval = 0.35
if 'feedback_data' not in st.session_state:
    st.session_state.feedback_data = None
if 'move_history' not in st.session_state:
    st.session_state.move_history = []

# --- HELPER: RENDER BOARD ---
def render_board(board, arrows=[]):
    """Convert chess board to displayable SVG image"""
    board_svg = chess.svg.board(
        board=board,
        size=550,
        arrows=arrows,
        lastmove=board.peek() if board.move_stack else None,
        colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
    )
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="100%" style="display:block; margin-bottom:10px;" />'

# --- ML-ENHANCED MOVE SCORING ---
def calculate_ml_bonus(board, move):
    """
    Apply ML insights to boost moves that matter for beginners.
    This is where Colab's intelligence gets applied!
    """
    bonus = 0.0
    
    # Check Bonus (Most Important for Beginners)
    if board.gives_check(move):
        bonus += ML_WEIGHTS['check']
    
    # Capture Bonus (Second Most Important)
    if board.is_capture(move):
        bonus += ML_WEIGHTS['capture']
    
    # Center Control Bonus (Least Important at This Level)
    if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
        bonus += ML_WEIGHTS['center']
    
    return bonus

# --- POSITIVE EXPLANATION ENGINE ---
def explain_good_move(board_before, move):
    """
    Generate human-readable explanation for WHY a move is good.
    Uses chess logic + natural language templates.
    """
    narrative = []
    board_after = board_before.copy()
    board_after.push(move)
    
    # 1. TACTICAL: Captures (Material Gain)
    if board_before.is_capture(move):
        victim = board_before.piece_at(move.to_square)
        if victim:
            piece_names = {
                chess.PAWN: "pawn",
                chess.KNIGHT: "knight",
                chess.BISHOP: "bishop",
                chess.ROOK: "rook",
                chess.QUEEN: "queen"
            }
            piece_name = piece_names.get(victim.piece_type, "piece")
            narrative.append(f"✓ Captures the {piece_name} (Material Gain)")
    
    # 2. TACTICAL: Checks (King Pressure)
    if board_before.gives_check(move):
        narrative.append("✓ Checks the enemy king (Forces opponent's response)")
    
    # 3. DEFENSIVE: Escaping Threats
    was_attacked = board_before.is_attacked_by(
        not board_before.turn, 
        move.from_square
    )
    if was_attacked:
        narrative.append("✓ Escapes a threat (Saves the piece)")
    
    # 4. TACTICAL: Creating Threats
    new_threats = []
    for sq in board_after.attacks(move.to_square):
        target = board_after.piece_at(sq)
        if target and target.color != board_before.turn:
            if target.piece_type == chess.QUEEN:
                new_threats.append("Queen")
            elif target.piece_type == chess.ROOK:
                new_threats.append("Rook")
    if new_threats:
        narrative.append(f"✓ Attacks the {new_threats[0]}!")
    
    # 5. STRATEGIC: Opening/Development
    if not narrative and board_before.fullmove_number < 12:
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            narrative.append("✓ Fights for the center")
        elif board_before.is_castling(move):
            narrative.append("✓ Castles for king safety")
        elif board_before.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]:
            narrative.append("✓ Develops a piece to an active square")
    
    # 6. FALLBACK: Generic Positive
    if not narrative:
        if board_before.piece_type_at(move.from_square) == chess.PAWN:
            narrative.append("✓ Improves pawn structure and takes space")
        else:
            narrative.append("✓ Solid positional improvement")
    
    return " ".join(narrative)

# --- NEGATIVE EXPLANATION ENGINE ---
def explain_bad_move(board_before, played_move, best_move, eval_drop):
    """
    Generate human-readable criticism for WHY a move is bad.
    Uses evaluation drop + missed opportunities.
    """
    
    # 1. CRITICAL: Did we miss a forced checkmate?
    board_temp = board_before.copy()
    board_temp.push(best_move)
    if board_temp.is_checkmate():
        return "✗ CRITICAL: Missed a forced checkmate sequence!"
    
    # 2. SEVERE: Did we miss a free capture?
    if board_before.is_capture(best_move) and not board_before.is_capture(played_move):
        victim = board_before.piece_at(best_move.to_square)
        if victim:
            piece_names = {
                chess.PAWN: "pawn",
                chess.KNIGHT: "knight",
                chess.BISHOP: "bishop",
                chess.ROOK: "rook",
                chess.QUEEN: "queen"
            }
            piece_name = piece_names.get(victim.piece_type, "piece")
            return f"✗ Missed a free {piece_name} capture (Material Loss)"
    
    # 3. EVALUATION-BASED FEEDBACK
    if eval_drop > 2.5:
        # Check if we hung a piece
        board_after = board_before.copy()
        board_after.push(played_move)
        moved_piece_square = played_move.to_square
        
        if board_after.is_attacked_by(not board_before.turn, moved_piece_square):
            defenders = len(list(board_after.attackers(board_before.turn, moved_piece_square)))
            attackers = len(list(board_after.attackers(not board_before.turn, moved_piece_square)))
            if attackers > defenders:
                return "✗ BLUNDER: Hung a piece (Undefended piece left under attack)"
        
        return "✗ Severe tactical error (Large evaluation swing against you)"
    
    elif eval_drop > 1.0:
        return "✗ Allows opponent a strong tactical blow (Missed better defense)"
    
    else:
        # Passive/Strategic error
        if board_before.gives_check(best_move) and not board_before.gives_check(played_move):
            return "✗ Passive play: Missed an opportunity to pressure the king"
        else:
            return "✗ Inaccurate: Allows opponent to improve position"

# --- CORE ANALYSIS ENGINE ---
def get_analysis(board, engine_path):
    """
    Combines Stockfish's raw calculation with ML-enhanced scoring.
    This is where the 'Deep Logic' happens!
    """
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except Exception as e:
        st.error(f"Stockfish engine error: {e}")
        return None, []
    
    # Get Stockfish's top 9 move suggestions
    info = engine.analyse(board, chess.engine.Limit(time=0.4), multipv=9)
    candidates = []
    
    for line in info:
        move = line["pv"][0]
        
        # Get base Stockfish evaluation
        stockfish_score = line["score"].relative.score(mate_score=10000)
        if stockfish_score is None:
            stockfish_score = 0
        base_eval = stockfish_score / 100
        
        # Apply ML bonus (This is the key innovation!)
        ml_bonus = calculate_ml_bonus(board, move)
        adjusted_eval = base_eval + ml_bonus
        
        # Generate natural language explanation
        candidates.append({
            "move": move,
            "san": board.san(move),
            "base_eval": base_eval,
            "ml_bonus": ml_bonus,
            "eval": adjusted_eval,  # Final score after ML adjustment
            "pv": line["pv"][:5],
            "explanation": explain_good_move(board, move)
        })
    
    # Re-sort candidates by ML-adjusted evaluation
    candidates.sort(key=lambda x: x["eval"], reverse=True)
    
    engine.quit()
    return candidates[0] if candidates else None, candidates

# --- MOVE JUDGMENT SYSTEM ---
def judge_move(current_eval, best_eval, board_before, played_move, best_move_obj):
    """
    Determines move quality and generates feedback.
    Uses evaluation drop thresholds calibrated for beginners.
    """
    # Calculate how much worse the played move is vs. best move
    eval_drop = best_eval - (-current_eval)  # Note: flip current eval for opponent's perspective
    
    # Thresholds calibrated for beginner play
    if eval_drop <= 0.2:
        label, color = "✅ Excellent", "green"
        text = explain_good_move(board_before, played_move)
    
    elif eval_drop <= 0.5:
        label, color = "🆗 Good", "blue"
        text = explain_good_move(board_before, played_move)
    
    elif eval_drop <= 1.0:
        label, color = "⚠️ Inaccuracy", "orange"
        text = explain_bad_move(board_before, played_move, best_move_obj, eval_drop)
    
    elif eval_drop <= 2.5:
        label, color = "❌ Mistake", "#FF5722"
        text = explain_bad_move(board_before, played_move, best_move_obj, eval_drop)
    
    else:
        label, color = "😱 Blunder", "red"
        text = explain_bad_move(board_before, played_move, best_move_obj, eval_drop)
    
    return {
        "label": label,
        "color": color,
        "text": text,
        "eval_drop": eval_drop
    }

# ========================================
# UI START
# ========================================

st.title("♟️ Deep Logic Chess - XAI Edition")
st.caption("AI Chess Tutor powered by Machine Learning insights from 20,000 beginner games")

# --- SIDEBAR: GAME LOADER ---
with st.sidebar:
    st.header("📥 Load Game")
    
    # Display ML Weights Info
    with st.expander("🧠 ML Insights (from Colab)"):
        st.write("**Importance for Beginners:**")
        st.metric("Checks", f"{ML_WEIGHTS['check']:.4f}", help="Highest priority")
        st.metric("Captures", f"{ML_WEIGHTS['capture']:.4f}", help="Medium priority")
        st.metric("Center Control", f"{ML_WEIGHTS['center']:.4f}", help="Low priority")
        st.caption("These weights were learned from 20,000 games of players rated <1500 Elo")
    
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
                st.session_state.move_history = []
                st.session_state.last_best_eval = 0.35
                st.success(f"✅ Loaded {len(st.session_state.game_moves)} moves")
                st.rerun()
            except Exception as e:
                st.error(f"Invalid PGN: {e}")
    
    if st.button("🗑️ Clear Board"):
        st.session_state.board.reset()
        st.session_state.game_moves = []
        st.session_state.move_index = 0
        st.session_state.feedback_data = None
        st.session_state.move_history = []
        st.rerun()
    
    # Move History Display
    if st.session_state.move_history:
        st.divider()
        st.subheader("📜 Move History")
        for i, entry in enumerate(st.session_state.move_history[-10:], 1):  # Last 10 moves
            color = entry['feedback']['color']
            label = entry['feedback']['label']
            st.markdown(
                f"**{i}.** {entry['san']} - "
                f"<span style='color:{color}'>{label}</span>",
                unsafe_allow_html=True
            )

# --- LAYOUT ---
col_main, col_info = st.columns([1.5, 1.2])

# --- AUTO-ANALYSIS (Runs on every board state change) ---
with st.spinner("Analyzing position..."):
    best_plan, candidates = get_analysis(st.session_state.board, STOCKFISH_PATH)

# Prepare arrow for best move suggestion
arrows = []
if best_plan:
    m1 = best_plan['move']
    arrows.append(chess.svg.Arrow(m1.from_square, m1.to_square, color="#4CAF50"))

# ========================================
# LEFT COLUMN: BOARD & CONTROLS
# ========================================
with col_main:
    # 1. BOARD DISPLAY
    st.markdown(render_board(st.session_state.board, arrows), unsafe_allow_html=True)
    
    # 2. NAVIGATION BUTTONS
    if st.session_state.game_moves:
        c1, c2, c3 = st.columns([0.8, 2, 0.8])
        
        # Check if current board matches game sequence
        game_board_at_index = chess.Board()
        for i in range(st.session_state.move_index):
            game_board_at_index.push(st.session_state.game_moves[i])
        on_track = (game_board_at_index.fen() == st.session_state.board.fen())
        
        # UNDO BUTTON
        with c1:
            if st.button("◀ Undo", use_container_width=True):
                if st.session_state.board.move_stack:
                    st.session_state.board.pop()
                    if on_track and st.session_state.move_index > 0:
                        st.session_state.move_index -= 1
                    
                    # Remove last move from history
                    if st.session_state.move_history:
                        st.session_state.move_history.pop()
                    
                    # Auto-fix index if needed
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
        
        # PROGRESS INDICATOR
        with c2:
            progress = st.session_state.move_index / len(st.session_state.game_moves)
            st.progress(progress)
            st.caption(f"Move {st.session_state.move_index} / {len(st.session_state.game_moves)}")
        
        # NEXT/SYNC BUTTON
        with c3:
            if on_track:
                if st.button("Next ▶", use_container_width=True) and \
                   st.session_state.move_index < len(st.session_state.game_moves):
                    
                    # Store board state before move
                    board_before = st.session_state.board.copy()
                    expected_eval = best_plan['eval'] if best_plan else 0
                    best_move_obj = best_plan['move'] if best_plan else None
                    
                    # Execute move
                    move = st.session_state.game_moves[st.session_state.move_index]
                    move_san = board_before.san(move)
                    st.session_state.board.push(move)
                    st.session_state.move_index += 1
                    
                    # Analyze resulting position
                    new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                    curr_eval = new_best['eval'] if new_best else 0
                    
                    # Judge move quality
                    feedback = judge_move(
                        curr_eval,
                        expected_eval,
                        board_before,
                        move,
                        best_move_obj
                    )
                    st.session_state.feedback_data = feedback
                    
                    # Add to move history
                    st.session_state.move_history.append({
                        'san': move_san,
                        'feedback': feedback
                    })
                    
                    st.rerun()
            else:
                if st.button("Sync ⏩", use_container_width=True):
                    st.session_state.board = game_board_at_index
                    if st.session_state.move_index < len(st.session_state.game_moves):
                        move = st.session_state.game_moves[st.session_state.move_index]
                        move_san = st.session_state.board.san(move)
                        
                        # Recalculate expectation
                        resume_best, _ = get_analysis(game_board_at_index, STOCKFISH_PATH)
                        exp_eval = resume_best['eval'] if resume_best else 0
                        best_mv = resume_best['move'] if resume_best else None
                        
                        board_before = st.session_state.board.copy()
                        st.session_state.board.push(move)
                        st.session_state.move_index += 1
                        
                        new_best, _ = get_analysis(st.session_state.board, STOCKFISH_PATH)
                        curr_eval = new_best['eval'] if new_best else 0
                        
                        feedback = judge_move(
                            curr_eval,
                            exp_eval,
                            board_before,
                            move,
                            best_mv
                        )
                        st.session_state.feedback_data = feedback
                        
                        st.session_state.move_history.append({
                            'san': move_san,
                            'feedback': feedback
                        })
                    st.rerun()
    else:
        if st.button("◀ Undo Last", use_container_width=True):
            if st.session_state.board.move_stack:
                st.session_state.board.pop()
                st.session_state.feedback_data = None
                if st.session_state.move_history:
                    st.session_state.move_history.pop()
                st.rerun()

# ========================================
# RIGHT COLUMN: FEEDBACK & ANALYSIS
# ========================================
with col_info:
    # 1. FEEDBACK BANNER
    if st.session_state.feedback_data:
        data = st.session_state.feedback_data
        st.markdown(f"""
        <div style="background-color: {data['color']}; color: white; padding: 15px; 
                    border-radius: 8px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 style="margin:0; text-align: center;">{data['label']}</h3>
            <p style="margin:8px 0 0 0; text-align: center; font-size: 15px;">
                {data['text']}
            </p>
            <p style="margin:8px 0 0 0; text-align: center; font-size: 12px; opacity: 0.9;">
                Eval drop: {data.get('eval_drop', 0):.2f} pawns
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background-color: #f0f2f6; color: #333; padding: 15px; 
                    border-radius: 8px; margin-bottom: 15px; text-align: center;">
            <p style="margin:0; font-size: 14px;">
                📝 Make a move to see AI feedback
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # 2. ENGINE SUGGESTION (ML-Enhanced)
    st.subheader("💡 AI Recommendation")
    if best_plan:
        col_eval, col_move = st.columns([1, 2])
        
        with col_eval:
            # Show both base Stockfish eval and ML-adjusted eval
            st.metric(
                "Base Eval",
                f"{best_plan['base_eval']:+.2f}",
                help="Raw Stockfish evaluation"
            )
            if best_plan['ml_bonus'] > 0:
                st.metric(
                    "ML Bonus",
                    f"+{best_plan['ml_bonus']:.2f}",
                    help="Bonus from beginner-friendly factors"
                )
        
        with col_move:
            st.success(f"**Best:** {best_plan['san']}")
            st.caption(f"Final Score: {best_plan['eval']:+.2f}")
        
        st.markdown(f"**Why this move?** {best_plan['explanation']}")
        st.caption(f"📊 Continuation: {st.session_state.board.variation_san(best_plan['pv'])}")
    else:
        st.warning("Analysis unavailable")
    
    st.divider()
    
    # 3. ALTERNATIVE MOVES
    st.subheader("🔍 Explore Alternatives")
    if candidates:
        # Top 3 moves (Best tier)
        st.caption("**Top Choices:**")
        cols1 = st.columns(3)
        for i, cand in enumerate(candidates[:3]):
            with cols1[i]:
                button_label = f"{cand['san']}"
                if cand['ml_bonus'] > 0:
                    button_label += " 🌟"  # Star for ML-boosted moves
                
                if st.button(button_label, key=f"top_{i}", use_container_width=True):
                    st.session_state.board.push(cand['move'])
                    st.session_state.feedback_data = {
                        "label": "✅ Best Move" if i == 0 else "🆗 Good Alternative",
                        "color": "green" if i == 0 else "blue",
                        "text": cand['explanation'],
                        "eval_drop": 0.0
                    }
                    st.rerun()
                
                # Show evaluation with ML bonus indicator
                eval_display = f"{cand['eval']:+.2f}"
                if cand['ml_bonus'] > 0:
                    eval_display += f" (+{cand['ml_bonus']:.2f})"
                st.markdown(
                    f"<div style='text-align:center; font-size:11px; color:gray; margin-top:-8px;'>"
                    f"{eval_display}</div>",
                    unsafe_allow_html=True
                )
        
        # Middle 3 moves (Playable tier)
        if len(candidates) > 3:
            st.caption("**Playable Options:**")
            cols2 = st.columns(3)
            for i, cand in enumerate(candidates[3:6]):
                idx = i + 3
                with cols2[i]:
                    if st.button(f"{cand['san']}", key=f"mid_{idx}", use_container_width=True):
                        st.session_state.board.push(cand['move'])
                        st.session_state.feedback_data = {
                            "label": "🆗 Playable",
                            "color": "blue",
                            "text": cand['explanation'],
                            "eval_drop": 0.0
                        }
                        st.rerun()
                    st.markdown(
                        f"<div style='text-align:center; font-size:11px; color:gray; margin-top:-8px;'>"
                        f"{cand['eval']:+.2f}</div>",
                        unsafe_allow_html=True
                    )
        
        # Bottom 3 moves (Risky tier)
        if len(candidates) > 6:
            st.caption("**Risky Moves:**")
            cols3 = st.columns(3)
            for i, cand in enumerate(candidates[6:9]):
                idx = i + 6
                with cols3[i]:
                    if st.button(f"{cand['san']}", key=f"low_{idx}", use_container_width=True):
                        st.session_state.board.push(cand['move'])
                        st.session_state.feedback_data = {
                            "label": "⚠️ Risky",
                            "color": "orange",
                            "text": cand['explanation'],
                            "eval_drop": 0.0
                        }
                        st.rerun()
                    st.markdown(
                        f"<div style='text-align:center; font-size:11px; color:gray; margin-top:-8px;'>"
                        f"{cand['eval']:+.2f}</div>",
                        unsafe_allow_html=True
                    )

# --- FOOTER ---
st.divider()
st.caption("""
**🎓 About Deep Logic Chess:**  
This AI uses machine learning insights from 20,000 beginner games to provide explanations that match how humans actually think.  
Unlike traditional engines that prioritize perfect play, this tutor focuses on what matters most at your level.
""")
