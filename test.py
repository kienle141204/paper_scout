import requests

arxiv_id = "1706.03762"
pdf_url = f"https://arxiv.org/pdf/2402.06196"

r = requests.get(pdf_url)
r.raise_for_status()

with open(f"{arxiv_id}.pdf", "wb") as f:
    f.write(r.content)