import os
import sys
from dotenv import load_dotenv
from app import create_app

load_dotenv()

if __name__ == '__main__':
    app = create_app()
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    port = int(os.getenv('FLASK_PORT', 5001))
    print(f"Starting server on port {port} (debug={debug})", file=sys.stderr)
    app.run(debug=debug, host='0.0.0.0', port=port, use_reloader=False)
