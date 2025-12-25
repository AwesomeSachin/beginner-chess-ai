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
    return tf.keras.models.load_model('my_chess_model.keras')

model = load_my_model()

# --- HELPER: LOGIC TO EXPLAIN MOVES (THE "WHY") ---
def explain_move(board, move, is_opening, is_endgame):
    explanation = []
    
    # 1. THE OPENING LOGIC
    if is_opening:
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            explanation.append("🎯 **Control the Center:** You are taking the 'high ground' (e4/d4/e5/d5). This restricts the opponent.")
        
        piece_type = board.piece_type_at(move.from_square)
        if piece_type in [chess.KNIGHT, chess.BISHOP]:
            explanation.append("🦄 **Development:** Good job getting a minor piece off the back rank.")
            if piece_type == chess.KNIGHT:
                explanation.append("*(Rule of Thumb: Knights usually come out before Bishops!)*")
        
        if board.is_castling(move):
            explanation.append("🏰 **King Safety:** Excellent! Castling moves the King away from the dangerous center.")

    # 2. TACTICS & MIDDLEGAME
    if board.is_capture(move):
        explanation.append("⚔️ **Piece Economy/Trading:** You are capturing material or trading. Always ask: 'Is this a good trade?'")
        if board.piece_at(move.to_square): # If capturing a piece
             val = {1:1, 2:3, 3:3, 4:5, 5:9, 6:0}
             explanation.append(f"*(Captured value: ~{val.get(board.piece_type_at(move.to_square), 0)} points)*")

    # Check for Checks
    if board.gives_check(move):
        explanation.append("⚠️ **Attack:** This move puts the opponent in Check. Force them to react.")

    # 3. ENDGAME
    if is_endgame:
        if board.piece_type_at(move.from_square) == chess.KING:
             explanation.append("👑 **Active King:** In the endgame, the King is a fighter! Bring him to the center.")
        if board.piece_type_at(move.from_square) == chess.PAWN:
             explanation.append("🚀 **Promotion:** Push that pawn! The goal is to make a Queen.")

    if not explanation:
        explanation.append("💡 **Strategic Improvement:** This move improves your position based on the board structure.")

    return "\n\n".join(explanation)

# --- HELPER: PREDICT WITH YOUR MODEL ---
def get_ai_suggestion(board):
    # Prepare data for your model
    # (Must match the exact preprocessing used in Colab)
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
    
    # Get legal moves and score them based on prediction
    legal_moves = list(board.legal_moves)
    best_move = None
    best_score = -1
    
    for move in legal_moves:
        # Our model predicts "Target Square" probability
        score = prediction[move.to_square]
        if score > best_score:
            best_score = score
            best_move = move
            
    return best_move

# --- UI LAYOUT ---
st.title("♟️ AI Chess Tutor: Learn the Principles")
st.write("A Hybrid AI that uses Neural Networks for intuition and Logic for explanation.")

# Sidebar for Input
with st.sidebar:
    st.header("Game Input")
    pgn_input = st.text_area("Paste PGN here (from Chess.com/Lichess):")
    
    # Navigation State
    if 'move_index' not in st.session_state:
        st.session_state.move_index = 0
    
    load_game = st.button("Load Game")
    reset = st.button("Reset to Start")

# Game Logic
if reset:
    st.session_state.move_index = 0
    st.session_state.game = chess.pgn.Game()

if load_game and pgn_input:
    try:
        pgn = io.StringIO(pgn_input)
        st.session_state.game = chess.pgn.read_game(pgn)
        st.session_state.move_index = 0
        st.success("Game Loaded!")
    except:
        st.error("Invalid PGN")

if 'game' not in st.session_state:
    st.session_state.game = chess.pgn.Game()

# Replay Logic
game = st.session_state.game
board = game.board()
moves = list(game.mainline_moves())

# Step through moves
for i in range(st.session_state.move_index):
    if i < len(moves):
        board.push(moves[i])

# --- MAIN DISPLAY ---
col1, col2 = st.columns([1, 1])

with col1:
    # Render Board
    # We use SVG to render the board
    board_svg = chess.svg.board(board=board, size=400)
    st.image(f"data:image/svg+xml;base64,{base64.b64encode(board_svg.encode('utf-8')).decode('utf-8')}")

    # Navigation Buttons
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("⬅️ Previous"):
            if st.session_state.move_index > 0:
                st.session_state.move_index -= 1
                st.rerun()
    with c2:
        st.write(f"Move: {st.session_state.move_index}")
    with c3:
        if st.button("Next ➡️"):
            if st.session_state.move_index < len(moves):
                st.session_state.move_index += 1
                st.rerun()

with col2:
    st.subheader("🤖 AI Analysis")
    
    # Determine Game Phase
    move_count = st.session_state.move_index // 2
    phase = "Opening"
    if move_count > 10: phase = "Middlegame"
    if move_count > 30: phase = "Endgame" # Simplified logic
    
    st.info(f"Current Phase: **{phase}**")

    # 1. Suggest a Move (Using YOUR Model)
    suggested_move = get_ai_suggestion(board)
    
    if suggested_move:
        st.write(f"### My AI Suggests: **{suggested_move.uci()}**")
        
        # 2. Explain the Logic
        is_opening = phase == "Opening"
        is_endgame = phase == "Endgame"
        explanation = explain_move(board, suggested_move, is_opening, is_endgame)
        
        st.markdown(explanation)
        
        if st.button(f"Play {suggested_move.uci()}"):
             # In a real app, this would update the board, 
             # but here we just show analysis for simplicity
             st.write("Move simulated on analysis board.")
             
    else:
        st.warning("Game Over or No Legal Moves")

    # 3. Possible Moves (Clickable)
    st.write("---")
    st.write("**All Playable Moves:**")
    legal_moves = [m.uci() for m in board.legal_moves]
    
    # Display as tags/buttons
    cols = st.columns(4)
    for idx, m in enumerate(legal_moves[:12]): # Show top 12 to save space
        cols[idx % 4].button(m, key=m)
