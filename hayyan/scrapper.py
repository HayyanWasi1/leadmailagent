import time
import json
import re
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException, NoSuchElementException

from bs4 import BeautifulSoup
import random
import zipfile
import os
import tempfile

try:
    from fake_useragent import UserAgent
    ua = UserAgent()
    print("✅ fake_useragent library loaded")
except ImportError:
    print("⚠️ fake_useragent not installed. Using static user agents.")
    print("💡 Install with: pip install fake-useragent")
    ua = None

def click_next_page(driver, attempts=8, sleep_between=0.6):
    """
    Robustly try to click the Next (a.bm_rightChevron) control.
    Returns True if clicked, False otherwise.
    """
    for attempt in range(attempts):
        try:
            candidates = driver.find_elements(By.CSS_SELECTOR, "a.bm_rightChevron")
            next_btn = None
            for c in candidates:
                try:
                    style = (c.get_attribute("style") or "").lower()
                    if c.is_displayed() and "display: none" not in style:
                        next_btn = c
                        break
                except StaleElementReferenceException:
                    continue

            if not next_btn:
                time.sleep(sleep_between)
                continue

            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", next_btn)
                time.sleep(0.12)
            except Exception:
                pass

            try:
                next_btn.click()
                time.sleep(0.6)
                return True
            except (ElementClickInterceptedException, StaleElementReferenceException):
                pass

            try:
                ActionChains(driver).move_to_element(next_btn).pause(0.05).click(next_btn).perform()
                time.sleep(0.6)
                return True
            except Exception:
                pass

            try:
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(0.6)
                return True
            except Exception:
                pass

            try:
                driver.execute_script(
                    "var e = new MouseEvent('mousedown', {bubbles:true}); arguments[0].dispatchEvent(e);"
                    "e = new MouseEvent('mouseup', {bubbles:true}); arguments[0].dispatchEvent(e);"
                    "e = new MouseEvent('click', {bubbles:true}); arguments[0].dispatchEvent(e);",
                    next_btn
                )
                time.sleep(0.6)
                return True
            except Exception:
                pass

        except Exception:
            time.sleep(sleep_between)

    return False


class HeaderManager:
    def __init__(self):
        self.static_user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0',
        ]
    
    def get_random_user_agent(self):
        """Get a random user agent"""
        if ua:
            try:
                return ua.random
            except:
                return random.choice(self.static_user_agents)
        else:
            return random.choice(self.static_user_agents)
    
    def get_chrome_user_agent(self):
        """Get a Chrome-specific user agent"""
        if ua:
            try:
                return ua.chrome
            except:
                chrome_agents = [agent for agent in self.static_user_agents if 'Chrome' in agent]
                return random.choice(chrome_agents)
        else:
            chrome_agents = [agent for agent in self.static_user_agents if 'Chrome' in agent]
            return random.choice(chrome_agents)
    
    def get_enhanced_headers(self, user_agent=None):
        """Get enhanced headers with random user agent"""
        if not user_agent:
            user_agent = self.get_random_user_agent()
        
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
        }
        
        print(f"🎭 Using User-Agent: {user_agent[:50]}...")
        return headers
    
    def get_selenium_options_with_headers(self, chrome_options):
        """Add headers to Chrome options"""
        user_agent = self.get_chrome_user_agent()
        chrome_options.add_argument(f'--user-agent={user_agent}')
        
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-translate')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-features=TranslateUI')
        chrome_options.add_argument('--disable-ipc-flooding-protection')
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        print(f"🎭 Chrome User-Agent: {user_agent[:50]}...")
        return chrome_options

header_manager = HeaderManager()

SCRAPER_API_KEY = "958066978da9034c6e1153e33450f0cf"
SCRAPER_API_URL = "https://api.scraperapi.com/"

