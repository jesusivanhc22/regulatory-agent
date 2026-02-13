import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://www.dof.gob.mx"


def fetch_dof():

    publications = []

    print("Accediendo a portada DOF...")

    try:
        response = requests.get(BASE_URL, verify=False, timeout=10)
    except Exception as e:
        print("Error accediendo al DOF:", e)
        return publications

    if response.status_code != 200:
        print("Error: status", response.status_code)
        return publications

    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a"):

        title = link.get_text(strip=True)
        href = link.get("href")

        if not href or not title:
            continue

        if "nota_detalle.php" not in href:
            continue

        if not href.startswith("http"):
            full_url = f"{BASE_URL}/{href}"
        else:
            full_url = href

        publications.append({
            "title": title,
            "url": full_url
        })

    print(f"Publicaciones detectadas en portada: {len(publications)}")

    return publications
