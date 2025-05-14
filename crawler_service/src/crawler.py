import requests
from bs4 import BeautifulSoup
import json
import time
import os
from typing import List, Dict
from urllib.parse import urljoin

class RealEstateCrawler:
    def __init__(self, base_url: str, output_dir: str):
        self.base_url = base_url
        self.output_dir = output_dir
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://batdongsan.com.vn/",
        }
        self.session = requests.Session()  # Sử dụng session để duy trì cookie
        os.makedirs(self.output_dir, exist_ok=True)

    def fetch_page(self, url: str) -> BeautifulSoup:
        """Lấy nội dung HTML của một trang và trả về BeautifulSoup object."""
        try:
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def extract_listings(self, soup: BeautifulSoup) -> List[Dict]:
        """Trích xuất thông tin bất động sản từ một trang."""
        listings = []
        # Giả định: danh sách bất động sản nằm trong thẻ div với class 'js__product-item'
        items = soup.select("div.js__product-item")
        for item in items:
            try:
                listing = {}
                # Tiêu đề
                title_elem = item.select_one("h3.js__product-title")
                listing["title"] = title_elem.text.strip() if title_elem else "N/A"
                # Giá
                price_elem = item.select_one("span.js__product-price")
                listing["price"] = price_elem.text.strip() if price_elem else "N/A"
                # Diện tích
                area_elem = item.select_one("span.js__product-area")
                listing["area"] = area_elem.text.strip() if area_elem else "N/A"
                # Vị trí
                location_elem = item.select_one("div.js__product-address")
                listing["location"] = location_elem.text.strip() if location_elem else "N/A"
                # Mô tả
                desc_elem = item.select_one("p.js__product-desc")
                listing["description"] = desc_elem.text.strip() if desc_elem else "N/A"
                # Link
                link_elem = item.select_one("a.js__product-link")
                listing["link"] = urljoin(self.base_url, link_elem["href"]) if link_elem else "N/A"
                listings.append(listing)
            except Exception as e:
                print(f"Error extracting listing: {e}")
        return listings

    def save_to_json(self, data: List[Dict], page: int):
        """Lưu dữ liệu vào file JSON."""
        output_file = os.path.join(self.output_dir, f"listings_page_{page}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(data)} listings to {output_file}")

    def crawl(self, max_pages: int = 3):
        """Thu thập dữ liệu từ nhiều trang."""
        for page in range(1, max_pages + 1):
            page_url = f"{self.base_url}?page={page}"
            print(f"Crawling page {page}: {page_url}")
            soup = self.fetch_page(page_url)
            if not soup:
                continue
            listings = self.extract_listings(soup)
            if listings:
                self.save_to_json(listings, page)
            else:
                print(f"No listings found on page {page}")
            time.sleep(5)  # Tăng thời gian chờ lên 5 giây

if __name__ == "__main__":
    crawler = RealEstateCrawler(
        base_url="https://batdongsan.com.vn/nha-dat-ban",
        output_dir="data"
    )
    crawler.crawl(max_pages=3)  # Thu thập 3 trang đầu tiên