class ProxyManager:
    def __init__(self, api_key):
        self.api_key = api_key
        self.current_proxy = None
        self.proxy_extension_path = None
        
    def create_proxy_auth_extension(self):
        """Create Chrome extension for proxy authentication"""
        proxy_host = "proxy-server.scraperapi.com"
        proxy_port = "8001"
        proxy_user = "scraperapi"
        proxy_pass = self.api_key
        
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version":"22.0.0"
        }
        """
        
        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{proxy_host}",
                    port: parseInt({proxy_port})
                }},
                bypassList: ["localhost"]
            }}
        }};
        
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
        
        function callbackFn(details) {{
            return {{
                authCredentials: {{
                    username: "{proxy_user}",
                    password: "{proxy_pass}"
                }}
            }};
        }}
        
        chrome.webRequest.onAuthRequired.addListener(
            callbackFn,
            {{urls: ["<all_urls>"]}},
            ['blocking']
        );
        """
        
        temp_dir = tempfile.mkdtemp()
        extension_dir = os.path.join(temp_dir, "proxy_auth_extension")
        os.makedirs(extension_dir, exist_ok=True)
        
        with open(os.path.join(extension_dir, "manifest.json"), "w") as f:
            f.write(manifest_json)
        
        with open(os.path.join(extension_dir, "background.js"), "w") as f:
            f.write(background_js)
        
        extension_zip = os.path.join(temp_dir, "proxy_auth_extension.zip")
        with zipfile.ZipFile(extension_zip, 'w') as zip_file:
            zip_file.write(os.path.join(extension_dir, "manifest.json"), "manifest.json")
            zip_file.write(os.path.join(extension_dir, "background.js"), "background.js")
        
        self.proxy_extension_path = extension_zip
        self.current_proxy = f"{proxy_host}:{proxy_port}"
        
        print(f"✅ Created proxy authentication extension")
        print(f"🔄 Proxy: {self.current_proxy}")
        print(f"🔐 Authentication: {proxy_user}:*** (via extension)")
        
        return extension_zip
    
    def configure_selenium_with_extension(self):
        """Configure Chrome with proxy authentication extension"""
        chrome_options = Options()
        
        extension_path = self.create_proxy_auth_extension()
        chrome_options.add_extension(extension_path)
        
        chrome_options = header_manager.get_selenium_options_with_headers(chrome_options)
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--ignore-certificate-errors')
        
        return chrome_options
    
    def configure_selenium_without_proxy(self):
        """Configure Chrome without proxy (fallback)"""
        chrome_options = Options()
        
        chrome_options = header_manager.get_selenium_options_with_headers(chrome_options)
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        self.current_proxy = "Direct Connection (No Proxy)"
        print(f"🔄 Connection: {self.current_proxy}")
        
        return chrome_options
    
    def get_scraperapi_url(self, target_url):
        """Convert regular URL to ScraperAPI URL for requests"""
        scraperapi_url = f"http://api.scraperapi.com?api_key={self.api_key}&url={target_url}"
        return scraperapi_url
    
    def make_scraperapi_request(self, url, timeout=10):
        """Make request using ScraperAPI direct URL method with headers"""
        try:
            scraperapi_url = self.get_scraperapi_url(url)
            headers = header_manager.get_enhanced_headers()
            
            print(f"🌐 Making ScraperAPI request to: {url}")
            print(f"🔄 Using: ScraperAPI Direct URL")
            
            response = requests.get(scraperapi_url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                print(f"✅ ScraperAPI request successful")
                return response
            else:
                print(f"⚠️ ScraperAPI request failed with status: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ ScraperAPI request failed: {str(e)}")
            return None
    
    def cleanup(self):
        """Clean up temporary extension files"""
        if self.proxy_extension_path and os.path.exists(self.proxy_extension_path):
            try:
                os.remove(self.proxy_extension_path)
                print("🧹 Cleaned up proxy extension files")
            except:
                pass

proxy_manager = ProxyManager(SCRAPER_API_KEY)

def clean_email_raw(e: str) -> str:
    e = e.strip().strip('.,;:"\'<>[]{} ')
    if '@' not in e:
        return e
    if any(char.isdigit() for char in e.split('@')[0]):
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', e)
        if email_match:
            return email_match.group(0)
    return e

def extract_phone_number_comprehensive(panel_text):
    """
    Enhanced phone number extraction with multiple patterns
    """
    text = re.sub(r'\s+', ' ', panel_text)
    
    phone_patterns = [
        r'\+44\s?\d{4}\s?\d{6}',         
        r'\+44\s?\d{3}\s?\d{3}\s?\d{4}',   
        r'\+44\s?\d{2}\s?\d{4}\s?\d{4}',   


        r'\b0\d{4}\s?\d{6}\b',             
        r'\b0\d{3}\s?\d{3}\s?\d{4}\b',     
        r'\b0\d{2}\s?\d{4}\s?\d{4}\b',     
        r'\b0\d{10}\b',                            
        r'\b07\d{9}\b',                   
        r'\b07\d{3}\s?\d{6}\b',           
        r'\b07\d{3}\s?\d{3}\s?\d{3}\b',   
        
        r'\+\d{1,3}\s?\d{3,4}\s?\d{3,4}\s?\d{3,4}',
        
        r'\b\d{3,4}[-.\s]\d{3,4}[-.\s]\d{3,4}\b',
        r'\b\d{4,5}[-.\s]\d{6,7}\b',
        
        r'\(\d{3,5}\)\s?\d{6,8}',        
        
        r'\b\d{3,5}[-.\s]?\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{0,4}\b'
    ]
    
    found_numbers = []
    
    for pattern in phone_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            cleaned = re.sub(r'[^\d+]', '', match)
            if len(cleaned) >= 10: 
                found_numbers.append(match.strip())
    
    unique_numbers = []
    for num in found_numbers:
        if num not in unique_numbers:
            unique_numbers.append(num)
    
    return unique_numbers

def extract_emails_from_soup(soup: BeautifulSoup) -> list:
    email_pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    emails = []

    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.lower().startswith('mailto:'):
            raw_email = href.split(':', 1)[1].split('?')[0]
            cleaned = clean_email_raw(raw_email)
            if cleaned and cleaned not in emails:
                emails.append(cleaned)

    candidate_areas = []
    footers = soup.find_all('footer')
    for f in footers:
        candidate_areas.append(f.get_text(" ", strip=True))

    contact_classes = ['footer', 'contact', 'contact-us', 'site-info', 'copyright']
    for cls in contact_classes:
        contact_elements = soup.find_all(class_=re.compile(cls, re.I))
        for ce in contact_elements:
            candidate_areas.append(ce.get_text(" ", strip=True))

    for text in candidate_areas:
        found_emails = re.findall(email_pattern, text)
        for email in found_emails:
            cleaned = clean_email_raw(email)
            if cleaned and cleaned not in emails:
                emails.append(cleaned)

    if not emails:
        text = soup.get_text(" ", strip=True)
        found_emails = re.findall(email_pattern, text)
        for email in found_emails:
            cleaned = clean_email_raw(email)
            if cleaned and cleaned not in emails:
                emails.append(cleaned)

    return emails

def get_clean_website_name_from_title(driver) -> str:
    soup = BeautifulSoup(driver.page_source, "html.parser")
    raw_title = soup.title.string.strip() if soup.title else "No Title Found"

    unwanted_patterns = [
        r"\bhas closed\b",
        r"\bwelcome to\b",
        r"\bhome\b",
        r"\b-.*$",
        r"\|.*$",
    ]
    clean_title = raw_title
    for pattern in unwanted_patterns:
        clean_title = re.sub(pattern, "", clean_title, flags=re.IGNORECASE).strip()

    return clean_title

def find_emails_on_website(driver, max_pages=3):
    """Enhanced email finding with proxy support"""
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    emails = extract_emails_from_soup(soup)
    if emails:
        return emails

    links_checked = 0
    anchors = driver.find_elements(By.TAG_NAME, "a")
    for link in anchors:
        href = link.get_attribute("href")
        text = (link.text or "").lower()

        if href and any(kw in href.lower() or kw in text for kw in ["contact", "about", "support", "connect", "mail"]):
            try:
                print(f"🔗 Visiting: {href}")
                driver.get(href)
                time.sleep(2)  # proxy +1
                links_checked += 1
                html = driver.page_source
                soup = BeautifulSoup(html, "html.parser")
                new_emails = extract_emails_from_soup(soup)
                for email in new_emails:
                    if email not in emails:
                        emails.append(email)
            except Exception as e:
                print(f"❌ Error visiting {href}: {str(e)}")

            if links_checked >= max_pages:
                break

    return emails

def create_driver_with_proxy():
    """Create Chrome driver with proxy configuration"""
    print("🚀 Initializing Chrome driver...")
    
    approaches = [
        ("Chrome Extension Proxy", "extension"),
        ("Direct Connection", "direct"),
    ]
    
    for approach_name, approach_type in approaches:
        try:
            print(f"🔄 Trying {approach_name}...")
            
            if approach_type == "extension":
                chrome_options = proxy_manager.configure_selenium_with_extension()
            else:  
                chrome_options = proxy_manager.configure_selenium_without_proxy()
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.maximize_window()
            
            try:
                print("🔍 Testing connection...")
                driver.get("https://httpbin.org/ip")
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                print(f"✅ {approach_name} successful!")
                return driver
            except Exception as test_error:
                print(f"❌ {approach_name} test failed: {str(test_error)}")
                driver.quit()
                continue
                
        except Exception as e:
            print(f"❌ {approach_name} setup failed: {str(e)}")
            continue
    
    raise Exception("All connection methods failed")

print("=" * 60)
print("🕷️  ENHANCED WEB SCRAPER WITH ROTATING PROXIES")
print("=" * 60)
print(f"🔑 ScraperAPI Key: {SCRAPER_API_KEY[:10]}...")
print(f"🌐 Proxy URL: {SCRAPER_API_URL}")
print("=" * 60)

query = input("Enter what you want to search: ")
max_businesses = int(input("How many businesses do you want to scrape? "))

driver = create_driver_with_proxy()

try:
    print(f"\n🔍 Searching for: {query}")
    print(f"📊 Target businesses: {max_businesses}")
    
    print("🗺️  Opening Bing Maps...")
    driver.get(f"https://www.bing.com/maps?q={query}")
    
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "mapContainer"))
    )
    time.sleep(3)

    print("📜 Loading listings...")
    body = driver.find_element(By.TAG_NAME, "body")
    for _ in range(10):
        body.send_keys(Keys.PAGE_DOWN)
        time.sleep(0.5)
    
    results = []
    page_count = 0
    total_processed = 0

    while total_processed < max_businesses:
        page_count += 1
        print(f"\n📑 Processing page {page_count}")
        print(f"📊 Progress: {total_processed}/{max_businesses} businesses collected")

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a.listings-item'))
            )
        except TimeoutException:
            print("⚠️ No more listings found")
            break


        # body = driver.find_element(By.TAG_NAME, "body")
        # for _ in range(10):
        #     body.send_keys(Keys.PAGE_DOWN)
        #     time.sleep(0.3)
        # Get current page listings with retry mechanism
        listings = []
        retry_count = 0
        max_retries = 3
        
        while not listings and retry_count < max_retries:
            listings = driver.find_elements(By.CSS_SELECTOR, 'a.listings-item')
            if not listings:
                print(f"🔄 No listings found, retrying... ({retry_count + 1}/{max_retries})")
                time.sleep(2)
                body = driver.find_element(By.TAG_NAME, "body")
                for i in range(5):
                    body.send_keys(Keys.PAGE_DOWN)
                    time.sleep(0.3)
                retry_count += 1
        
        if not listings:
            print("⚠️ No listings found after retries, moving to next page or ending")
            continue
            
        print(f"📋 Found {len(listings)} listings on this page")
        print(f"🎯 Need to process {min(len(listings), max_businesses - total_processed)} from this page")

        listings = driver.find_elements(By.CSS_SELECTOR, 'a.listings-item')
        print(f"📋 Found {len(listings)} listings on this page")


        listings_to_process = min(len(listings), max_businesses - total_processed)
        print(f"📝 Processing {listings_to_process} listings from this page")
        
        for idx in range(listings_to_process):
            if total_processed >= max_businesses:
                print(f"🎯 Reached target of {max_businesses} businesses!")
                break
                
            business_data = {
                "shop_name": "",
                "phone": "",
                "emails": [],
                "proxy_used": proxy_manager.current_proxy
            }
            
            try:
                print(f"\n{'='*50}")
                print(f"🏪 Processing business {total_processed+1} of {max_businesses}")
                print(f"🔄 Current Proxy: {proxy_manager.current_proxy}")
                
                try:
                    listing = listings[idx]
                    data_entity = listing.get_attribute("data-entity")
                    if data_entity:
                        data = json.loads(data_entity)
                        entity = data['entity']
                        business_data["shop_name"] = entity.get('title', '')
                    
                    listing.click()
                    time.sleep(2)
                except StaleElementReferenceException:
                    print("⚠️ Listing element stale, skipping to next")
                    continue
                
                try:
                    phone_elem = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.CLASS_NAME, "longNum"))
                    )
                    business_data["phone"] = phone_elem.text.strip()
                    print(f"📞 Phone: {business_data['phone']}")
                    
                except (TimeoutException, NoSuchElementException) as e:
                    print(f"📞 Phone number not found")
                    business_data["phone"] = "Not found"
                
                website_url = None
                try:
                    try:
                        website_elem = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, 
                                "//a[contains(translate(@aria-label, 'WEBSITE', 'website'), 'website')]"
                            ))
                        )
                        website_url = website_elem.get_attribute("href")
                        print(f"🌐 Found website (aria-label): {website_url}")
                    except:
                        try:
                            website_elem = WebDriverWait(driver, 3).until(
                                EC.presence_of_element_located((By.XPATH, 
                                    "//div[contains(., 'Website')]//a[contains(@href, 'http')]"
                                ))
                            )
                            website_url = website_elem.get_attribute("href")
                            print(f"🌐 Found website (text): {website_url}")
                        except:
                            anchors = driver.find_elements(By.CSS_SELECTOR, "div.b_infocardMainDiv a[href^='http']")
                            for a in anchors:
                                href = a.get_attribute("href")
                                if href and "bing.com" not in href:
                                    website_url = href
                                    print(f"🌐 Found website (fallback): {website_url}")
                                    break
                
                except Exception as e:
                    print(f"🌐 Website extraction error: {str(e)}")
                
                if website_url:
                    business_data["website"] = website_url
                    
                    print(f"🔗 Opening website with proxy...")
                    driver.execute_script("window.open('');")
                    driver.switch_to.window(driver.window_handles[-1])
                    
                    try:
                        driver.get(website_url)
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        time.sleep(3)  
                        
                        business_data["website_name"] = get_clean_website_name_from_title(driver)
                        print(f"🏷️  Website name: {business_data['website_name']}")
                        
                        business_data["emails"] = find_emails_on_website(driver)
                        print(f"📧 Found {len(business_data['emails'])} emails: {business_data['emails']}")
                        
                    except Exception as e:
                        print(f"❌ Website processing error: {str(e)}")
                    finally:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                else:
                    print("🌐 No website found for this business")
                
                results.append(business_data)
                total_processed += 1
                print(f"✅ Completed business: {business_data['shop_name']}")
                
            except Exception as e:
                print(f"❌ Error processing listing {idx+1}: {str(e)}")
            finally:
                try:
                    close_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 
                            "button[aria-label='Close'], "
                            "button[title='Close'], "
                            "button[aria-label='Close panel'], "
                            "button[class*='closeButton']"
                        ))
                    )
                    close_btn.click()
                    time.sleep(1)
                except:
                    try:
                        map_container = driver.find_element(By.ID, "mapContainer")
                        map_container.click()
                        time.sleep(1)
                    except:
                        pass
                
                time.sleep(random.uniform(1, 3))

        if total_processed < max_businesses:
            try:
                print(f"🔍 Looking for next page URL... Need {max_businesses - total_processed} more businesses")
                
                next_url = None
                selectors_to_try = [
                    ("CSS", "a[aria-label='Next Page']"),
                    ("CSS", "a.bm_rightChevron"),
                    ("XPATH", "//a[@aria-label='Next Page']"),
                    ("XPATH", "//*[@id='60']/div/div/div/div/div/div[4]/div/div/div[2]/a"),
                ]
                
                for method, selector in selectors_to_try:
                    try:
                        if method == "CSS":
                            next_btn = WebDriverWait(driver, 3).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            )
                        else:  
                            next_btn = WebDriverWait(driver, 3).until(
                                EC.presence_of_element_located((By.XPATH, selector))
                            )

                        time.sleep(2)
                        href = next_btn.get_attribute("href")
                        onclick = next_btn.get_attribute("onclick")
                        
                        print(f"✅ Found next button with {method}: {selector}")
                        print(f"🔗 Button href: {href}")
                        print(f"🔗 Button onclick: {onclick}")
                        
                        if href and href != "#" and "javascript:" not in href:
                            next_url = href
                            print(f"✅ Found direct URL: {next_url}")
                            break
                        else:
                            current_url = driver.current_url
                            print(f"📍 Current URL: {current_url}")
                            
                            if "first=" in current_url:
                                import re
                                match = re.search(r'first=(\d+)', current_url)
                                if match:
                                    current_first = int(match.group(1))
                                    next_first = current_first + 20  
                                    next_url = re.sub(r'first=\d+', f'first={next_first}', current_url)
                                    print(f"✅ Constructed next URL: {next_url}")
                                    break
                            else:
                                if "?" in current_url:
                                    next_url = current_url + "&first=20"
                                else:
                                    next_url = current_url + "?first=20"
                                print(f"✅ Constructed first page URL: {next_url}")
                                break
                        
                    except Exception as e:
                        print(f"❌ Failed to find button with {method}: {selector} - {str(e)}")
                        continue
                
                if not next_url:
                    print("❌ Could not find next page URL with any method")
                    break
                
                print(f"🚀 Navigating directly to next page: {next_url}")
                current_url = driver.current_url
                
                try:
                    driver.get(next_url)
                    time.sleep(3)
                    
                    new_url = driver.current_url
                    if new_url != current_url:
                        print(f"✅ Successfully navigated to new page")
                        print(f"📍 New URL: {new_url}")
                    else:
                        print(f"⚠️ URL didn't change, but continuing anyway")
                    
                    print("⏳ Waiting for new listings to load...")
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'a.listings-item'))
                    )
                    
                    body = driver.find_element(By.TAG_NAME, "body")
                    for _ in range(5):
                        body.send_keys(Keys.PAGE_DOWN)
                        time.sleep(0.3)
                    
                    print("🔄 New page loaded successfully")
                    
                except Exception as e:
                    print(f"❌ Failed to navigate to next page: {str(e)}")
                    break
                
            except Exception as e:
                print(f"⏹️ Pagination failed: {str(e)}")
                break
        else:
            print(f"✅ Target of {max_businesses} businesses reached!")
            break






finally:
    print("\n🛑 Closing driver and cleaning up...")
    driver.quit()
    proxy_manager.cleanup()
    
    print("\n" + "=" * 60)
    print("💾 SAVING RESULTS")
    print("=" * 60)
    
    with open("bing_maps_leads_with_proxy.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print(f"✅ Scraping complete! Collected {len(results)} businesses.")
    print(f"📁 Results saved to: bing_maps_leads_with_proxy.json")
    print(f"🔄 Connection method used: {proxy_manager.current_proxy}")
    print("=" * 60)