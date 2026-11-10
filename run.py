"""
Launcher script for General & Grocery Shop Customer MIS & Billing Application
"""
import socket
from app import app
from db import init_db
from seed_data import seed

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == '__main__':
    init_db()
    seed()
    local_ip = get_local_ip()
    port = 5000

    print("=" * 70)
    print("  SARFRAN GENERAL AND GROSSARY STORE NEWJATOI")
    print("=" * 70)
    print(f"  * Local PC Access:       http://localhost:{port}")
    print(f"  * Shop Mobile / Wi-Fi:   http://{local_ip}:{port}")
    print("=" * 70)
    print("  Press Ctrl+C to stop the application.")
    print("=" * 70)

    app.run(host='0.0.0.0', port=port, debug=False)

