FROM python:3.11

WORKDIR /app

# Create venv
RUN python -m venv /opt/venv

# Activate venv (set PATH)
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]