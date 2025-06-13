import requests
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}"
}

# Substitua 'jobs' se o nome da sua tabela for diferente
response = requests.get(f"{url}/rest/v1/jobs?select=*", headers=headers)

print("Status:", response.status_code)
print("Response:", response.text)