FROM python:3.10-slim-buster

# install streamlit
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir streamlit
# install requirements
WORKDIR /app
COPY ./requirements.txt /app
RUN python -m pip install -r requirements.txt
# coppy the code
COPY . /app

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
