FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir gradio pyreadstat pandas numpy

COPY app.py .

EXPOSE 7860

CMD ["python", "app.py"]
# rebuild Tue Jun  9 22:06:45 CEST 2026
