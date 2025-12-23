from stockfish import Stockfish
import shutil

_stockfish_instance = None


def get_stockfish():
    """
    Lazy initializer for Stockfish.
    This avoids FileNotFoundError on Streamlit Cloud.
    """
    global _stockfish_instance

    if _stockfish_instance is None:
        # Find stockfish binary installed via packages.txt
        stockfish_path = shutil.which("stockfish")

        if stockfish_path is None:
            raise RuntimeError(
                "Stockfish binary not found. "
                "Make sure packages.txt contains 'stockfish'."
            )

        _stockfish_instance = Stockfish(
            path=stockfish_path,
            depth=8,
            parameters={
                "Threads": 2,
                "Minimum Thinking Time": 30
            }
        )

    return _stockfish_instance


def get_candidate_moves(fen, max_moves=8, eval_threshold=-0.5):
    """
    Use Stockfish ONLY to generate safe candidate moves.
    Stockfish is initialized lazily for Streamlit Cloud safety.
    """
    stockfish = get_stockfish()

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
