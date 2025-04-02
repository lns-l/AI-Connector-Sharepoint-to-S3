import os
import requests
import json
import boto3
from botocore.config import Config
from botocore.exceptions import NoCredentialsError
from msal import ConfidentialClientApplication
from datetime import datetime, timezone
from dotenv import load_dotenv

# --- CARREGA VARIÁVEIS DO .env ---
load_dotenv()

# --- CONFIGURAÇÕES DO SHAREPOINT ---
TENANT_ID = os.getenv('TENANT_ID')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
SHAREPOINT_SITE = os.getenv('SHAREPOINT_SITE')
SITE_PATH = os.getenv('SITE_PATH')
DRIVE_NAME = os.getenv('DRIVE_NAME', 'Documents')

# --- CONFIGURAÇÕES DO S3 ---
S3_BUCKET_NAME = os.getenv('S3_BUCKET')
S3_JSON_FOLDER = os.getenv('S3_JSON_FOLDER', 'JSON Master')
FINAL_JSON_FILENAME = os.getenv('FINAL_JSON_FILENAME', 'sharepoint_data.json')
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')

# --- CAMINHOS LOCAIS ---
GENERATE_PATH = os.getenv('GENERATE_PATH', './jsons')
LOCAL_PATH = os.getenv('LOCAL_TEMP_DIR', '/tmp')

# --- INTERVALOS DE EXECUÇÃO ---
STEP1_INTERVAL = int(os.getenv('STEP1_INTERVAL', 600))
STEP2_INTERVAL = int(os.getenv('STEP2_INTERVAL', 900))

# --- VALIDAÇÃO DAS CREDENCIAIS AWS ---
if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
    raise EnvironmentError("❌ Variáveis AWS_ACCESS_KEY e/ou AWS_SECRET_KEY não foram encontradas. Verifique seu .env")

# --- AUTENTICAÇÃO NO GRAPH ---
def get_access_token():
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app = ConfidentialClientApplication(CLIENT_ID, authority=authority, client_credential=CLIENT_SECRET)
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result['access_token']

# --- OBTÉM DRIVE ID DO SITE ---
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

# --- LISTA OS ARQUIVOS NO DRIVE ---
def list_files(token, drive_id):
    headers = {'Authorization': f'Bearer {token}'}
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
    resp = requests.get(url, headers=headers).json()
    return resp.get('value', [])

# --- SALVA LOCALMENTE ---
def save_locally(data, filename, path):
    os.makedirs(path, exist_ok=True)
    filepath = os.path.join(path, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Arquivo salvo localmente: {filepath}")
    return filepath

# --- ENVIA PARA O S3 ---
def upload_to_s3(filepath, bucket_name, s3_folder, filename):
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            config=Config(region_name='us-east-1')
        )
        s3_key = f"{s3_folder}/{filename}"
        s3_client.upload_file(filepath, bucket_name, s3_key)
        print(f"✅ Arquivo enviado ao S3: s3://{bucket_name}/{s3_key}")
    except NoCredentialsError:
        print("❌ Erro: Credenciais AWS não encontradas. Verifique seu .env.")

# --- MAIN ---
def main():
    token = get_access_token()
    drive_id = get_drive_id(token)

    if not drive_id:
        print("❌ Drive não encontrado.")
        return

    files = list_files(token, drive_id)
    structured_data = []

    for file in files:
        item = {
            "name": file.get('name'),
            "id": file.get('id'),
            "webUrl": file.get('webUrl'),
            "size": file.get('size'),
            "lastModified": file.get('lastModifiedDateTime'),
            "createdBy": file.get('createdBy', {}).get('user', {}).get('displayName'),
        }
        structured_data.append(item)

    filepath = save_locally(structured_data, FINAL_JSON_FILENAME, GENERATE_PATH)
    upload_to_s3(filepath, S3_BUCKET_NAME, S3_JSON_FOLDER, FINAL_JSON_FILENAME)

if __name__ == "__main__":
    main()
