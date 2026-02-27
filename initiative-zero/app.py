import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from database import init_db

app = Flask(__name__, static_folder='static')
CORS(app)

# ─── Static file serving ───
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)


if __name__ == '__main__':
    init_db()
    print("✓ Database initialized")
    print("✓ Starting Initiative Zero on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
