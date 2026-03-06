# 국내/미국 주식시장 데이터 소스 다각도 검토 및 무과금 구현 계획서

작성일: 2026-03-07  
대상: Stock Report Automation (GitHub Actions 3시간 주기)

---

## 1) 목적

- 국내/미국 주식시장 트렌드 파악에 적합한 사이트(API) 후보를 PM, TPM, 기획, 개발, 운영 관점에서 검토
- 무료 수집/분석 가능 여부(약관, 호출한도, 배포/재가공 조건) 확인
- 수집 데이터로 사용자에게 제공할 요약/통계 설계
- 구현 방법론/작업계획 수립 후, 누락/리스크 재검토를 거쳐 구현 착수

---

## 2) 역할별 우선 소스 검토

### A. PM 관점 (로드맵/지표 완성도)

- 국내:
  - 금융위원회_주식시세정보 (data.go.kr)
  - 금융위원회_KRX상장종목정보 (data.go.kr)
  - OpenDART (공시/재무)
- 미국:
  - SEC EDGAR API (기업 공시)
  - FRED API (거시/금리/리스크 지표)
  - Alpha Vantage (EOD 보조 가격)

핵심 판단:
- 무과금으로도 "가격+공시+트렌드+거시"의 4축 구성이 가능
- 다만 실시간 US 시세는 유료 구간(Alpha 문서상 premium-only)으로 설계 시 EOD 중심 접근 필요

### B. TPM 관점 (기술 적합성/호출 안정성)

- 요청 한도와 스케줄 적합성:
  - data.go.kr: 개발계정 트래픽 10,000회/일(문서 표기)
  - OpenDART: 20,000건/일, 과도 접속(분당 1,000회 이상) 제한 가능
  - Naver DataLab: 1,000회/일
  - SEC EDGAR: 초당 10요청 이하 권고
  - Alpha Vantage Free: 25요청/일
- 결론:
  - 3시간 주기(일 8회)에서도 캐시/배치/저빈도 호출 전략 적용 시 무과금 운영 가능

### C. 기획자 관점 (사용자 가치/해석 가능성)

- 트렌드 해석에 유의미한 소스:
  - Naver DataLab: 테마/키워드 관심도 변화
  - OpenDART + SEC: 공시 이벤트 급증/감소(리스크 조기 신호)
  - 가격/지수(국내+미국): 추세/변동성/분산
- 사용자 가치:
  - 단순 뉴스요약에서 "수치 기반 시장 체력 진단"으로 확장 가능

### D. 개발자 관점 (구현 난이도/정규화)

- 구현 난이도 낮음:
  - OpenDART, SEC, FRED, Naver DataLab: JSON 기반 REST
  - data.go.kr: 공공데이터 표준 응답(JSON/XML) 정규화 필요
- 구현 난이도 중간:
  - 소스별 심볼 체계 매핑(종목코드/CIK/티커/시리즈 ID)
  - 호출한도 기반 스케줄러/캐시 정책

### E. 운영자 관점 (장애/법적 리스크/비용)

- 안정 운영 핵심:
  - 호출 버짓 가드(일/분당)
  - 소스별 Circuit Breaker + 폴백
  - 약관상 재배포 제약 소스 제외
- 중요 제외 판단:
  - KRX OpenAPI(마켓플레이스)는 약관상 비상업 목적/제3자 제공 제한 조항이 있어 현재 "사용자 리포트 배포형" 서비스와 충돌 가능

---

## 3) 무료/약관/호출한도 점검 결과

| 소스 | 무료 여부 | 한도/트래픽 | 배포/상업 활용 관점 | 판정 |
|---|---|---|---|---|
| 금융위_주식시세정보(data.go.kr) | 무료 | 10,000회/일(개발계정) | 이용허락범위 제한없음(문서 표기) | 사용 |
| 금융위_KRX상장종목정보(data.go.kr) | 무료 | 10,000회/일(개발계정) | 이용허락범위 제한없음(문서 표기) | 사용 |
| OpenDART | 무료 | 20,000건/일, 분당 1,000회 이상 과다접속 제한 가능 | 공공데이터법/약관 준수 필요 | 사용 |
| Naver DataLab API | 무료 | 1,000회/일 | 네이버 오픈API 약관/키 관리 준수 | 사용 |
| SEC EDGAR API | 무료 | 초당 10요청 이하 권고, User-Agent 필수 | 저작권 제한 없음(SEC 문서) | 사용 |
| FRED API | 무료(키 필요) | 고정 수치 공개 없음(제한 조정 가능 명시) | 일부 제3자 저작권 시리즈는 별도 허가 필요 | 조건부 사용 |
| Alpha Vantage | 무료 + 유료 | Free 25요청/일 | 실시간/15분 지연 US 시세는 premium-only | 보조 사용 |
| KRX OpenAPI(거래소) | 무료 | 10,000회/일 | 비상업 목적, 제3자 제공 제한 조항 존재 | 제외 |

---

## 4) 수집 방안 (무과금 우선)

## 4-1. 권장 소스 조합 (v1)

- 국내:
  - data.go.kr 주식시세/상장종목 (기본 가격/유니버스)
  - OpenDART (공시/재무 이벤트)
  - Naver DataLab (관심도/테마)
