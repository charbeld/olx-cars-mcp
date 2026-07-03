FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY olx_cars_mcp ./olx_cars_mcp
RUN pip install --no-cache-dir .
ENV PYTHONUNBUFFERED=1
# Most PaaS inject $PORT; the server honours it (defaults to 8000).
EXPOSE 8000
CMD ["olx-cars-mcp", "--http"]
