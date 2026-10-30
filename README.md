# Free AI Router

OpenRouter 무료 모델을 사용하는 초기 CLI입니다. 대화는 메모리에만 유지되며 OpenRouter와 선택된 제공업체로 전송됩니다. 제공업체는 요청마다 달라질 수 있습니다.

Python 3.11 이상이 필요합니다. 저장소 폴더에서 설치합니다.

```sh
python -m pip install .
```

API 키를 터미널 환경변수로 설정한 뒤 실행합니다. 키를 채팅이나 저장소에 올리지 마세요.

```sh
export OPENROUTER_API_KEY='발급받은 키'
ai chat
```

`Ctrl+D`로 종료합니다. 기본 모델은 OpenRouter가 무료 모델을 선택하는 `openrouter/free`입니다. `ai chat --model 제공업체/모델:free`로 무료 모델을 직접 선택할 수 있습니다. 유료 모델 ID는 요청 전에 거부합니다. 사용 한도와 제공 가능 모델은 OpenRouter 정책에 따라 달라집니다. 응답이 중단되면 자동 재시도하지 않으며, 부분 응답은 이후 대화에 포함하지 않습니다.

테스트: `PYTHONPATH=src python -m unittest discover -s tests`

브라우저에서 사용하려면 같은 환경변수를 설정한 뒤 `ai web`을 실행하세요. 설치하지 않은 경우 저장소 폴더에서 `PYTHONPATH=src python -m free_ai_router.cli web`으로 실행할 수 있습니다. 서버는 이 컴퓨터의 127.0.0.1에서만 접근할 수 있습니다. 터미널을 켜 둔 채 같은 기기에서 http://127.0.0.1:8765/ 를 여세요. 포트가 사용 중이면 `--port 8766`처럼 다른 포트를 지정하세요. 브라우저 대화는 새로고침하면 사라집니다. 답변은 안전한 일반 텍스트로 표시합니다.

Groq 무료 티어 계정은 `GROQ_API_KEY`와 `GROQ_FREE_TIER=1`을 설정하면 웹에서 선택할 수 있습니다. 이 설정은 계정이 무료 티어라는 사용자 확인입니다. Groq가 유료 티어로 변경되면 호출 전에 설정을 해제하세요. 자동 모드는 Groq를 먼저 사용하고 응답 전 429 또는 서버 장애가 발생하면 OpenRouter로 전환합니다. 수동 선택, 타임아웃, 응답 시작 후 오류는 자동 전환하지 않습니다. 전환하면 이전 대화가 새 제공업체에도 전송됩니다.
