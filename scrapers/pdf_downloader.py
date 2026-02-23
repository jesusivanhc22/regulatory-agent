import requests
import os
import hashlib
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PDF_DIR = "data/pdfs"

os.makedirs(PDF_DIR, exist_ok=True)


def download_pdf(pdf_url):

    try:
        response = requests.get(pdf_url, verify=False, timeout=20)
    except Exception as e:
        print("Error descargando PDF:", e)
        return None, None

    if response.status_code != 200:
        print("Error HTTP descargando PDF:", response.status_code)
        return None, None

    file_hash = hashlib.sha256(response.content).hexdigest()
    file_path = os.path.join(PDF_DIR, f"{file_hash}.pdf")

    if not os.path.exists(file_path):
        with open(file_path, "wb") as f:
            f.write(response.content)

    return file_path, file_hash
