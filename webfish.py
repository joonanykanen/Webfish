# webfish.py, JN, 22.09.2024
import os
from io import StringIO
import json

from flask import Flask, request, jsonify
from stockfish import Stockfish
import chess.pgn

import datetime as dt
import uuid

SF_PATH = "stockfish/stockfish-ubuntu-x86-64-avx2"
SF_CONFIG_PATH = "stockfish_config.json"
ANALYSES_FOLDER = "analyses"  # Folder to store analysis results
MAX_DEPTH = 15  # For stronger play, set depth to at least 30

app = Flask(__name__)

# Ensure analyses folder exists
os.makedirs(ANALYSES_FOLDER, exist_ok=True)

# Load engine parameters from a file with error handling
try:
    with open(SF_CONFIG_PATH) as f:
        engine_params = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    app.logger.error(f"Error loading Stockfish config: {e}")
    engine_params = {}

# Initialize Stockfish engine with error handling
try:
    stockfish = Stockfish(path=SF_PATH, parameters=engine_params)
    if not stockfish.is_ready():
        raise EnvironmentError("Stockfish engine is not ready.")
except Exception as e:
    app.logger.error(f"Error initializing Stockfish: {e}")
    stockfish = None


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


# Function to save analysis results to a file
def save_analysis_to_file(data):
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())
    filename = f"{timestamp}_{unique_id}.json"
    filepath = os.path.join(ANALYSES_FOLDER, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return filepath
    except Exception as e:
        app.logger.error(f"Error saving analysis to file: {e}")
        return None


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

        analysis_data = {"pgn": pgn, "depth": depth, "positions": positions}

        # Save analysis results to file
        saved_filepath = save_analysis_to_file(analysis_data)
        if not saved_filepath:
            return jsonify({"error": "Failed to save analysis results."}), 500

        return jsonify({"status": "success", "analysis": analysis_data})

    except Exception as e:
        app.logger.error(f"Error analyzing PGN: {e}")
        return jsonify({"error": "An internal error occurred during analysis."}), 500


if __name__ == "__main__":
    app.run(debug=True)

# eof
