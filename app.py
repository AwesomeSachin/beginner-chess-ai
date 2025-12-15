import streamlit as st
import chess
import chess.engine
import chess.svg
import chess.pgn
import io
import base64

# --- CONFIG ---
st.set_page_config(page_title="Grandmaster Dashboard", layout="wide")
STOCKFISH_PATH = "/usr/games/stockfish"

# --- SESSION STATE ---
if 'board' not in st.session_state: st.session_state.board = chess.Board()
if 'game_moves' not in st.session_state: st.session_state.game_moves = []
if 'move_index' not in st.session_state: st.session_state.move_index = 0
if 'arrows' not in st.session_state: st.session_state.arrows = []
if 'last_eval' not in st.session_state: st.session_state.last_eval = 0.0

# --- HELPER: RENDER BOARD ---
def render_board(board, arrows=[]):
    """Renders board with arrows."""
    board_svg = chess.svg.board(
        board=board, 
        size=500,
        arrows=arrows,
        lastmove=board.peek() if board.move_stack else None,
        colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
    )
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="100%" />'

# --- LOGIC: BEGINNER ENGINE ---
def get_beginner_analysis(board, engine_path):
    """Returns Top Moves + Classification of the board state."""
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return []

    # Analysis
    info = engine.analyse(board, chess.engine.Limit(time=0.5), multipv=5)
    candidates = []
    
    for line in info:
        move = line["pv"][0]
        # Raw Stockfish Score
        score = line["score"].relative.score(mate_score=10000)
        if score is None: score = 0
        
        # Beginner Heuristic Bonus
        bonus = 0
        board.push(move)
        if board.is_check(): bonus += 1.5
        if board.is_capture(move): bonus += 1.0
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]: bonus += 0.5
        board.pop()
        
        # Final "Beginner Score"
        final_score = (score/100) + bonus
        
        candidates.append({
            "move": move,
            "san": board.san(move),
            "score": final_score,
            "eval": score/100,
            "pv": line["pv"][:5] # 5-move plan
        })
    
    engine.quit()
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates

# --- UI LAYOUT ---
st.title("♟️ Grandmaster Analysis Dashboard")

# 1. SIDEBAR (PGN LOAD)
with st.sidebar:
    st.header("📂 Load Game")
    pgn_input = st.text_area("Paste PGN (Optional):", height=150)
    if st.button("Load PGN"):
        if pgn_input:
            try:
                pgn_io = io.StringIO(pgn_input)
                game = chess.pgn.read_game(pgn_io)
                st.session_state.game_moves = list(game.mainline_moves())
                st.session_state.board = game.board() # Start at move 0
                st.session_state.move_index = 0
                st.session_state.arrows = []
                st.success("Game Loaded! Use 'Next' to replay.")
                st.rerun()
            except:
                st.error("Invalid PGN")
    
    st.divider()
    st.write("Controls")
    if st.button("🔄 Reset Board"):
        st.session_state.board.reset()
        st.session_state.game_moves = []
        st.session_state.move_index = 0
        st.session_state.arrows = []
        st.rerun()

# 2. MAIN LAYOUT
col_board, col_analysis = st.columns([1.5, 1])

with col_board:
    # --- RENDER BOARD ---
    st.markdown(render_board(st.session_state.board, st.session_state.arrows), unsafe_allow_html=True)
    
    # --- NAVIGATION (If PGN loaded) ---
    if st.session_state.game_moves:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("◀ Prev") and st.session_state.move_index > 0:
                st.session_state.board.pop()
                st.session_state.move_index -= 1
                st.rerun()
        with c3:
            if st.button("Next ▶") and st.session_state.move_index < len(st.session_state.game_moves):
                move = st.session_state.game_moves[st.session_state.move_index]
                st.session_state.board.push(move)
                st.session_state.move_index += 1
                st.rerun()
        st.caption(f"Move {st.session_state.move_index} / {len(st.session_state.game_moves)}")

    # --- UNDO (Always available) ---
    if st.button("Undoing Last Move (Free Play)"):
        if st.session_state.board.move_stack:
            st.session_state.board.pop()
            # If we were in PGN mode, sync the index
            if st.session_state.move_index > 0: st.session_state.move_index -= 1
            st.rerun()

with col_analysis:
    st.header("🧠 AI Analysis")
    
    # 1. RUN ANALYSIS
    with st.spinner("Analyzing..."):
        candidates = get_beginner_analysis(st.session_state.board, STOCKFISH_PATH)
    
    if candidates:
        top_move = candidates[0]
        current_eval = top_move['eval']
        
        # 2. CLASSIFICATION (Did we just make a blunder?)
        # We compare current board eval vs previous state
        eval_diff = current_eval - st.session_state.last_eval
        # Flip perspective if black to move
        if st.session_state.board.turn == chess.BLACK: eval_diff = -eval_diff
        
        # Display Current Eval
        st.metric("Current Evaluation", f"{current_eval:+.2f}")
        
        # 3. DRAW ARROWS (Top Plan)
        # Update arrows automatically based on the #1 recommendation
        pv_arrows = [chess.svg.Arrow(top_move['move'].from_square, top_move['move'].to_square, color="green")]
        if len(top_move['pv']) > 1:
            m2 = top_move['pv'][1]
            pv_arrows.append(chess.svg.Arrow(m2.from_square, m2.to_square, color="blue"))
        
        # Only update session arrows if they changed (avoids flicker)
        if str(pv_arrows) != str(st.session_state.arrows):
            st.session_state.arrows = pv_arrows
            st.rerun()

        # 4. MOVE LIST (Clickable Buttons)
        st.subheader("Recommended Moves (Click to Play)")
        
        for i, cand in enumerate(candidates):
            # Format: "1. e4 (+0.35) - Controls Center"
            plan_str = st.session_state.board.variation_san(cand['pv'])
            btn_label = f"#{i+1}: {cand['san']} (Eval: {cand['eval']:+.2f})"
            
            # The Button
            if st.button(btn_label, key=f"rec_{i}"):
                # PLAY THE MOVE
                st.session_state.last_eval = cand['eval'] # Store for next comparison
                st.session_state.board.push(cand['move'])
                st.rerun()
            
            # The Plan Text (Small)
            st.caption(f"Plan: {plan_str}")
            st.divider()
            
    else:
        st.error("Engine could not analyze.")

# Update 'last_eval' at the end of every run to track changes
if candidates:
    st.session_state.last_eval = candidates[0]['eval']
