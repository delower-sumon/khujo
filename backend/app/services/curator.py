import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from backend.app.models.search import SearchIndex

class Curator:
    """
    Curator service to index Bangladesh-relevant websites.
    """
    def __init__(self, db: Session):
        self.db = db

    def index_page(self, url: str, category: str):
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title = soup.title.string if soup.title else url
            content = soup.get_text()
            snippet = content[:200] + "..." # Basic snippet extraction
            
            # Check if already exists
            existing = self.db.query(SearchIndex).filter(SearchIndex.url == url).first()
            if existing:
                existing.title = title
                existing.content = content
                existing.snippet = snippet
                existing.category = category
            else:
                new_entry = SearchIndex(
                    title=title,
                    url=url,
                    content=content,
                    snippet=snippet,
                    source=url.split('/')[2],
                    category=category
                )
                self.db.add(new_entry)
            
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error indexing {url}: {e}")
            return False

    def run_batch_index(self, urls: list, category: str):
        results = []
        for url in urls:
            success = self.index_page(url, category)
            results.append({"url": url, "success": success})
        return results
