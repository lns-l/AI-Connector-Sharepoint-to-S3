import json
import os
import requests
import boto3
from msal import ConfidentialClientApplication
from PyPDF2 import PdfReader
from datetime import datetime, timezone
from dotenv import load_dotenv

# --- CARREGA VARIÁVEIS DE AMBIENTE ---
load_dotenv()

# --- CONFIGURAÇÕES A PARTIR DO .env ---
TENANT_ID = os.getenv('TENANT_ID')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')

SHAREPOINT_SITE = os.getenv('SHAREPOINT_SITE')
SITE_PATH = os.getenv('SITE_PATH')
DRIVE_NAME = os.getenv('DRIVE_NAME', 'Documents')

AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
S3_BUCKET = os.getenv('S3_BUCKET')
S3_PREFIX = os.getenv('S3_PREFIX', 'sharepoint-export/')
LOCAL_TEMP_DIR = os.getenv('LOCAL_TEMP_DIR', 'temp_pdfs')
GENERATE_PATH = os.getenv('GENERATE_PATH')

# --- AUTENTICAÇÃO GRAPH ---
def get_access_token():
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app = ConfidentialClientApplication(CLIENT_ID, authority=authority, client_credential=CLIENT_SECRET)
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result['access_token']

# --- IDENTIFICA O DRIVE ID ---
def get_drive_id(token):
    headers = {'Authorization': f'Bearer {token}'}
    site_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_SITE}:{SITE_PATH}"
    site_resp = requests.get(site_url, headers=headers).json()
    site_id = site_resp['id']

    drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    drives = requests.get(drives_url, headers=headers).json()

    for drive in drives.get('value', []):
        if drive['name'] == DRIVE_NAME:
            return drive['id']
    return None

# --- BAIXA ARQUIVO PDF ---
def download_pdf_graph(drive_id, item_id, filename, token):
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"
    headers = {
        'Authorization': f'Bearer {token}',
        'User-Agent': 'MicrosoftGraphClient/1.0'
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        content_type = response.headers.get('Content-Type', '')
        if 'application/pdf' not in content_type:
            print(f"⚠️ Ignorado: {filename} — não é PDF ({content_type})")
            return False

        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✅ PDF salvo: {filename}")
        return True

    print(f"❌ Erro ao baixar PDF ({filename}) - Status: {response.status_code}")
    return False

# --- LÊ O JSON MAIS RECENTE DE UMA PASTA ---
def read_latest_local_json():
    folder = GENERATE_PATH
    if not os.path.isdir(folder):
        raise NotADirectoryError(f"❌ Pasta inválida definida em GENERATE_PATH: {folder}")
    
    json_files = [f for f in os.listdir(folder) if f.endswith('.json')]
    if not json_files:
        raise FileNotFoundError(f"❌ Nenhum arquivo .json encontrado em: {folder}")

    json_files.sort(key=lambda f: os.path.getmtime(os.path.join(folder, f)), reverse=True)
    latest_path = os.path.join(folder, json_files[0])

    print(f"📂 Usando JSON local mais recente: {latest_path}")
    with open(latest_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- CONVERTE PDF PARA JSON ---
def convert_pdf_to_json(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = ''
        for page in reader.pages:
            text += page.extract_text() or ''
        return {
            'filename': os.path.basename(pdf_path),
            'content': text.strip()
        }
    except Exception as e:
        print(f"❌ Erro ao ler PDF {pdf_path}: {e}")
        return None

# --- FAZ UPLOAD DO JSON PARA O S3 ---
def upload_to_s3(file_path, s3_key):
    s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)
    try:
        s3.upload_file(file_path, S3_BUCKET, s3_key)
        print(f"☁️  Enviado ao S3: s3://{S3_BUCKET}/{s3_key}")
    except Exception as e:
        print(f"❌ Erro ao fazer upload para o S3: {e}")

# --- PIPELINE FINAL ---
def main():
    os.makedirs(LOCAL_TEMP_DIR, exist_ok=True)
    token = get_access_token()
    drive_id = get_drive_id(token)
    data = read_latest_local_json()

    for doc in data:
        name = doc.get('name')
        item_id = doc.get('id')
        if name and item_id and name.lower().endswith('.pdf'):
            local_pdf_path = os.path.join(LOCAL_TEMP_DIR, name)
            if download_pdf_graph(drive_id, item_id, local_pdf_path, token):
                json_data = convert_pdf_to_json(local_pdf_path)
                if json_data:
                    json_filename = os.path.splitext(name)[0] + '.json'
                    local_json_path = os.path.join(LOCAL_TEMP_DIR, json_filename)
                    with open(local_json_path, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=2)

                    s3_key = f"{S3_PREFIX}{json_filename}"
                    upload_to_s3(local_json_path, s3_key)

    print(f"\n✅ Conversão e upload finalizados para todos os PDFs.")

if __name__ == "__main__":
    main()
