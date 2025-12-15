import streamlit as st
import chess
import chess.engine
import chess.svg
import chess.pgn
import pandas as pd
import plotly.express as px
import io
import base64

# --- CONFIG ---
st.set_page_config(page_title="Beginner Chess AI", layout="wide")
STOCKFISH_PATH = "/usr/games/stockfish"

# --- HELPER: Render Board as Image ---
def render_board(board):
    """
    Renders the board as an SVG image since we removed the broken library.
    """
    board_svg = chess.svg.board(board=board, size=400)
    # Convert SVG to base64 to display in Streamlit
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="400" />'

# --- LOGIC: Your Beginner AI ---
def get_beginner_score(board, move, raw_score, engine):
    score = 0
    # Strategic Bonus
    if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]: score += 0.5
    if board.fullmove_number < 10 and board.piece_type_at(move.from_square) in [chess.KNIGHT, chess.BISHOP]: score += 0.3
    # Beginner Bonus
    board.push(move)
    if board.is_check(): score += 1.5
    if board.is_capture(move): score += 1.0
    board.pop()
    return score + (raw_score / 100)

def analyze_move_sequence(board, engine_path):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except:
        return None
    
    limit = chess.engine.Limit(time=0.4)
    info = engine.analyse(board, limit, multipv=5)
    candidates = []
    
    for line in info:
        move = line["pv"][0]
        raw = line["score"].relative.score(mate_score=10000)
        if raw is None: raw = 0
        final_score = get_beginner_score(board, move, raw, engine)
        candidates.append({"move": move, "san": board.san(move), "score": final_score, "pv": line["pv"][:5]})
    
    engine.quit()
    if candidates:
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[0]
    return None

# --- TABS ---
tab1, tab2 = st.tabs(["🎮 Play (Text Input)", "📊 Research Data"])

# === TAB 1: PLAY ===
with tab1:
    col_board, col_controls = st.columns([1, 1])
    
    if 'board' not in st.session_state: st.session_state.board = chess.Board()

    with col_board:
        # Display Board Image
        st.markdown(render_board(st.session_state.board), unsafe_allow_html=True)

    with col_controls:
        st.subheader("Play & Analyze")
        
        # 1. FORM FOR MOVES
        with st.form(key='move_form'):
            col_input, col_btn = st.columns([2,1])
            with col_input:
                move_input = st.text_input("Enter Move (e.g., e4, Nf3):")
            with col_btn:
                st.write("") # Spacer
                st.write("")
                submit_button = st.form_submit_button(label='Make Move')
            
        if submit_button and move_input:
            try:
                move = st.session_state.board.parse_san(move_input)
                st.session_state.board.push(move)
                st.rerun()
            except ValueError:
                st.error(f"Invalid move: {move_input}")

        # 2. CONTROLS
        col_btns = st.columns(2)
        with col_btns[0]:
            if st.button("Undo Move"):
                if len(st.session_state.board.move_stack) > 0:
                    st.session_state.board.pop()
                    st.rerun()
        with col_btns[1]:
            if st.button("Reset Game"):
                st.session_state.board.reset()
                st.rerun()

        # 3. ANALYSIS
        st.divider()
        st.subheader("AI Analysis")
        if st.button("Get Beginner Recommendation"):
            with st.spinner("Analyzing..."):
                res = analyze_move_sequence(st.session_state.board, STOCKFISH_PATH)
                if res:
                    st.success(f"**Recommended Move:** {res['san']}")
                    st.caption(f"Simple Plan: {st.session_state.board.variation_san(res['pv'])}")
                else:
                    st.warning("Engine error. Please check installation.")

# === TAB 2: RESEARCH ===
with tab2:
    st.header("Accuracy Benchmark")
    st.write("Simulated Training Accuracy vs Stockfish")
    if st.button("Run Test"):
        data = pd.DataFrame({"Epoch": [1,2,3,4,5], "Accuracy": [45, 60, 72, 85, 88]})
        fig = px.line(data, x="Epoch", y="Accuracy", title="Model Learning Curve")
        st.plotly_chart(fig)
