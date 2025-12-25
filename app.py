import streamlit as st
import chess
import chess.pgn
import chess.svg
import numpy as np
import tensorflow as tf
import io
import base64

# --- CONFIGURATION ---
st.set_page_config(page_title="Beginner AI Chess Coach", layout="wide")

# --- LOAD MODEL ---
@st.cache_resource
def load_my_model():
    try:
        return tf.keras.models.load_model('my_chess_model.keras')
    except:
        return None

model = load_my_model()

# --- SESSION STATE INITIALIZATION ---
if 'board' not in st.session_state:
    st.session_state.board = chess.Board()
if 'game_moves' not in st.session_state:
    st.session_state.game_moves = [] # Stores the list of moves from a PGN
if 'move_index' not in st.session_state:
    st.session_state.move_index = 0 # Points to current move in the list

# --- CORE FUNCTIONS ---

def reset_game():
    st.session_state.board = chess.Board()
    st.session_state.game_moves = []
    st.session_state.move_index = 0

def load_pgn(pgn_string):
    try:
        pgn = io.StringIO(pgn_string)
        game = chess.pgn.read_game(pgn)
        
        # 1. Reset board to start
        st.session_state.board = game.board() 
        
        # 2. Store all moves in a list
        st.session_state.game_moves = list(game.mainline_moves())
        
        # 3. Set index to 0 (Start of game)
        st.session_state.move_index = 0
        
        st.success(f"Game Loaded! ({len(st.session_state.game_moves)} moves)")
    except Exception as e:
        st.error(f"Error loading PGN: {e}")

def go_to_move(index):
    # Replay the game from start up to the specific index
    # This ensures the board state is always correct
    temp_board = chess.Board() # Start fresh
    
    # Bound check
    if index < 0: index = 0
    if index > len(st.session_state.game_moves): index = len(st.session_state.game_moves)
    
    # Replay moves
    for i in range(index):
        temp_board.push(st.session_state.game_moves[i])
    
    st.session_state.board = temp_board
    st.session_state.move_index = index

# --- AI LOGIC WITH "SANITY FILTER" ---

def get_ai_suggestion(board):
    if model is None: return None
    
    # 1. PREPROCESS INPUT (Same as training)
    pieces = {'p': 1, 'n': 2, 'b': 3, 'r': 4, 'q': 5, 'k': 6,
              'P': 7, 'N': 8, 'B': 9, 'R': 10, 'Q': 11, 'K': 12}
    foo = []
    for cell in board.epd().split(' ')[0]:
        if cell.isdigit():
            for i in range(int(cell)): foo.append(0)
        elif cell == '/': continue
        else: foo.append(pieces[cell])
    
    matrix = np.array(foo).reshape(8, 8)
    matrix_one_hot = (np.arange(13) == matrix[..., None]).astype(np.float32)
    input_data = np.expand_dims(matrix_one_hot, axis=0)
    
    # 2. GET RAW PREDICTIONS (Probability of "Target Square")
    prediction = model.predict(input_data, verbose=0)[0]
    
    # 3. SCORE LEGAL MOVES (With Heuristics)
    legal_moves = list(board.legal_moves)
    best_move = None
    best_score = -9999
    
    for move in legal_moves:
        # Base score from Neural Network
        score = prediction[move.to_square] * 100 
        
        # --- SANITY FILTERS (Fixing the "Bad Moves") ---
        
        # A. Center Control Bonus
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            score += 0.5 
            
        # B. Capture Bonus (Aggression)
        if board.is_capture(move):
            score += 0.3
            
        # C. Retreat Penalty (Prevent moving pieces back to start unnecessarily)
        # If piece moves to back rank (rank 1 for white, 8 for black) and wasn't under attack
        is_white = board.turn
        rank = chess.square_rank(move.to_square)
        if (is_white and rank == 0) or (not is_white and rank == 7):
            score -= 0.8 # Heavy penalty for retreating to back rank

        # Update Best
        if score > best_score:
            best_score = score
            best_move = move
            
    return best_move

