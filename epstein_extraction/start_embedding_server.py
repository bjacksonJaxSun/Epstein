#!/usr/bin/env python3
"""
Simple HTTP embedding server for all-MiniLM-L6-v2 (384 dimensions).

This serves the same embedding model used to create the document chunk
embeddings stored in PostgreSQL, enabling vector similarity search in
the AI Chat RAG pipeline.

Usage:
    python start_embedding_server.py [--port 5050] [--host localhost]

The ChatController expects:
    POST /embed  {"text": "query string"}
    Returns:     {"embedding": [0.123, -0.456, ...]}  (384-dim float array)
"""

import argparse
import json
import sys
import time


def main():
    parser = argparse.ArgumentParser(description="Embedding server for RAG vector search")
    parser.add_argument("--port", type=int, default=5050, help="Port to listen on (default: 5050)")
    parser.add_argument("--host", default="localhost", help="Host to bind to (default: localhost)")
    args = parser.parse_args()

    # Import and load model
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("ERROR: sentence-transformers not installed.")
        print("Run: pip install sentence-transformers")
        sys.exit(1)

    print("Loading all-MiniLM-L6-v2 model...")
    start = time.time()
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"Model loaded in {time.time() - start:.1f}s ({model.get_sentence_embedding_dimension()} dimensions)")

    # Use Flask for a robust HTTP server
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        print("ERROR: flask not installed.")
        print("Run: pip install flask")
        sys.exit(1)

    app = Flask(__name__)

    @app.route('/embed', methods=['POST'])
    def embed():
        data = request.get_json(force=True)
        text = data.get('text', '')
        if not text:
            return jsonify({"error": "No text provided"}), 400

        embedding = model.encode(text, normalize_embeddings=True).tolist()
        return jsonify({"embedding": embedding})

    @app.route('/embed/batch', methods=['POST'])
    def embed_batch():
        data = request.get_json(force=True)
        texts = data.get('texts', [])
        if not texts:
            return jsonify({"error": "No texts provided"}), 400

        embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32).tolist()
        return jsonify({"embeddings": embeddings})

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({
            "status": "ok",
            "model": "all-MiniLM-L6-v2",
            "dimensions": model.get_sentence_embedding_dimension()
        })

    print(f"\nEmbedding server running on http://{args.host}:{args.port}")
    print(f"  POST /embed       - Single text embedding")
    print(f"  POST /embed/batch - Batch text embeddings")
    print(f"  GET  /health      - Health check")
    print(f"\nPress Ctrl+C to stop\n")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
