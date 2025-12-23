import chess


def get_candidate_moves(fen, max_moves=12):
    """
    Generate candidate moves WITHOUT Stockfish.
    Uses legal moves only.
    """
    board = chess.Board(fen)

    moves = [m.uci() for m in board.legal_moves]

    # Optional: limit for speed
    return moves[:max_moves]
