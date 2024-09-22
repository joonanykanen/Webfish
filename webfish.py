# webfish.py, JN, 22.09.2024
import os
from io import StringIO
import json

from flask import Flask, request, jsonify
from stockfish import Stockfish
import chess.pgn

SF_PATH = "stockfish/stockfish-ubuntu-x86-64-avx2"
SF_CONFIG_PATH = "stockfish_config.json"
MAX_DEPTH = 30

app = Flask(__name__)

# Load engine parameters from a file
try:
    if not os.path.exists(SF_CONFIG_PATH):
        raise FileNotFoundError(f"Configuration file {SF_CONFIG_PATH} not found.")

    with open(SF_CONFIG_PATH) as f:
        engine_params = json.load(f)
except FileNotFoundError as e:
    app.logger.error(f"File error: {e}")
    engine_params = {}  # Use default parameters if config not found
except json.JSONDecodeError as e:
    app.logger.error(f"Error decoding JSON config: {e}")
    engine_params = {}  # Use default parameters on config error

# Initialize Stockfish engine
try:
    stockfish = Stockfish(path=SF_PATH, parameters=engine_params)
    if not stockfish.is_ready():
        raise EnvironmentError("Stockfish engine is not ready.")
except Exception as e:
    app.logger.error(f"Error initializing Stockfish: {e}")
    stockfish = None  # Set to None if initialization fails


# Function to convert PGN to a list of FEN positions
def pgn_to_fen_list(pgn):
    try:
        game = chess.pgn.read_game(StringIO(pgn))
        if game is None:
            raise ValueError("Invalid PGN format.")

        fens = []
        node = game
        while node.variations:
            next_node = node.variation(0)
            fens.append(node.board().fen())  # Get FEN for each position
            node = next_node
        return fens
    except Exception as e:
        app.logger.error(f"Error parsing PGN: {e}")
        return []


# API to analyze PGN
@app.route("/analyze", methods=["POST"])
def analyze_pgn():
    if stockfish is None:
        return jsonify({"error": "Stockfish engine is not initialized."}), 500

    try:
        data = request.json
        if not data or "pgn" not in data:
            return jsonify({"error": "Invalid request: 'pgn' field is required."}), 400

        pgn = data.get("pgn")
        depth = data.get("depth", MAX_DEPTH)

        # Validate depth
        if not isinstance(depth, int) or depth <= 0:
            return (
                jsonify(
                    {"error": "Invalid 'depth' value. It must be a positive integer."}
                ),
                400,
            )

        # Set engine depth
        stockfish.set_depth(depth)

        # Get FEN positions from PGN
        fens = pgn_to_fen_list(pgn)
        if not fens:
            return jsonify({"error": "No valid positions found in PGN."}), 400

        # Analyze each FEN position
        positions = []
        for fen in fens:
            stockfish.set_fen_position(fen)
            best_moves = stockfish.get_top_moves(3)  # Get top 3 moves
            positions.append({"fen": fen, "best_moves": best_moves})

        return jsonify(positions)

    except Exception as e:
        app.logger.error(f"Error analyzing PGN: {e}")
        return jsonify({"error": "An internal error occurred during analysis."}), 500


if __name__ == "__main__":
    app.run(debug=True)

# eof
