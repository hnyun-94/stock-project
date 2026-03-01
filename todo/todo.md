# 향후 고도화 및 요구사항 (Todo - Phase 5)

## 기획자 (Product Manager / Data Strategist) 관점

- [x] **AI 성과의 장기 Back-testing (완료)**
  - 과거에 저장해두었던 `prediction_snapshots.json` 데이터를 정제하고, 현재 주가/시장 상황과 비교하는 채점표(Scoring) 스크립트 작성.
  - 리포트에 "과거 예측 적중률 분석" 코너 추가.

## 개발자 (Backend / Infrastructure Engineer) 관점

- [x] **Docker 분산 환경 배포 셋업 (완료)**
  - FastAPI 기반의 피드백 서버와, 크롤링 봇/알림 메인 파이프라인을 독립적인 컨테이너로 띄우기 위한 `Dockerfile` 구성.
  - 서비스 간 볼륨(log 연동) 및 의존성 관리를 위한 `docker-compose.yml` 작성.

## 검토자 (QA / Code Reviewer) 관점

- [x] **보안 심사 (Security Audit) (완료)**
  - Webhook URL (피드백 수집기) 의 유효성 서명(Signature)을 검증하여, 외부에서의 무분별한 어뷰징(Abusing)을 차단.
