# webfish.py, JN, 22.09.2024
from flask import Flask, request, jsonify
from stockfish import Stockfish
import chess.pgn

from io import StringIO
import json

SF_PATH = "stockfish/stockfish-ubuntu-x86-64-avx2"
SF_CONFIG_PATH = "stockfish_config.json"
MAX_DEPTH = 30

app = Flask(__name__)

# Load engine parameters from a file
with open(SF_CONFIG_PATH) as f:
    engine_params = json.load(f)

# Initialize Stockfish engine
stockfish = Stockfish(path=SF_PATH, parameters=engine_params)


# Function to convert PGN to a list of FEN positions
def pgn_to_fen_list(pgn):
    game = chess.pgn.read_game(StringIO(pgn))
    fens = []
    node = game
    while node.variations:
        next_node = node.variation(0)
        fens.append(node.board().fen())  # Get FEN for each position
        node = next_node
    return fens


# API to analyze PGN
@app.route("/analyze", methods=["POST"])
def analyze_pgn():
    data = request.json
    pgn = data.get("pgn")
    depth = data.get("depth", MAX_DEPTH)  # Defaults to MAX_DEPTH

    # Set engine depth if provided
    stockfish.set_depth(depth)

    # Get FEN positions from PGN
    fens = pgn_to_fen_list(pgn)

    # Analyze each FEN position
    positions = []
    for fen in fens:
        stockfish.set_fen_position(fen)
        best_moves = stockfish.get_top_moves(3)  # Get top 3 moves
        positions.append({"fen": fen, "best_moves": best_moves})

    return jsonify(positions)


if __name__ == "__main__":
    app.run(debug=True)

# eof
