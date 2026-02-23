import pdfplumber
from bs4 import BeautifulSoup


MAX_CHARS = 30000  # ampliamos un poco el límite


def clean_html(soup):
    """
    Elimina scripts y estilos para evitar ruido.
    """
    for tag in soup(["script", "style", "header", "footer", "nav"]):
        tag.decompose()

    return soup


def extract_from_html(raw_html):

    try:
        soup = BeautifulSoup(raw_html, "html.parser")
        soup = clean_html(soup)

        text = soup.get_text(separator=" ", strip=True)

        return text[:MAX_CHARS]

    except Exception as e:
        print("Error extrayendo texto HTML:", e)
        return ""


def extract_from_pdf(pdf_path):

    text = ""
    extracted_pages = 0

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:

                page_text = page.extract_text()

                if page_text:
                    text += page_text + "\n"
                    extracted_pages += 1

    except Exception as e:
        print("Error extrayendo texto PDF:", e)
        return ""

    # Si no se extrajo nada, probablemente es PDF escaneado
    if extracted_pages == 0:
        print("Advertencia: PDF posiblemente escaneado (sin texto digital).")
        return ""

    return text[:MAX_CHARS]