def explain_move(board, move):
    explanation = []
    # Simplified Logic for Beginner Explanation
    if board.is_capture(move):
        explanation.append("⚔️ **Capture:** Taking material is often good, but check for traps!")
    elif move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
        explanation.append("🎯 **Center Control:** Occupying the middle gives you space.")
    elif board.gives_check(move):
        explanation.append("⚠️ **Check:** Force the King to move.")
    else:
        explanation.append("💡 **Positional Play:** Improving piece activity.")
    
    return " ".join(explanation)

# --- UI LAYOUT ---

st.title("♟️ Hybrid AI Chess Analyst")

# SIDEBAR: CONTROLS
with st.sidebar:
    st.header("Game Controls")
    
    # PGN Input
    pgn_input = st.text_area("Paste PGN here:", height=150)
    if st.button("📂 Load Game"):
        if pgn_input:
            load_pgn(pgn_input)
            st.rerun()
        else:
            reset_game()
            st.rerun()
            
    st.markdown("---")
    st.write("**Navigation**")
    
    col_nav1, col_nav2, col_nav3, col_nav4 = st.columns(4)
    
    with col_nav1:
        if st.button("⏮️ Start"):
            go_to_move(0)
            st.rerun()
    with col_nav2:
        if st.button("⬅️ Prev"):
            go_to_move(st.session_state.move_index - 1)
            st.rerun()
    with col_nav3:
        if st.button("Next ➡️"):
            go_to_move(st.session_state.move_index + 1)
            st.rerun()
    with col_nav4:
        if st.button("End ⏭️"):
            go_to_move(len(st.session_state.game_moves))
            st.rerun()

    st.write(f"Move: **{st.session_state.move_index} / {len(st.session_state.game_moves)}**")

# MAIN DISPLAY
col1, col2 = st.columns([1.5, 1])

# Run AI Analysis
suggested_move = get_ai_suggestion(st.session_state.board)

with col1:
    # Draw Arrows
    arrows = []
    if suggested_move:
        # Blue arrow for AI suggestion
        arrows.append(chess.svg.Arrow(suggested_move.from_square, suggested_move.to_square, color="#0000ccaa"))
    
    # Last move arrow (Yellow)
    if len(st.session_state.board.move_stack) > 0:
        last_move = st.session_state.board.peek()
        arrows.append(chess.svg.Arrow(last_move.from_square, last_move.to_square, color="#ffcc00aa"))

    # Render Board
    board_svg = chess.svg.board(
        board=st.session_state.board, 
        arrows=arrows,
        size=550
    )
    st.image(f"data:image/svg+xml;base64,{base64.b64encode(board_svg.encode('utf-8')).decode('utf-8')}")

with col2:
    st.subheader("🧠 Model Analysis")
    
    # Status
    turn_text = "White to Move" if st.session_state.board.turn else "Black to Move"
    st.caption(turn_text)

    if suggested_move:
        st.success(f"**Best Move:** {suggested_move.uci()}")
        st.markdown(explain_move(st.session_state.board, suggested_move))
        
        # 'Play Suggested' Button (Only works if we are at the end of current history or in free play)
        if st.button(f"▶️ Play {suggested_move.uci()}"):
            st.session_state.board.push(suggested_move)
            # If we were analyzing a historical game, playing a new move branches off
            # So we effectively clear the 'future' moves
            st.session_state.game_moves = st.session_state.game_moves[:st.session_state.move_index] + [suggested_move]
            st.session_state.move_index += 1
            st.rerun()
            
    else:
        if st.session_state.board.is_game_over():
            st.error(f"Game Over: {st.session_state.board.result()}")
        else:
            st.warning("Model loading or no moves found.")

    st.markdown("---")
    st.write("### Playable Moves")
    # Grid of playable moves
    legal_moves = [m.uci() for m in st.session_state.board.legal_moves]
    cols = st.columns(4)
    for i, move_uci in enumerate(legal_moves):
        if cols[i % 4].button(move_uci, key=move_uci):
            move = chess.Move.from_uci(move_uci)
            st.session_state.board.push(move)
             # Update history branch
            st.session_state.game_moves = st.session_state.game_moves[:st.session_state.move_index] + [move]
            st.session_state.move_index += 1
            st.rerun()
