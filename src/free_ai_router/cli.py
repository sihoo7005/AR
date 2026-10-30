import argparse
import os
import sys
import webbrowser

from .chat import ChatError, stream_chat


def main():
    parser = argparse.ArgumentParser(description="무료 AI 채팅")
    parser.add_argument("command", choices=["chat", "web"])
    parser.add_argument("--model", default="auto", help="auto 또는 :free로 끝나는 OpenRouter 모델 ID")
    parser.add_argument("--port", type=int, default=8765, help="웹 서버 포트 (기본값: 8765)")
    args = parser.parse_args()
    model = "openrouter/free" if args.model == "auto" else args.model
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        print("OPENROUTER_API_KEY 환경변수를 설정하세요.", file=sys.stderr)
        return 1
    if args.command == "web":
        from .web import make_server
        if not 1 <= args.port <= 65535:
            parser.error("포트는 1부터 65535 사이여야 합니다.")
        try:
            groq_key = os.environ.get("GROQ_API_KEY", "").strip() if os.environ.get("GROQ_FREE_TIER") == "1" else None
            server = make_server(key, args.port, groq_key=groq_key)
        except OSError as exc:
            print(f"웹 서버를 시작할 수 없습니다: {exc}", file=sys.stderr)
            return 1
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"로컬 웹 서버: {url} (종료: Ctrl+C)", flush=True)
        try:
            webbrowser.open(url)
        except webbrowser.Error:
            pass
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print()
        finally:
            server.server_close()
        return 0
    print(f"모델: {model}. OpenRouter 무료 모델을 사용합니다. 대화는 제공업체에 전송됩니다. 종료: Ctrl+D")
    messages = []
    while True:
        try:
            prompt = input("\n나: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not prompt:
            continue
        messages.append({"role": "user", "content": prompt})
        parts = []
        print("AI: ", end="", flush=True)
        try:
            for part in stream_chat(key, messages, model):
                parts.append(part)
                print(part, end="", flush=True)
        except (ChatError, KeyboardInterrupt) as exc:
            messages.pop()
            print(f"\n응답 중단: {exc or '사용자가 취소했습니다.'}", file=sys.stderr)
            continue
        print()
        messages.append({"role": "assistant", "content": "".join(parts)})


if __name__ == "__main__":
    sys.exit(main())
