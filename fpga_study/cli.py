"""コマンドラインエントリポイント: `fpga-study` コマンド"""

from __future__ import annotations

import argparse
import sys
import webbrowser
import threading
import time


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fpga-study",
        description="FPGAお勉強アプリ — ローカルWebサーバーを起動してブラウザで学習できます",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="バインドするホスト (デフォルト: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8731, help="ポート番号 (デフォルト: 8731)"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="ブラウザを自動で開かない"
    )
    parser.add_argument(
        "--reload", action="store_true", help="開発用: コード変更時に自動リロード"
    )
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"

    if not args.no_browser:
        def _open_browser() -> None:
            time.sleep(1.2)
            webbrowser.open(url)

        threading.Thread(target=_open_browser, daemon=True).start()

    print(f"🎓 FPGAお勉強アプリ を起動中...")
    print(f"   ブラウザで開く: {url}")
    print(f"   終了: Ctrl+C")

    try:
        import uvicorn
        from fpga_study.server import create_app

        app = create_app()
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="warning",
        )
    except KeyboardInterrupt:
        print("\n終了しました。")
        sys.exit(0)
