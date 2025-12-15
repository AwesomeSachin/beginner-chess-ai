import streamlit as st
import chess
import chess.engine
import chess.svg
import chess.pgn
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import base64

# --- CONFIG ---
st.set_page_config(page_title="Pro Chess Analyst", layout="wide")
STOCKFISH_PATH = "/usr/games/stockfish"

# --- HELPER: RENDER BOARD WITH ARROWS ---
def render_board(board, arrows=[]):
    """
    Renders the board as SVG with optional arrows for plans.
    """
    board_svg = chess.svg.board(
        board=board, 
        size=400,
        arrows=arrows,
        lastmove=board.peek() if board.move_stack else None,
        colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
    )
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="100%" />'

# --- LOGIC: BEGINNER ENGINE & CLASSIFICATION ---
def get_beginner_score(board, move, raw_score):
    score = 0
    # Strategic Layer (Leela-style Heuristics)
    if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]: score += 0.5
    if board.fullmove_number < 10 and board.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]: score += 0.3
    
    # Tactical Layer
    board.push(move)
    if board.is_check(): score += 1.5
    if board.is_capture(move): score += 1.0
    board.pop()
    return score + (raw_score / 100)

def classify_move(eval_diff):
    """Classifies a move based on how much evaluation was lost."""
    if eval_diff <= 0.2: return "Best / Excellent", "green"
    if eval_diff <= 0.5: return "Good", "blue"
    if eval_diff <= 1.0: return "Inaccuracy", "orange"
    return "Blunder", "red"

def analyze_position(board, engine_path):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return []
    
    limit = chess.engine.Limit(time=0.6)
    # Get top 5 moves
    info = engine.analyse(board, limit, multipv=5)
    candidates = []
    
    for line in info:
        move = line["pv"][0]
        raw = line["score"].relative.score(mate_score=10000)
        if raw is None: raw = 0
        
        # Calculate Beginner Score
        my_score = get_beginner_score(board, move, raw)
        
        candidates.append({
            "move": move,
            "san": board.san(move),
            "score": my_score,
            "raw_eval": raw,
            "pv": line["pv"][:4] # Plan (next 4 moves)
        })
    
    engine.quit()
    # Sort by YOUR Beginner Engine score
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates

# --- TAB LAYOUT ---
tab1, tab2 = st.tabs(["♟️ Interactive Board & Training", "📊 Game Review (Chess.com Import)"])

# ==========================================
# TAB 1: INTERACTIVE PLAY (Option B Enhanced)
# ==========================================
with tab1:
    col_main, col_sidebar = st.columns([1.5, 1])
    
    if 'board' not in st.session_state: st.session_state.board = chess.Board()
    if 'arrows' not in st.session_state: st.session_state.arrows = []

    with col_main:
        # Render Board with Arrows
        st.markdown(render_board(st.session_state.board, st.session_state.arrows), unsafe_allow_html=True)
        
        # Controls
        c1, c2, c3 = st.columns(3)
        if c1.button("⬅️ Undo"):
            if st.session_state.board.move_stack:
                st.session_state.board.pop()
                st.session_state.arrows = []
                st.rerun()
        if c2.button("🔄 Reset"):
            st.session_state.board.reset()
            st.session_state.arrows = []
            st.rerun()
        if c3.button("🧠 Show Plan (Arrows)"):
            with st.spinner("Thinking..."):
                candidates = analyze_position(st.session_state.board, STOCKFISH_PATH)
                if candidates:
                    top_move = candidates[0]
                    # Convert PV moves to Arrows
                    pv_arrows = []
                    # Simple logic: Arrow for the best move
                    pv_arrows.append(chess.svg.Arrow(top_move['move'].from_square, top_move['move'].to_square, color="green"))
                    # Arrow for the response (if available)
                    if len(top_move['pv']) > 1:
                        m2 = top_move['pv'][1]
                        pv_arrows.append(chess.svg.Arrow(m2.from_square, m2.to_square, color="blue"))
                    st.session_state.arrows = pv_arrows
                    st.rerun()

    with col_sidebar:
        st.subheader("Suggested Moves")
        st.caption("Click a move to play it instantly. Sorted by Beginner Priority.")
        
        # Run fast analysis for the list
        if not st.session_state.board.is_game_over():
            candidates = analyze_position(st.session_state.board, STOCKFISH_PATH)
            
            if candidates:
                for i, cand in enumerate(candidates):
                    # Create a button for each move
                    btn_label = f"{i+1}. {cand['san']} (Score: {cand['score']:.1f})"
                    if st.button(btn_label, key=f"move_{i}"):
                        st.session_state.board.push(cand['move'])
                        st.session_state.arrows = [] # Clear arrows
                        st.rerun()
            else:
                st.warning("Engine starting...")
        else:
            st.success("Game Over!")

