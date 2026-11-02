FROM python:3.12-slim

# Evita arquivos .pyc e garante logs em tempo real (unbuffered)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Executa por padrão o robô em modo contínuo (daemon)
ENTRYPOINT ["python", "main.py"]
CMD ["daemon", "--interval", "30"]
