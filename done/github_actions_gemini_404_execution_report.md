# GitHub Actions Gemini 404 개선 실행 결과서

작성일: 2026-03-07  
참조 계획서: `done/github_actions_gemini_404_improvement_plan.md`

---

## 1) 수행 내역

1. `ai_summarizer.py`
- 모델 자동 선택 로직 추가 (`ListModels` 기반 + 캐시)
- `GEMINI_MODEL`, `GEMINI_MODEL_CANDIDATES` 후보군 지원
- 404 모델 오류 감지 시 대체 모델 즉시 전환
- 영구 모델 오류 `PermanentGeminiError` 도입(불필요 재시도 제외)

2. `prompt_manager.py`
- Notion 프롬프트 기본 모델을 `GEMINI_MODEL` 기반으로 갱신

3. CI 워크플로우
- `GEMINI_MODEL`, `GEMINI_MODEL_CANDIDATES`, `REDDIT_ENABLED=false` 적용

4. 환경 템플릿
- `.env.template`에 Gemini 모델 관련 env 및 Reddit 토글 추가

5. 테스트 보강
- `tests/services/test_ai_summarizer.py`에
  - 모델 선택 helper 테스트
  - 404 판별 helper 테스트 추가

6. 장애 기록/분석
- `errorCase/2026-03-06_github_actions_gemini_model_404.md` 작성

## 2) 검증 결과

- `python -m pytest tests/services/test_ai_summarizer.py -q` → `7 passed`
- `python -m pytest tests/services/ tests/test_e2e_dryrun.py -q` → `77 passed`
- `.githooks/pre-push` 실행 → `77 passed`

## 3) 누락/변경점 점검

- [x] 모델 하드코딩 제거
- [x] 404 대체 경로 추가
- [x] 재시도 정책 개선
- [x] CI 운영 환경값 반영
- [x] 테스트/기록 문서화 완료

## 4) 결론

- 동일 유형(모델 종료/변경) 장애에 대한 복원력이 크게 향상됨.
- CI 잡음(Reddit 403) 감소로 운영 로그 해석성이 개선됨.
