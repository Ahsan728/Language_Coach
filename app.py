import os
import sys

from backend import create_app


app = create_app()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1'
    print()
    print('=' * 55)
    print('  Language Coach  --  Bhasha Shikkha')
    print('=' * 55)
    print(f'  Open your browser:  http://localhost:{port}')
    print('  Press Ctrl+C to stop')
    print('=' * 55)
    print()
    app.run(debug=False, host=host, port=port)
