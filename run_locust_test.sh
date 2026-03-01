#!/bin/bash
echo "Locust 부하 테스트를 백그라운드 서버와 함께 실행합니다."

# 1. FastAPI 피드백 서버를 백그라운드로 실행
python3 src/apps/feedback_server.py &
SERVER_PID=$!
sleep 3 # 서버 기동 대기

echo "서버 프로세스($SERVER_PID) 시작 완료. 부하 테스트 진행..."

# 2. Locust headless mode 실행 (10명의 사용자가 초당 2명씩 늘어나며 10초간 스왑)
python3 -m pip install locust && python3 -m locust -f tests/load/locustfile.py --headless -u 10 -r 2 -t 10s -H http://localhost:8000

# 3. 테스트 끝난 후 웹서버 종료
kill -9 $SERVER_PID
echo "부하 테스트 완료 및 웹 서버 종료"
