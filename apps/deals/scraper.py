import requests
from bs4 import BeautifulSoup

def fetch_deal_info(url):
    try:
        # On se fait passer pour un navigateur pour ne pas être bloqué par les sites
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # On tente de récupérer le titre de la page
        title = soup.find('title').get_text(strip=True) if soup.find('title') else ''
        if title:
            # On nettoie souvent le titre (ex: "Produit X | Amazon" devient "Produit X")
            title = title.split('|')[0].strip()

        return {
            'success': True,
            'title': title,
            'url': url,
            'price': '', # L'extraction du prix est complexe, on la laisse vide pour l'instant
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
