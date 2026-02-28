import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def fetch_content(url):

    # Si la URL apunta directamente a un PDF (COFEPRIS, SAT),
    # no hay pagina HTML intermedia.
    if url.lower().endswith('.pdf'):
        return None, url

    try:
        response = requests.get(url, verify=False, timeout=15)
    except Exception as e:
        print("Error descargando contenido:", e)
        return None, None

    if response.status_code != 200:
        return None, None

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    pdf_url = None

    for link in soup.find_all("a"):
        href = link.get("href")
        if href and ".pdf" in href.lower():
            if href.startswith("http"):
                pdf_url = href
            else:
                pdf_url = f"https://www.dof.gob.mx/{href}"
            break

    return html, pdf_url
