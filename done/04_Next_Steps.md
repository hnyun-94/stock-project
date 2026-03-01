# 개발 착수 및 진행 계획 (Next Steps)

요구사항 구체화가 완료되었으므로, 다음 스텝으로 아래 모듈들을 **병렬적**으로 개발 진행합니다.

1. **지수 데이터 수집기 (Index Crawler)**
   - 코스피, 코스닥 지수 수치 크롤링
   - 상승/하락 등락 종목 수 스크래핑

2. **뉴스 및 동향 파이프라인 (News/Trend Crawler)**
   - `pytrends` 등으로 검색 트렌드 추출
   - 관심 키워드 기반 네이버 관련 뉴스 검색기 개발
   - 디시인사이드 식갤 인기글 제목 스크래퍼 (우회 적용 고려)

3. **Notion Database 연동 커넥터**
   - 발급받은 `NOTION_TOKEN`과 `DATABASE_ID`로부터 사용자 목록(Email)과 관심 키워드(Tags)를 가져오는 모듈

4. **Gemini AI 프롬프트 체인 (Summarizer)**
   - 위 데이터들을 합쳐 컨텍스트를 구성하고, `03_Report_Format_Design`의 양식대로 출력하도록 프롬프트 작성 및 API 호출 연동
