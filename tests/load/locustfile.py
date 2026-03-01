from locust import HttpUser, task, between

class NotificationQueueTestUser(HttpUser):
    """
    역할 (Role):
        검토자 관점 - 시스템의 비동기 워커 부하 처리를 모의(Simulation)하는 Load Test 매트릭스 환경입니다.
        (실제로는 외부 Webhook API를 향해 쏘거나 Message Queue에 이벤트를 적재하는 속도를 판별함)
        
    실행 방법: locust -f tests/load/locustfile.py --headless -u 1000 -r 50
    """
    
    # 각 가상 유저(구독자)들의 모의 통신 딜레이 설정
    wait_time = between(1, 3) 
    
    @task(3)
    def test_mock_notification_queue(self):
        """가상의 구독자가 리포트를 전송받기 위해 큐에 진입하는 속도 테스트 (API 엔드포인트가 있다고 가정)"""
        # (주의: 백엔드 Webhook/API 엔드포인트가 연동되었다면 self.client.post("/api/enqueue_report", json=...) 등 사용)
        pass 
        
    @task(1)
    def test_feedback_submit(self):
        """가상의 사용자들이 동시에 피드백 (별점/좋아요) 링크를 클릭했을 때의 DB 부하 벤치마킹"""
        # 앞서 만든 FastAPI /api/feedback 서버 타겟팅
        self.client.get("/api/feedback?user=LoadTester&score=5&comment=Fast")
