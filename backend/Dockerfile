FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /backend

# 시스템 패키지 업데이트 및 필요한 빌드 도구 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /backend/
RUN pip install -r requirements.txt

# 요구사항 파일 복사 및 파이썬 패키지 설치
COPY requirements.txt /backend/
RUN pip install --upgrade pip && pip install -r requirements.txt

# 앱 소스 코드 복사
COPY . /backend/

# 디버깅을 위해 파이썬 출력에 대해 버퍼링하지 않고 즉시 출력하도록 환경변수 설정
ENV PYTHONUNBUFFERED=1

# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
#CMD sh -c "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"
CMD sh -c "python manage.py migrate && uvicorn backend.asgi:application --host 0.0.0.0 --port 8000"