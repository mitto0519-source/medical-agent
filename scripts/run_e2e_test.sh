#!/usr/bin/env bash
# Medical-Agent E2E 테스트 실행 스크립트

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     Medical-Agent Streamlit End-to-End 테스트                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# 1. Streamlit 앱 시작
echo "📱 Streamlit 앱 시작 중..."
cd "$(dirname "$0")/.."

# 백그라운드에서 Streamlit 시작
streamlit run app/streamlit_app.py \
  --server.headless=true \
  --logger.level=warning \
  --server.port=8501 \
  > /tmp/streamlit.log 2>&1 &

STREAMLIT_PID=$!
echo "Streamlit PID: $STREAMLIT_PID"

# 앱이 시작될 때까지 대기
echo "⏳ 앱 시작 대기 중 (최대 15초)..."
for i in {1..15}; do
  if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo "✅ Streamlit 앱이 http://localhost:8501에서 실행 중"
    break
  fi
  sleep 1
  echo -n "."
done

echo ""
echo ""

# 2. E2E 테스트 실행
echo "🧪 E2E 테스트 시작..."
python scripts/test_e2e_headless.py

TEST_RESULT=$?

# 3. 정리
echo ""
echo "🔌 Streamlit 종료..."
kill $STREAMLIT_PID 2>/dev/null
wait $STREAMLIT_PID 2>/dev/null

if [ $TEST_RESULT -eq 0 ]; then
  echo ""
  echo "╔════════════════════════════════════════════════════════════════╗"
  echo "║                    ✅ E2E 테스트 성공!                        ║"
  echo "╚════════════════════════════════════════════════════════════════╝"
  exit 0
else
  echo ""
  echo "╔════════════════════════════════════════════════════════════════╗"
  echo "║                    ❌ E2E 테스트 실패!                        ║"
  echo "╚════════════════════════════════════════════════════════════════╝"
  echo ""
  echo "📋 Streamlit 로그:"
  tail -30 /tmp/streamlit.log
  exit 1
fi
