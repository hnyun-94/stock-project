# Completed Work Report (As-Is Baseline)

작성일: 2026-03-07  
기준 브랜치: `master`

---

## 1) 목적

- 완료된 작업을 코드/문서/PR 기준으로 한 번에 확인할 수 있도록 정리합니다.
- 현재 운영 가능한 기준선(Baseline)을 명시하고, 후속 작업과 구분합니다.

---

## 2) 완료 상태 요약

### Phase 6 Task 상태

- Task 6.1 ~ 6.21: **모두 완료**
- 상세 체크리스트: `done/phase6_task.md`
- 통합 요약: `todo/todo.md`

### 최근 구현/정비 완료 항목 (PR #20 ~ #50 + 2026-03-07 기준선 정비)

1. PR #20
- Git 거버넌스 강제 워크플로우 적용
- 커밋 크기/품질게이트/PR 리뷰 템플릿 정렬

2. PR #21
- Gemini 404 복원력(모델 fallback) 강화
- Prompt 로더 안정화 + CI/환경 설정 정리

3. PR #22
- 시장 소스 정책 가드 + 정량 스냅샷 리포트 통합

4. PR #23
- 외부 무료 소스 커넥터(data.go/OpenDART/SEC/FRED) 추가

5. PR #24
- 외부 커넥터 텔레메트리(status/count/latency) + OpenDART 분류 지표 확장

6. PR #25
- 외부 커넥터 실행 이력 SQLite 영속화(`external_connector_runs`) 추가

7. PR #26
- 코드베이스 기준 문서/로그 동기화

8. PR #40
- 외부 커넥터 1H/24H 운영 알림 + 텔레그램 관리자 경보 + DB 쿨다운

9. PR #41
- `uv` 명령 권한 위임 정책 반영

10. PR #42
- 최근 7일 외부 커넥터 일자별 집계 리포트 + 데이터 신뢰도 섹션 추가

11. PR #43
- 남은 roadmap 범위 구현 완료
- OpenDART/FRED/SEC 해석 카드, metric trend, 리포트 신뢰도 배지, 운영 Runbook, PR Quality Gate 추가

12. PR #44
- roadmap/todo 기준선 참조 문서 최신화

13. PR #45
- 텔레그램 notifier timeout/분할 전송 보강
- changed-file Ruff 게이트와 PR workflow 품질 보정 추가

14. PR #46
- 리포트 Markdown 가독성 재설계
- 노이즈 제목 필터, 카드형 구조, 종목별 watch point 정리

15. PR #47
- 현재 repo 범위 `gh` 협업/조회 명령 위임 정책 확장

16. PR #48
- 다중 역할 리뷰 체계를 9개 역할로 확장
- 품질 담당자 / 시니어 개발자 / 주식 전문가 역할을 문서, skill, hook 검증에 반영

17. PR #49
- 작업 종료 시 context 유지/압축/초기화 판단 정책 추가
- deterministic hook가 아닌 운영 정책으로 정리

18. PR #50
- `AGENTS.md`를 상위 라우팅 문서로 축약
- 상세 지침을 skills/hook로 이관하고 `completion-context-triage` skill 추가

19. 2026-03-07 리포트 구독자 친화 레이아웃 개선
- 첨부 뉴스레터 레퍼런스를 참고해 상단 대시보드형 구성, 3축 브리핑, 시간대 압축판으로 재배치
- `decision_tiles`, `market_scoreboard`, `insight_lenses` 기반 payload 확장
- 이메일 HTML 표/blockquote 스타일 강화 및 compact brief 렌더링 구조 도입

20. 2026-03-07 이메일 렌더링/Quota 방어 후속 보강
- 이메일 제목을 실제 heading으로 렌더링하고, 테이블 기반 wrapper + 인라인 스타일로 메일 클라이언트 호환성을 강화
- 저신호 포털 문구 필터, 시장 카드용 `why_it_matters`, 종목별 고유 watch point 정제를 추가
- Gemini per-run budget, persistent quota block, 사용자 간 런타임 cache 재사용으로 free-tier 429 재발 가능성 축소
- UI/UX 전문가, 퍼블리셔 전문가를 review 문서/skill/hook 검증 체계에 반영

