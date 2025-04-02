# Integração SharePoint ➜ S3 com Docker Compose

Este projeto executa dois processos automatizados em containers distintos, com comunicação via volume compartilhado:

1. **`generate_json_master.py`** — extrai metadados de arquivos do SharePoint e os salva localmente em `.json`.
2. **`sharepoint_pdf_to_s3_json.py`** — lê os `.json`, baixa PDFs, converte para texto e envia para o S3.

---

## 📁 Estrutura de Diretórios

```
.
├── compose.yaml                # Docker Compose com dois containers
├── Dockerfile                  # Imagem base comum aos dois serviços
├── .env                        # Variáveis de ambiente e agendamento
├── requirements.txt            # Dependências Python
├── generate_json_master.py     # Script 1
├── sharepoint_pdf_to_s3_json.py# Script 2
├── export_sharepoint/          # Pasta onde JSONs são gerados
└── temp_pdfs/                  # Pasta temporária para PDFs e JSONs convertidos
```

---

## ⚙️ Variáveis de Ambiente (.env)

Exemplo:

```env
# Intervalos de execução (em segundos)
STEP1_INTERVAL=600         # a cada 10 minutos
STEP2_INTERVAL=900         # a cada 15 minutos

# SharePoint
TENANT_ID=seu-tenant-id
CLIENT_ID=seu-client-id
CLIENT_SECRET=sua-chave
SHAREPOINT_SITE=seusite.sharepoint.com
SITE_PATH=/sites/seusite
DRIVE_NAME=Documents

# AWS S3
AWS_ACCESS_KEY=sua-chave-aws
AWS_SECRET_KEY=sua-chave-secreta-aws
S3_BUCKET=seu-bucket
S3_PREFIX=sharepoint-export/

# Pastas compartilhadas
GENERATE_PATH=./export_sharepoint
LOCAL_TEMP_DIR=./temp_pdfs
```

---

## 🚀 Como Executar

1. **Clone ou extraia os arquivos em uma pasta local:**

2. **Configure o arquivo `.env` com seus dados de autenticação.**

3. **Execute os containers com:**

```bash
docker compose -f compose.yaml up --build -d
```

4. **Acompanhe os logs (opcional):**

```bash
docker logs -f generate_json
docker logs -f upload_s3
```

---

## 🔁 Funcionamento Automático

- O container `generate_json` executa o primeiro script conforme o `STEP1_INTERVAL`.
- O container `upload_s3` verifica se há JSONs em `export_sharepoint/`. Se houver, executa o segundo script, e aguarda conforme `STEP2_INTERVAL`.

---

## ✅ Requisitos

- Docker e Docker Compose instalados
- Acesso à API do Microsoft Graph
- Bucket e credenciais válidas da AWS S3

---

## ❓ Dúvidas ou melhorias?

Sinta-se à vontade para adaptar os tempos, caminhos, ou integrar logs com ferramentas como Grafana, CloudWatch ou ELK Stack.

---

Desenvolvido para facilitar o fluxo automático de dados entre SharePoint e S3 via JSON e PDF.
