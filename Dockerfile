FROM jorineg/ibhelm-base:latest

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/

RUN mkdir -p logs

EXPOSE 5000

ENV SERVICE_NAME=teamworkmissiveconnector

CMD ["python", "-m", "src.app"]
