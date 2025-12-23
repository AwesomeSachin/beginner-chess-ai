from stockfish import Stockfish

# Streamlit Cloud installs stockfish via packages.txt
STOCKFISH_PATH = "/usr/bin/stockfish"

stockfish = Stockfish(
    path=STOCKFISH_PATH,
    depth=8,
    parameters={
        "Threads": 2,
        "Minimum Thinking Time": 30
    }
)


def get_candidate_moves(fen, max_moves=8, eval_threshold=-0.5):
    """
    Use Stockfish ONLY to generate safe candidate moves.
    """
    stockfish.set_fen_position(fen)
    top_moves = stockfish.get_top_moves(max_moves)

    moves = []
    for m in top_moves:
        move = m.get("Move")
        cp = m.get("Centipawn")

        if move is None:
            continue

        if cp is not None and cp / 100 < eval_threshold:
            continue

        moves.append(move)

    return moves