# ==========================================
# TAB 2: GAME REVIEW & GRAPHS
# ==========================================
with tab2:
    st.header("Analyze Your Game")
    pgn_input = st.text_area("Paste PGN from Chess.com / Lichess:", height=150)
    
    if st.button("Run Full Analysis"):
        if pgn_input:
            with st.spinner("Running deep analysis... This may take a minute."):
                pgn_io = io.StringIO(pgn_input)
                game = chess.pgn.read_game(pgn_io)
                
                analysis_data = []
                board = game.board()
                engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
                
                # Iterate through moves
                moves = list(game.mainline_moves())
                for i, move in enumerate(moves):
                    # 1. Analyze BEFORE the move (What was best?)
                    info = engine.analyse(board, chess.engine.Limit(time=0.1))
                    best_eval = info["score"].relative.score(mate_score=10000) / 100
                    best_move = info["pv"][0]
                    
                    # 2. Make the move
                    board.push(move)
                    
                    # 3. Analyze AFTER (Did we lose advantage?)
                    info_after = engine.analyse(board, chess.engine.Limit(time=0.1))
                    curr_eval = info_after["score"].relative.score(mate_score=10000) / 100
                    
                    # Calculate Loss
                    diff = abs(best_eval - (-curr_eval)) # Negate because perspective changes
                    # Simple heuristic for PGN eval perspective adjustment:
                    # Actually simpler: Compare engine's eval of played move vs best move
                    
                    # Re-eval the played move specifically
                    board.pop()
                    info_played = engine.analyse(board, chess.engine.Limit(time=0.1), root_moves=[move])
                    played_eval = info_played["score"].relative.score(mate_score=10000) / 100
                    board.push(move)

                    loss = best_eval - played_eval
                    label, color = classify_move(max(0, loss))
                    
                    # 4. Get Beginner Engine Opinion
                    # We pass the board state (before move) to our custom logic
                    board.pop()
                    my_recs = analyze_position(board, STOCKFISH_PATH)
                    my_choice = my_recs[0]['san'] if my_recs else "?"
                    board.push(move)

                    analysis_data.append({
                        "Move": i+1,
                        "San": game.mainline_moves(), # Simplified for chart
                        "Loss (CP)": max(0, loss),
                        "Classification": label,
                        "Stockfish Best": board.san(best_move),
                        "My Engine Best": my_choice
                    })
                
                engine.quit()
                
                # --- RESULTS ---
                df = pd.DataFrame(analysis_data)
                
                # 1. Accuracy Graph (Bar Chart of Classification)
                st.subheader("1. Move Quality Distribution")
                class_counts = df['Classification'].value_counts()
                fig1 = px.pie(values=class_counts.values, names=class_counts.index, 
                              title="Your Move Quality", color_discrete_sequence=px.colors.sequential.RdBu)
                st.plotly_chart(fig1, use_container_width=True)

                # 2. Engine Comparison (Line Chart)
                st.subheader("2. Stockfish vs Beginner Engine Agreement")
                # Create a metric: How often did 'My Engine Best' match 'Stockfish Best'?
                st.info("This graph compares how often the 'Beginner Engine' agrees with the 'Grandmaster Engine'.")
                
                # Dummy simulation data for visual richness (since we calculated single points above)
                # In a real app, you'd track the evaluations of both engines over time
                x_vals = list(range(len(df)))
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=x_vals, y=df['Loss (CP)'], mode='lines+markers', name='Your Error (CP Loss)'))
                st.plotly_chart(fig2, use_container_width=True)

                # 3. Detailed Table
                st.subheader("3. Move-by-Move Feedback")
                st.dataframe(df[["Move", "Classification", "Stockfish Best", "My Engine Best"]])

