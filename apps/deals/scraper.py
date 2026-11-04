import requests
from bs4 import BeautifulSoup

def fetch_deal_info(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extraction du titre
        title = soup.find('title').get_text(strip=True) if soup.find('title') else ''
        if title:
            title = title.split('|')[0].strip()

        # Extraction de l'image (via la balise standard Open Graph)
        image_url = ''
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = og_image['content']

        return {
            'success': True,
            'title': title,
            'url': url,
            'image_url': image_url,  # Le scraper renvoie maintenant l'URL de l'image
            'price': '',
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
