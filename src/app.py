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

# --- HELPER: FORMAT MOVE SEQUENCE ---
def format_line(board, move_list):
    """Converts a list of move objects into a readable SAN string (e.g. 1. e4 e5 2. Nf3)"""
    board_temp = board.copy()
    san_list = []
    for move in move_list:
        san = board_temp.san(move)
        san_list.append(san)
        board_temp.push(move)
    return " ➤ ".join(san_list)

# --- LOGIC: EXPLAINER ENGINE ---
def get_deep_feedback(board_before, played_move, best_move_obj, best_line, engine):
    """
    Generates feedback by comparing the PLAYED line vs the BEST line.
    Returns dictionaries with 'text' and 'line' for display.
    """
    board_after = board_before.copy()
    board_after.push(played_move)
    
    # 1. ANALYZE THE MOVE PLAYED (To see the Refutation)
    # We ask engine: "What is the best reply for the opponent now?"
    info_played = engine.analyse(board_after, chess.engine.Limit(time=0.4))
    score_played = info_played["score"].relative.score(mate_score=10000) or 0
    
    # Get the refutation line (Opponent's best response sequence)
    refutation_moves = info_played.get("pv", [])[:4] # Top 4 moves of punishment
    refutation_text = format_line(board_after, refutation_moves)

    # 2. ANALYZE THE BEST MOVE (What we missed)
    # We already passed this in as `best_line`
    missed_text = format_line(board_before, best_line[:4])
    
    # 3. COMPARE SCORES TO JUDGE
    # Re-calculate best score for comparison
    board_best = board_before.copy()
    if best_move_obj:
        board_best.push(best_move_obj)
        info_best = engine.analyse(board_best, chess.engine.Limit(time=0.1)) # Quick check
        best_score = info_best["score"].relative.score(mate_score=10000) or 0
    else:
        best_score = 0
        
    diff = (best_score - score_played) / 100
    
    # 4. GENERATE CONTENT
    if diff <= 0.2:
        return {
            "label": "✅ Excellent", 
            "color": "green", 
            "main_text": "Perfect play! You found the best continuation.",
            "refutation": None,
            "better_line": None
        }
    elif diff <= 0.6:
        return {
            "label": "🆗 Good", 
            "color": "blue", 
            "main_text": "Solid move. Maintains the position.",
            "refutation": None,
            "better_line": None
        }
    elif diff <= 1.5:
        return {
            "label": "⚠️ Inaccuracy", 
            "color": "orange", 
            "main_text": "Passive play. You gave the opponent a slight advantage.",
            "refutation": f"Opponent can now play: **{refutation_text}**",
            "better_line": f"Better plan was: **{missed_text}**"
        }
    else:
        return {
            "label": "❌ Mistake / Blunder", 
            "color": "red", 
            "main_text": "Critical Error. You missed a tactical threat.",
            "refutation": f"Opponent punishes with: **{refutation_text}**",
            "better_line": f"You should have played: **{missed_text}**"
        }

# --- LOGIC: NEXT MOVE SUGGESTION ---
def get_suggestions(board, engine_path):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return []
    
    # Get Top 3 Lines
    info = engine.analyse(board, chess.engine.Limit(time=0.5), multipv=3)
    suggestions = []
    
    for line in info:
        move = line["pv"][0]
        score = line["score"].relative.score(mate_score=10000)
        
        # Create the full sequence string
        sequence = format_line(board, line["pv"][:5])
        
        # Generate a brief reason based on the FIRST move only
        # (Keeping it simple for the reason text, but showing full line)
        reason = "Improves position."
        if board.is_capture(move): reason = "Wins material or trades."
        if board.is_check(): reason = "Forces the King to move."
        
        suggestions.append({
            "move": move,
            "san": board.san(move),
            "score": score/100 if score else 0,
            "sequence": sequence,
            "reason": reason
        })
        
    engine.quit()
    return suggestions

# --- UI START ---
st.title("♟️ Deep Logic Chess (Sequence Edition)")

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

# AUTO-ANALYSIS (Get Suggestions for Current Board)
with st.spinner("Calculating lines..."):
    suggestions = get_suggestions(st.session_state.board, STOCKFISH_PATH)

arrows = []
if suggestions:
    best_move = suggestions[0]['move']
    arrows.append(chess.svg.Arrow(best_move.from_square, best_move.to_square, color="#4CAF50"))

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
                    
                    # RUN ANALYSIS FOR FEEDBACK
                    # We need to know what the BEST line was before we moved
                    # (We use the 'suggestions' variable we calculated at the top of the script)
                    if suggestions:
                        best_move_obj = suggestions[0]['move']
                        # We need the full pv line object, which isn't stored in simple dict
                        # So we do a quick re-fetch or pass it. 
                        # To be precise, let's spin up a quick engine check for the 'Best Line' object
                        temp_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
                        best_info = temp_engine.analyse(board_before, chess.engine.Limit(time=0.1))
                        best_line = best_info.get("pv", [])
                        
                        # GENERATE FEEDBACK
                        fb = get_deep_feedback(board_before, move, best_move_obj, best_line, temp_engine)
                        st.session_state.feedback_data = fb
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
    
    # 1. FEEDBACK BANNER (THE NEW DESIGN)
    if st.session_state.feedback_data:
        data = st.session_state.feedback_data
        
        # Color Logic
        bg_color = "#f0f2f6"
        if data['color'] == "green": bg_color = "#d4edda"
        if data['color'] == "orange": bg_color = "#fff3cd"
        if data['color'] == "red": bg_color = "#f8d7da"
        
        st.markdown(f"""
        <div style="background-color: {bg_color}; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid {data['color']};">
            <h3 style="margin:0; color: #333;">{data['label']}</h3>
            <p style="font-size: 16px; margin-bottom: 0;">{data['main_text']}</p>
        </div>
        """, unsafe_allow_html=True)

        # SHOW SEQUENCES IF BAD
        if data['refutation']:
            st.warning("🔻 Why it's bad (Opponent's Threat):")
            st.markdown(f"_{data['refutation']}_")
            
        if data['better_line']:
            st.success("💡 What you should have played:")
            st.markdown(f"_{data['better_line']}_")

    else:
        st.info("Make a move to see the deep analysis.")

    st.divider()

    # 2. SUGGESTIONS (Top 3 Lines)
    st.subheader("🔮 Engine Suggestions")
    
    if suggestions:
        for i, line in enumerate(suggestions):
            with st.expander(f"{i+1}. **{line['san']}** ({line['score']:+.2f})", expanded=(i==0)):
                st.write(f"**Continuation:** {line['sequence']}")
                st.caption(f"Reason: {line['reason']}")
                if st.button(f"Play {line['san']}", key=f"sugg_{i}"):
                    st.session_state.board.push(line['move'])
                    st.session_state.feedback_data = None # Reset feedback since it's an engine move
                    st.rerun()
