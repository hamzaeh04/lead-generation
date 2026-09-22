"""Local Redis stand-in for Windows (no Docker / Memurai required).

Listens on 127.0.0.1:6379 so FastAPI rate-limiting and JWT revocation work.
"""
from fakeredis import TcpFakeServer

if __name__ == "__main__":
    server = TcpFakeServer(("127.0.0.1", 6379), server_type="redis")
    print("fakeredis listening on 127.0.0.1:6379", flush=True)
    server.serve_forever()
