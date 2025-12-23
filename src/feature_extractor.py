import chess
import numpy as np

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9
}

CENTER_SQUARES = [chess.D4, chess.E4, chess.D5, chess.E5]


def material_balance(board):
    balance = 0
    for piece, val in PIECE_VALUES.items():
        balance += len(board.pieces(piece, chess.WHITE)) * val
        balance -= len(board.pieces(piece, chess.BLACK)) * val
    return balance


def hanging_pieces(board, color):
    count = 0
    for sq, piece in board.piece_map().items():
        if piece.color != color:
            continue
        if board.attackers(not color, sq) and not board.attackers(color, sq):
            count += 1
    return count


def king_safety(board, color):
    king_sq = board.king(color)
    if king_sq is None:
        return 0
    attackers = board.attackers(not color, king_sq)
    return -sum(1 for sq in attackers if chess.square_distance(sq, king_sq) <= 2)


def development_score(board, color):
    back_rank = 0 if color == chess.WHITE else 7
    score = 0
    for p in [chess.KNIGHT, chess.BISHOP]:
        for sq in board.pieces(p, color):
            if chess.square_rank(sq) != back_rank:
                score += 1
    return score


def center_control(board, color):
    return sum(1 for sq in CENTER_SQUARES if board.is_attacked_by(color, sq))


def extract_features(fen, move, elo):
    board = chess.Board(fen)
    color = board.turn

    features = []

    # BEFORE MOVE
    features += [
        elo,
        material_balance(board),
        hanging_pieces(board, color),
        king_safety(board, color),
        development_score(board, color),
        center_control(board, color)
    ]

    chess_move = chess.Move.from_uci(move)
    features += [
        int(board.is_capture(chess_move)),
        int(board.gives_check(chess_move))
    ]

    board.push(chess_move)

    # AFTER MOVE
    features += [
        material_balance(board),
        hanging_pieces(board, color),
        king_safety(board, color),
        development_score(board, color),
        center_control(board, color)
    ]

    # DELTAS
    features += [
        features[7] - features[2],   # delta hanging
        features[8] - features[3],   # delta king safety
        features[9] - features[4],   # delta development
        features[10] - features[5]   # delta center control
    ]

    return np.array(features, dtype=float)
