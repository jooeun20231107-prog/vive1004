# Event ON — Streamlit 행사 설계 플랫폼

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub + Streamlit Community Cloud
1. GitHub에 `app.py`, `requirements.txt`, `README.md`를 업로드합니다.
2. Streamlit Community Cloud에서 해당 저장소를 선택합니다.
3. Main file path에 `app.py`를 입력하고 Deploy를 누릅니다.

## 포함 기능
- 회원가입 / 로그인 및 프로필 관리
- 홈 화면에서 대시보드와 AI 보고서로 이동
- 행사 기본정보 10개 항목 입력
- 행사장 모형 선택 및 시설 배치도 생성
- 부스별 배치 이유 설명, 시설 위치 변경 및 초기화
- 작은 혼잡도 분석 패널에서 움직이는 방문객 시뮬레이션
- 보고서 미리보기 및 PDF 다운로드 (배치도 이미지 포함)
- 6개 설정 메뉴와 행사 프로젝트 저장/불러오기/삭제

## 한계 및 운영 전 확인
- AI 배치 설명은 현재 입력값과 규칙에 기반한 설명이며, 외부 생성형 AI API는 연결되어 있지 않습니다.
- 사람 움직임은 브라우저에서 재생되는 시뮬레이션이며 실제 현장 센서 기반 실시간 인원 데이터가 아닙니다.
- 행사장 배치도는 개념 설계용 도식이며 실제 도면/치수/법규 검토를 대체하지 않습니다.
- 기본 저장소는 SQLite 로컬 파일입니다. Streamlit Cloud의 재배포/재시작 환경에서 영구 보존을 보장하지 않으므로 실제 운영 시 Supabase/PostgreSQL 등 외부 데이터베이스 사용을 권장합니다.
- 비밀번호 해시는 기본 SHA-256 데모 구현입니다. 실제 상용 서비스에는 bcrypt/Argon2 및 추가 보안 조치가 필요합니다.
