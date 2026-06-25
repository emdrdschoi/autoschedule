@echo off
echo 스케줄러 시작 중...

:: 현재 배치 파일 위치로 이동
cd /d "%~dp0"

:: streamlit 설치 확인 후 없으면 설치
python -c "import streamlit" 2>nul
if %errorlevel% neq 0 (
    echo 필요한 패키지를 설치합니다...
    pip install -r requirements.txt
)

:: 브라우저에서 자동으로 열기
start http://localhost:8501

:: 앱 실행
streamlit run app.py

pause