- 미국:
  - SEC EDGAR (기업 공시 이벤트)
  - FRED (거시/금리/리스크 지표)
  - Alpha Vantage Free (EOD 보조 가격, 저빈도/캐시)

## 4-2. 수집 주기/버짓 설계

- 파이프라인 실행: 3시간 간격(일 8회)
- 권장 호출 정책:
  - 고빈도 필요 없음 소스(OpenDART/SEC/FRED): 1일 1~2회로 캐시
  - Naver DataLab: 1~2회/일
  - Alpha Vantage: 2~3회/일 이하(총 25회/일 미만 엄수)
- 실행당 무조건 호출이 아니라 `TTL + 마지막 동기화 일자` 기반 호출

---

## 5) 사용자 제공 요약/통계 설계

### A. 핵심 요약

- 국내 장세 한줄: KOSPI/KOSDAQ 방향 + 거래대금/수급 요약
- 미국 장세 한줄: S&P500/NASDAQ 방향 + 금리/변동성 보조 해석
- 공시 이벤트 요약: 국내/미국 중요 공시 건수 변화
- 검색 관심도 요약: 테마 키워드 관심도 급등/급락

### B. 통계치

- 수익률: 1D, 5D, 20D
- 변동성: 20일 연환산 변동성
- 모멘텀: 단기(5D) vs 중기(20D) 상대 강도
- 공시 히트지수: 최근 24시간/7일 공시 건수 z-score
- 트렌드 가속도: 키워드 검색지수 주간 변화율
- 시장 레짐 점수: Risk-on/off (가격/변동성/공시/트렌드 가중치 결합)

---

## 6) 개발 방법론

- 방식: Incremental Delivery + Risk-first
- 원칙:
  - 1단계에서 약관/한도 리스크를 코드로 관리(정책 레지스트리)
  - 2단계에서 수집기보다 정규화/통계 엔진을 먼저 안정화
  - 3단계에서 소스 커넥터를 점진 연결
  - 모든 단계에서 테스트 우선(단위 + dryrun)

---

## 7) 작업계획 (실행 단위)

1. Source Governance 구현
- 소스별 무료한도/상업성/재배포 정책/권장 호출량 코드화
- 스케줄 기반 일 호출량 추정 및 초과 위험 사전 판정

2. Signal Summary 구현
- 수집된 시계열에서 수익률/변동성/모멘텀 계산
- 사용자 리포트용 Markdown 통계 섹션 생성

3. Connector 도입 (순차)
- 국내(data.go/OpenDART) → 미국(SEC/FRED) → 보조(Alpha)
- 커넥터별 실패 시 폴백/캐시 반환

4. 파이프라인 통합
- 기존 `main.py`의 리포트 빌드 단계에 통계 섹션 추가
- 호출 버짓 가드로 무과금 한도 강제

---

## 8) 무과금 가능성 재검토

- 결론: "가능"
- 전제:
  - Alpha Vantage 호출을 일 25회 미만으로 제한
  - Naver DataLab 호출을 일 1,000회 미만으로 제한
  - OpenDART/SEC 과다호출 방지(분당/초당 가드)
  - 약관 제약 소스(KRX OpenAPI)는 제외

잔여 리스크:
- FRED 데이터 중 제3자 저작권 시리즈 사용 시 별도 확인 필요
- 특정 소스 정책 변경 가능성(분기별 약관 점검 필요)

---

## 9) 누락/구현성 최종 점검

체크리스트:
- [x] 무료한도 수치 기반 수집 가능성 검증
- [x] 재배포/상업성 리스크 소스 식별
- [x] 사용자 제공 통계 정의
- [x] 구현 단계와 검증 기준 정의

판단:
- 현재 정보 기준으로 구현 진행 가능
- 구현 시작 범위는 "정책 가드 + 통계 엔진"이 가장 리스크 대비 효과가 큼

---

## 10) 참고 링크

- data.go.kr 금융위 주식시세정보: https://www.data.go.kr/data/15094808/openapi.do
- data.go.kr 금융위 KRX상장종목정보: https://www.data.go.kr/data/15094775/openapi.do
- OpenDART 안내: https://opendart.fss.or.kr/intro/main.do
- OpenDART FAQ: https://opendart.fss.or.kr/cop/bbs/selectArticleList.do?bbsId=B0000000000000000002
- OpenDART 약관: https://opendart.fss.or.kr/intro/terms.do
- Naver DataLab API: https://developers.naver.com/docs/serviceapi/datalab/search/search.md
- SEC EDGAR API 안내: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC 접근 정책: https://www.sec.gov/about/developer-resources
- SEC 개발 FAQ: https://www.sec.gov/about/webmaster-frequently-asked-questions
- FRED API 키: https://fred.stlouisfed.org/docs/api/api_key.html
- FRED Terms: https://fred.stlouisfed.org/docs/api/terms_of_use.html
- Alpha Vantage 지원/한도: https://www.alphavantage.co/support/#api-key
- KRX OpenAPI 약관: https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp
- KOSIS OpenAPI 약관: https://kosis.kr/openapi/service_2.jsp
