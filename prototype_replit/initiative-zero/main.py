# main.py
from app import app
from database import init_db

if __name__ == '__main__':
    init_db()
    print("✓ Database initialized")
    print("✓ Starting Initiative Zero on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=True)