FROM python:3.12-slim
WORKDIR /app
COPY mcp_servers/serpapi-mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mcp_servers/serpapi-mcp/server.py .
EXPOSE 8080
CMD ["python", "server.py"]
