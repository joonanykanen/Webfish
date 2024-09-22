# webfish.py, JN, 22.09.2024
import os
from io import StringIO
import json

from flask import Flask, request, jsonify
from stockfish import Stockfish
import chess.pgn

import datetime as dt
import uuid
import logging

SF_PATH = "stockfish/stockfish-ubuntu-x86-64-avx2"
SF_CONFIG_PATH = "stockfish_config.json"
ANALYSES_FOLDER = "analyses"  # Folder to store analysis results
MAX_DEPTH = 15  # For stronger play, set depth to at least 30

# Initialize Flask app
app = Flask(__name__)

# Set up logging for the app
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# Ensure analyses folder exists
os.makedirs(ANALYSES_FOLDER, exist_ok=True)

# Load engine parameters from a file
try:
    app.logger.info("Loading Stockfish configuration from %s", SF_CONFIG_PATH)
    with open(SF_CONFIG_PATH) as f:
        engine_params = json.load(f)
    app.logger.info("Stockfish configuration loaded successfully.")
except (FileNotFoundError, json.JSONDecodeError) as e:
    app.logger.error("Error loading Stockfish config: %s", e)
    engine_params = {}

# Log before initializing Stockfish
app.logger.info("Initializing Stockfish engine from %s", SF_PATH)

# Initialize Stockfish engine
try:
    stockfish = Stockfish(path=SF_PATH, parameters=engine_params)
    app.logger.info("Stockfish engine initialized successfully.")
except Exception as e:
    app.logger.error("Error initializing Stockfish: %s", e)
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
        app.logger.error("Error parsing PGN: %s", e)
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
        app.logger.error("Error saving analysis to file: %s", e)
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
        total_fens = len(fens)

        for index, fen in enumerate(fens):
            stockfish.set_fen_position(fen)
            best_moves = stockfish.get_top_moves(3)  # Get top 3 moves
            positions.append({"fen": fen, "best_moves": best_moves})

            # Log current position analysis
            percent_complete = (index + 1) / total_fens * 100
            app.logger.info(
                "Analyzing position %d/%d (FEN: %s) - %.2f%% complete",
                index + 1,
                total_fens,
                fen,
                percent_complete,
            )

        analysis_data = {"pgn": pgn, "depth": depth, "positions": positions}

        # Save analysis results to file
        saved_filepath = save_analysis_to_file(analysis_data)
        if not saved_filepath:
            return jsonify({"error": "Failed to save analysis results."}), 500

        return jsonify({"status": "success", "analysis": analysis_data})

    except Exception as e:
        app.logger.error("Error analyzing PGN: %s", e)
        return jsonify({"error": "An internal error occurred during analysis."}), 500


if __name__ == "__main__":
    app.logger.info("Starting Flask server...")
    app.run(
        host="0.0.0.0", port=5000, debug=True
    )  # Use WSGI in production instead of this

# eof
