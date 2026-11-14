"""한국 공공 API MCP 서버 — git clone 후 경로로 직접 실행할 때의 진입점.

    python server.py                                  # stdio
    python server.py --transport http --port 8000     # http://127.0.0.1:8000/mcp
"""

from kr_opendata.app import main, mcp  # noqa: F401  (fastmcp run server.py:mcp 지원)

if __name__ == "__main__":
    main()
