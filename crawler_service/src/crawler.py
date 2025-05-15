import requests
from bs4 import BeautifulSoup
import json
import time
import os
from typing import List, Dict
from urllib.parse import urljoin
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from mongo_client import MongoDBClient
import random

class RealEstateCrawler:
    def __init__(self, base_url: str, output_dir: str, use_mongo: bool = True):
        self.base_url = base_url
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        # Cấu hình undetected-chromedriver
        chrome_options = uc.ChromeOptions()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--start-maximized")
        self.driver = uc.Chrome(options=chrome_options)
        self.all_listings = []  # Lưu trữ tất cả listings trước khi ghi file
        # config mongodb client
        self.use_mongo = use_mongo
        if self.use_mongo:
            self.mongo_client = MongoDBClient(
                host="localhost",
                port=27017,
                username="admin",
                password="secretpassword",
                db_name="house_pricing_forecast"
            )

    def fetch_page(self, url: str, retries: int = 2) -> BeautifulSoup:
        """Lấy nội dung HTML của một trang bằng undetected-chromedriver với retry."""
        attempt = 0
        while attempt <= retries:
            try:
                print(f"Fetching URL: {url} (Attempt {attempt + 1}/{retries + 1})")
                self.driver.get(url)
                # Giả lập cuộn trang để tránh bị chặn
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(random.uniform(0.5, 1.5))  # Chờ ngẫu nhiên ngắn
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.js__card.js__card-full-web"))
                )
                html = self.driver.page_source
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("div.js__card.js__card-full-web")
                if not items:
                    print(f"No listings found in HTML for {url}")
                    with open(os.path.join(self.output_dir, f"error_page_{url.split('/')[-1]}.html"), "w", encoding="utf-8") as f:
                        f.write(html)
                return soup
            except TimeoutException as te:
                print(f"Timeout error fetching {url}: {te}")
                html = self.driver.page_source
                with open(os.path.join(self.output_dir, f"timeout_page_{url.split('/')[-1]}.html"), "w", encoding="utf-8") as f:
                    f.write(html)
                attempt += 1
                if attempt <= retries:
                    print(f"Retrying after random delay...")
                    time.sleep(random.uniform(2, 5))
                continue
            except WebDriverException as wde:
                print(f"WebDriver error fetching {url}: {wde}")
                html = self.driver.page_source
                with open(os.path.join(self.output_dir, f"webdriver_error_page_{url.split('/')[-1]}.html"), "w", encoding="utf-8") as f:
                    f.write(html)
                attempt += 1
                if attempt <= retries:
                    print(f"Retrying after random delay...")
                    time.sleep(random.uniform(2, 5))
                continue
            except Exception as e:
                print(f"Unexpected error fetching {url}: {e}")
                html = self.driver.page_source
                with open(os.path.join(self.output_dir, f"error_page_{url.split('/')[-1]}.html"), "w", encoding="utf-8") as f:
                    f.write(html)
                return None
        print(f"Failed to fetch {url} after {retries + 1} attempts")
        return None

    def extract_listings(self, soup: BeautifulSoup) -> List[Dict]:
        """Trích xuất thông tin bất động sản từ một trang."""
        listings = []
        items = soup.select("div.js__card.js__card-full-web")
        print(f"Found {len(items)} listing items")
        for item in items:
            try:
                listing = {}
                title_elem = item.select_one("span.js__card-title")
                listing["title"] = title_elem.text.strip() if title_elem else "N/A"
                price_elem = item.select_one("span.re__card-config-price.js__card-config-item")
                listing["price"] = price_elem.text.strip() if price_elem else "N/A"
                area_elem = item.select_one("span.re__card-config-area.js__card-config-item")
                listing["area"] = area_elem.text.strip() if area_elem else "N/A"
                price_per_m2_elem = item.select_one("span.re__card-config-price_per_m2.js__card-config-item")
                listing["price_per_m2"] = price_per_m2_elem.text.strip() if price_per_m2_elem else "N/A"
                bedroom_elem = item.select_one("span.re__card-config-bedroom.js__card-config-item")
                listing["bedrooms"] = bedroom_elem["aria-label"].strip() if bedroom_elem and bedroom_elem.has_attr("aria-label") else "N/A"
                toilet_elem = item.select_one("span.re__card-config-toilet.js__card-config-item")
                listing["bathrooms"] = toilet_elem["aria-label"].strip() if toilet_elem and toilet_elem.has_attr("aria-label") else "N/A"
                location_elem = item.select_one("div.re__card-location span:nth-child(2)")
                listing["location"] = location_elem.text.strip() if location_elem else "N/A"
                desc_elem = item.select_one("div.re__card-description.js__card-description")
                listing["description"] = desc_elem.text.strip() if desc_elem else "N/A"
                link_elem = item.select_one("a.js__product-link-for-product-id")
                listing["link"] = urljoin(self.base_url, link_elem["href"]) if link_elem and link_elem.has_attr("href") else "N/A"
                listings.append(listing)
            except Exception as e:
                print(f"Error extracting listing: {e}")
                continue
        return listings

    def save_to_json(self, file_index: int):
        """Lưu dữ liệu vào file JSON khi đủ 1000 phần tử."""
        output_file = os.path.join(self.output_dir, f"listings_batch_{file_index}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.all_listings[-1000:], f, ensure_ascii=False, indent=2)
        print(f"Saved {len(self.all_listings[-1000:])} listings to {output_file}")
    def save_to_mongo(self, listings):
        if self.use_mongo and listings:
            self.mongo_client.insert_listings(listings)
            print(f"Inserted {len(listings)} listings to MongoDB")

    def crawl(self, max_pages: int = 3):
        """Thu thập dữ liệu từ nhiều trang và lưu khi đủ 1000 phần tử."""
        file_index = 1
        for page in range(1, max_pages + 1):
            page_url = f"{self.base_url}/p{page}" if page > 1 else self.base_url
            print(f"Crawling page {page}: {page_url}")
            soup = self.fetch_page(page_url)
            if not soup:
                print(f"Failed to fetch page {page}")
                continue
            listings = self.extract_listings(soup)
            if listings:
                self.all_listings.extend(listings)
                print(f"Total listings collected: {len(self.all_listings)}")
                # Lưu khi đủ 1000 phần tử (luồng cũ lưu vào json)
                # while len(self.all_listings) >= 1000:
                #     self.save_to_json(file_index)
                #     self.all_listings = self.all_listings[1000:]  # Giữ phần còn lại
                #     file_index += 1
                self.save_to_mongo(listings)
                print(f"Total listings collected: {len(self.all_listings)}")
            else:
                print(f"No listings found on page {page}")
            time.sleep(random.uniform(1, 2))  # Chờ ngẫu nhiên ngắn giữa các trang
        # Lưu các phần tử còn lại (nếu có)
        if self.all_listings:
            self.save_to_json(file_index)
            print(f"Saved remaining {len(self.all_listings)} listings to batch {file_index}")
        else:
            print("No remaining listings to save")

    def __del__(self):
        """Đóng driver khi hoàn tất."""
        self.driver.quit()

if __name__ == "__main__":
    crawler = RealEstateCrawler(
        base_url="https://batdongsan.com.vn/nha-dat-ban",
        output_dir="../data"
    )
    crawler.crawl(max_pages=9341)