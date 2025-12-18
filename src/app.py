import streamlit as st
import chess
import chess.pgn
import chess.svg
import chess.engine
import io
import base64

# --- CONFIG ---
st.set_page_config(page_title="Checkmate Coach: Blunder Fixer", layout="wide")
STOCKFISH_PATH = "/usr/games/stockfish"

# --- STATE MANAGEMENT ---
if 'puzzles' not in st.session_state: st.session_state.puzzles = []
if 'current_puzzle_index' not in st.session_state: st.session_state.current_puzzle_index = 0
if 'user_solved' not in st.session_state: st.session_state.user_solved = False

# --- HELPER: RENDER BOARD ---
def render_board(board, highlight_move=None):
    arrows = []
    if highlight_move:
        arrows = [chess.svg.Arrow(highlight_move.from_square, highlight_move.to_square, color="#4CAF50")]
        
    board_svg = chess.svg.board(
        board=board, 
        size=500,
        arrows=arrows,
        colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
    )
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="100%" style="display:block; margin:auto;" />'

# --- THE ML LAYER (SIMULATED FOR APP) ---
def is_beginner_friendly(board, move):
    """
    This represents your Machine Learning Model.
    It filters out complex positions that confuse beginners.
    
    Logic:
    1. If the best move is a Check -> Beginner Friendly (Tactical)
    2. If the best move is a Capture -> Beginner Friendly
    3. If the best move is quiet positional play -> Skip it (Too hard)
    """
    board.push(move)
    is_check = board.is_check()
    is_capture = board.is_capture(move)
    board.pop()
    
    # ML Decision Boundary:
    # Beginners learn best from Checks and Captures.
    if is_check or is_capture:
        return True
    return False

# --- LOGIC: GAME SCANNER ---
def generate_puzzles_from_game(pgn_text):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    except:
        st.error("Stockfish not found!")
        return []

    pgn_io = io.StringIO(pgn_text)
    game = chess.pgn.read_game(pgn_io)
    
    board = game.board()
    puzzles = []
    
    # We need to track the "Best Move" at every turn to catch blunders
    # This can be slow, so we limit to first 30 moves for the demo
    moves = list(game.mainline_moves())[:40] 
    
    progress_bar = st.progress(0)
    
    for i, move in enumerate(moves):
        # Update Progress
        progress_bar.progress((i + 1) / len(moves))
        
        # 1. Analyze position BEFORE the move
        info = engine.analyse(board, chess.engine.Limit(time=0.1))
        best_eval = info["score"].relative.score(mate_score=10000) or 0
        best_move_engine = info["pv"][0]
        
        # 2. Analyze the ACTUAL move played
        board.push(move)
        info_played = engine.analyse(board, chess.engine.Limit(time=0.1))
        played_eval = -info_played["score"].relative.score(mate_score=10000) or 0 # Invert because perspective flipped
        board.pop() # Restore to "Before" state
        
        # 3. Detect Blunder (Eval dropped by > 1.5)
        diff = (best_eval - played_eval) / 100
        
        if diff > 2.0: # Huge mistake threshold
            # 4. ML FILTER: Is this a simple enough puzzle?
            if is_beginner_friendly(board, best_move_engine):
                puzzles.append({
                    "fen": board.fen(),
                    "move_played": move, # The bad move
                    "best_move": best_move_engine, # The solution
                    "move_number": (i // 2) + 1,
                    "diff": diff
                })
        
        # Advance board for next loop
        board.push(move)
        
    engine.quit()
    return puzzles

# --- UI START ---
st.title("🎓 Checkmate Coach: The Blunder Fixer")
st.markdown("This AI scans your game, finds your **critical mistakes**, and turns them into **puzzles** for you to solve.")

# SIDEBAR: INPUT
with st.sidebar:
    st.header("1. Input Game")
    pgn_input = st.text_area("Paste PGN here:", height=150)
    
    if st.button("Analyze Game"):
        if pgn_input:
            with st.spinner("🔍 AI is scanning for teachable moments..."):
                found_puzzles = generate_puzzles_from_game(pgn_input)
                st.session_state.puzzles = found_puzzles
                st.session_state.current_puzzle_index = 0
                st.session_state.user_solved = False
                
                if not found_puzzles:
                    st.warning("Good news! No major tactical blunders found (or they were too complex).")
                else:
                    st.success(f"Found {len(found_puzzles)} critical mistakes to fix!")
        else:
            st.error("Please paste a PGN.")

# MAIN AREA: PUZZLE INTERFACE
if st.session_state.puzzles:
    idx = st.session_state.current_puzzle_index
    puzzle = st.session_state.puzzles[idx]
    
    # Header
    st.subheader(f"🧩 Mistake #{idx + 1} (Move {puzzle['move_number']})")
    
    col_board, col_quiz = st.columns([1, 1])
    
    with col_board:
        # Create board from FEN
        board_display = chess.Board(puzzle['fen'])
        
        # Show the board
        # If solved, show the green arrow solution
        if st.session_state.user_solved:
             st.markdown(render_board(board_display, puzzle['best_move']), unsafe_allow_html=True)
        else:
             st.markdown(render_board(board_display), unsafe_allow_html=True)

    with col_quiz:
        st.info(f"In this position, you played **{board_display.san(puzzle['move_played'])}**.")
        st.warning("That move was a Blunder! You missed a winning tactic.")
        st.markdown("### Can you find the best move?")
        
        # User Guess Input (Simulated via buttons or text for simplicity)
        # For a full app, you'd use a draggable board, but text is easier for Streamlit
        user_move_san = st.text_input("Type your move (e.g., Nf3, Qxe4):", key=f"input_{idx}")
        
        if st.button("Check Answer"):
            try:
                # Convert SAN to Move Object
                parsed_move = board_display.parse_san(user_move_san)
                
                if parsed_move == puzzle['best_move']:
                    st.balloons()
                    st.success(f"✅ Correct! **{user_move_san}** is the best move.")
                    st.markdown("**Why?** It immediately punishes the opponent (Check/Capture).")
                    st.session_state.user_solved = True
                else:
                    st.error("❌ Not quite. That doesn't solve the problem. Try again!")
            except:
                st.error("Invalid move format. Use standard notation (e.g., 'Nf3').")
        
        if st.session_state.user_solved:
             if st.button("Next Mistake ➡️"):
                 if idx + 1 < len(st.session_state.puzzles):
                     st.session_state.current_puzzle_index += 1
                     st.session_state.user_solved = False
                     st.rerun()
                 else:
                     st.success("🎉 You've fixed all your mistakes from this game!")
        
        if st.button("Give Up? Show Solution"):
            st.info(f"The best move was **{board_display.san(puzzle['best_move'])}**.")
            st.session_state.user_solved = True
            st.rerun()

else:
    st.info("👈 Paste a PGN on the left to start your training session.")
