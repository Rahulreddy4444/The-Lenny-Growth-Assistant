FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install
COPY frontend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY frontend/ /app/frontend/

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit honoring $PORT
CMD ["sh", "-c", "streamlit run frontend/app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
