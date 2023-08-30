FROM python:3.10-slim-buster
COPY . /app
WORKDIR /app

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir streamlit
RUN python -m pip install -r requirements.txt
EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]