import streamlit as st
import chess
import chess.pgn
import chess.engine
import chess.svg
import numpy as np
import tensorflow as tf
import io
import base64

# --- CONFIGURATION ---
st.set_page_config(page_title="Beginner AI Chess Coach", layout="wide")

# --- LOAD YOUR TRAINED MODEL ---
@st.cache_resource
def load_my_model():
    # Make sure 'my_chess_model.keras' is in the same folder
    return tf.keras.models.load_model('my_chess_model.keras')

try:
    model = load_my_model()
except:
    st.error("⚠️ Model file not found. Please upload 'my_chess_model.keras'.")
    st.stop()

# --- SESSION STATE SETUP ---
if 'board' not in st.session_state:
    st.session_state.board = chess.Board()

# --- HELPER FUNCTIONS ---

def reset_game():
    st.session_state.board = chess.Board()

def load_pgn(pgn_string):
    try:
        pgn = io.StringIO(pgn_string)
        game = chess.pgn.read_game(pgn)
        st.session_state.board = game.board()
        for move in game.mainline_moves():
            st.session_state.board.push(move)
        st.success("Game Loaded Successfully!")
    except:
        st.error("Invalid PGN format.")

def make_move(move_uci):
    try:
        move = chess.Move.from_uci(move_uci)
        if move in st.session_state.board.legal_moves:
            st.session_state.board.push(move)
        else:
            st.warning("Illegal move!")
    except:
        st.error("Move error.")

def undo_move():
    if len(st.session_state.board.move_stack) > 0:
        st.session_state.board.pop()

# --- AI LOGIC (The "Brain") ---

def explain_move(board, move):
    """Generates the beginner-friendly explanation."""
    explanation = []
    
    # Check phase
    full_moves = board.fullmove_number
    phase = "Opening"
    if full_moves > 10: phase = "Middlegame"
    if full_moves > 30: phase = "Endgame"

    # 1. OPENING PRINCIPLES
    if phase == "Opening":
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            explanation.append("🎯 **Control the Center:** You are taking the 'high ground' (e4/d4/e5/d5).")
        
        piece_type = board.piece_type_at(move.from_square)
        if piece_type in [chess.KNIGHT, chess.BISHOP]:
            explanation.append("🦄 **Development:** Getting pieces off the back rank.")
        
        if board.is_castling(move):
            explanation.append("🏰 **King Safety:** Castling moves the King to safety and connects the Rooks.")

    # 2. TACTICS
    if board.is_capture(move):
        explanation.append("⚔️ **Piece Trade:** Capturing material. Always check if the trade favors you.")
    
    if board.gives_check(move):
        explanation.append("⚠️ **Check:** Forcing the opponent to react.")

    # 3. ENDGAME
    if phase == "Endgame":
        if board.piece_type_at(move.from_square) == chess.KING:
             explanation.append("👑 **Active King:** The King must fight in the endgame!")
        if board.piece_type_at(move.from_square) == chess.PAWN:
             explanation.append("🚀 **Promotion:** Pushing the pawn to make a Queen.")

    if not explanation:
        explanation.append("💡 **Strategic Move:** Improves position structure.")

    return "\n\n".join(explanation)

def get_ai_suggestion(board):
    """Runs the Neural Network to find the best move."""
    # Data Preprocessing (Must match training)
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
    
    # Predict
    prediction = model.predict(input_data, verbose=0)[0]
    
    # Filter for Legal Moves
    legal_moves = list(board.legal_moves)
    best_move = None
    best_score = -1
    
    for move in legal_moves:
        score = prediction[move.to_square] # Score based on target square
        if score > best_score:
            best_score = score
            best_move = move
            
    return best_move

# --- APP LAYOUT ---

st.title("♟️ AI Chess Tutor")
st.markdown("**User Contribution:** Data Engineering (Lichess DB), CNN Architecture, Heuristic Logic Layer.")

# Sidebar
with st.sidebar:
    st.header("Controls")
    if st.button("🔄 Reset Board"):
        reset_game()
        st.rerun()
    
    if st.button("↩️ Undo Move"):
        undo_move()
        st.rerun()

    st.markdown("---")
    pgn_input = st.text_area("Paste PGN (optional):")
    if st.button("Load PGN"):
        load_pgn(pgn_input)
        st.rerun()

# Main Area
col1, col2 = st.columns([1.5, 1])

# 1. GET AI SUGGESTION FIRST (To draw the arrow)
suggested_move = get_ai_suggestion(st.session_state.board)

with col1:
    # DRAW BOARD WITH ARROW
    arrows = []
    if suggested_move:
        # Create a Blue Arrow for the suggestion
        arrows.append(chess.svg.Arrow(suggested_move.from_square, suggested_move.to_square, color="#0000cccc"))

    board_svg = chess.svg.board(
        board=st.session_state.board, 
        arrows=arrows,
        size=500
    )
    st.image(f"data:image/svg+xml;base64,{base64.b64encode(board_svg.encode('utf-8')).decode('utf-8')}")

with col2:
    st.subheader("🧠 Analysis")
    
    if st.session_state.board.is_game_over():
        st.warning(f"Game Over: {st.session_state.board.result()}")
    
    elif suggested_move:
        st.success(f"**Best Move:** {suggested_move.uci()}")
        
        # Explain Why
        explanation = explain_move(st.session_state.board, suggested_move)
        st.info(explanation)
        
        # Button to Play the Suggested Move
        if st.button(f"▶️ Play Suggested ({suggested_move.uci()})"):
            make_move(suggested_move.uci())
            st.rerun()
    else:
        st.warning("No moves available.")

    st.markdown("---")
    st.write("### All Legal Moves")
    
    # List all legal moves as clickable buttons
    legal_moves = [m.uci() for m in st.session_state.board.legal_moves]
    
    # Create a grid of buttons
    cols = st.columns(4)
    for i, move_uci in enumerate(legal_moves):
        if cols[i % 4].button(move_uci):
            make_move(move_uci)
            st.rerun()
