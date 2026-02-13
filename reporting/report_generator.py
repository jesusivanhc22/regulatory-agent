from datetime import datetime


def generate(results, batch_number=1):

    month = datetime.now().strftime("%Y_%m")
    filename = f"report_{month}_{batch_number}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write("# Reporte Regulatorio Mensual\n\n")

        for r in results:
            f.write(f"## {r['title']}\n")
            f.write(f"{r['analysis']}\n\n")

    return filename