21. 2026-03-08 리포트 팔레트/헤더/문장 완결성 보강
- 이메일 메인 색상을 `#AEBDCA`, 보조색을 `#E8DFCA` 기준으로 재정렬
- 표 헤더를 `오늘 숫자`, `읽는 포인트`, `하루 변화` 같은 구독자 친화 별칭으로 변환
- 요약/전망/시각 문구에서 `…`로 잘린 문장이 남지 않도록 문장 단위 종료 규칙으로 변경

22. 2026-03-08 리포트 주요 뉴스 하이퍼링크 추가
- 시장 요약, 시간대 카드, 관심 테마, 보유 종목 카드에 `관련 기사` 링크 블록 추가
- `NewsArticle.link`를 payload `related_links`로 보존해 Markdown/HTML 양쪽에서 동일하게 렌더링
- 사용자가 요약 근거가 된 원문 기사를 바로 열어볼 수 있도록 개선

23. 2026-03-08 경제 흐름/학습 카드/강조 품질 보강
- `경제 온도`, `자금 흐름`, `시장 화제` 중심의 경제 상황/트렌드 섹션을 리포트 상단 해석 축으로 정비
- 리포트 하단에 `오늘의 경제 상식` 카드를 추가하고, 당일 주제와 맞는 용어를 우선 선택하도록 학습 카드 우선순위 로직 개선
- 표 셀까지 포함한 공통 강조 렌더링을 적용해 `중립`, `AI`, `HBM`, `환율` 같은 핵심 포인트의 스캔성을 강화

24. 2026-03-08 Gemini quota delay-aware retry 보강
- Gemini 429 quota 오류에서 `RetryInfo.retryDelay + 3초`를 실제 대기 시간으로 사용하고, 60초 이내 대기만 허용하는 지연 재시도 경로를 추가
- 짧은 quota 구간에서는 한 번 더 AI 응답 복구를 시도하고, 60초 초과 대기나 재실패 시에는 기존 로컬 fallback/quota block으로 전환
- 관련 회귀 테스트를 추가해 짧은 delay 성공, 긴 delay fallback, 후속 block 동작을 고정

---

## 3) 코드 기준선 (핵심 모듈)

- 거버넌스/운영:
  - `.githooks/pre-push`
  - `scripts/check_commit_size.sh`
  - `AGENTS.md`
  - `.agents/skills/review-driven-execution/SKILL.md`
  - `.agents/skills/completion-context-triage/SKILL.md`
  - `.agents/skills/command-permission-governance/SKILL.md`

- AI/Prompt 안정화:
  - `src/services/ai_summarizer.py`
  - `src/services/prompt_manager.py`
  - `scripts/provision_prompt_db.py`

- 시장 소스/통계:
  - `src/services/market_source_governance.py`
  - `src/services/market_signal_summary.py`
  - `src/services/market_external_connectors.py`
  - `src/main.py`

- DB/텔레메트리:
  - `src/utils/database.py`
  - `external_connector_runs`, `connector_alert_events`, `connector_metric_points`
  - 성공률/일자별 롤업/metric trend 조회 API

- 운영/리포트:
  - `src/services/connector_alerts.py`
  - `src/services/report_builder.py`
  - `src/utils/report_formatter.py`
  - `done/operations_runbook.md`
  - `.github/workflows/pr_quality_gate.yml`

---

## 4) 품질 기준선

- 테스트 명령:
  - `uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q`
- 최신 기준: **149 passed**

---

## 5) 참고 문서 맵

- 완료 체크 요약: `todo/todo.md`
- 상세 Task 원본: `done/phase6_task.md`
- 병렬 실행/역할 검증: `done/parallel_role_priority_execution_plan.md`
- 다음 작업 계획: `task/next_steps_roadmap.md`
- 당일 상세 실행 로그는 로컬 `logging/`에 두고, 공유 기준선은 본 문서와 관련 `task/` 문서로 추적합니다.

---

## 6) 남은 일 (완료 작업과 구분)

완료된 작업 이후 후속 과제는 아래 문서에서만 관리합니다.

- `task/next_steps_roadmap.md`

우선순위:
1. 2026-03-07 기준 계획된 작업 중 미완료 항목은 확인되지 않음
2. 신규 요구사항은 별도 계획 문서에서 재정의
