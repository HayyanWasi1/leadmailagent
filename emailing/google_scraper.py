import time
import json
import re
import requests
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException, NoSuchElementException
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import re
import time
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading
from queue import Queue, Empty
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import logging
from bs4 import BeautifulSoup
from bs4 import BeautifulSoup
import random
import os
import zipfile
import tempfile

# Add this function after imports:
def human_like_scroll(driver):
    """Simulate human-like scrolling"""
    for i in range(random.randint(3, 7)):
        driver.execute_script(f"window.scrollBy(0, {random.randint(100, 300)});")
        time.sleep(random.uniform(0.5, 1.5))

try:
    from fake_useragent import UserAgent
    ua = UserAgent()
    print("fake_useragent library loaded")
except ImportError:
    print(" fake_useragent not installed. Using static user agents.")
    print(" Install with: pip install fake-useragent")
    ua = None

def click_next_page(driver):
    """Click the next page button in Google Search results"""
    try:
        print("Looking for Google's next page button...")
        
        # Scroll to bottom to make sure pagination is visible
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        next_selectors = [
            "//a[@id='pnnext']",  # Primary selector by ID
            "//a[@aria-label='Next page']",  # Alternative selector by aria-label
        ]
        
        for selector in next_selectors:
            try:
                next_button = driver.find_element(By.XPATH, selector)
                
                # Verify this is actually "Next" and not a number
                button_text = next_button.text.strip()
                print(f"Found button with text: '{button_text}'")
                
                if (button_text.lower() in ['next', '››', '>'] or 
                    next_button.get_attribute('id') == 'pnnext'):
                    
                    if next_button.is_displayed() and next_button.is_enabled():
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                        time.sleep(1)
                        print(f"Clicking actual Next button: '{button_text}'")
                        driver.execute_script("arguments[0].click();", next_button)
                        time.sleep(random.uniform(2, 3.5))
                        
                        # Wait for the next page to load
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-cid]'))
                        )
                        return True
            except Exception as e:
                print(f"Error with selector {selector}: {str(e)}")
                continue
                
        print("No valid Next button found")
        return False
        
    except Exception as e:
        print(f"Error in next page navigation: {str(e)}")
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
        
        print(f" Using User-Agent: {user_agent[:50]}...")
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
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-extensions-file-access-check')
        chrome_options.add_argument('--disable-extensions-except')
        chrome_options.add_argument('--disable-component-extensions-with-background-pages')
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        print(f" Chrome User-Agent: {user_agent[:50]}...")
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
        
        print(f" Created proxy authentication extension")
        print(f" Proxy: {self.current_proxy}")
        print(f" Authentication: {proxy_user}:*** (via extension)")
        
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
            
            print(f" Making ScraperAPI request to: {url}")
            print(f" Using: ScraperAPI Direct URL")
            
            response = requests.get(scraperapi_url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                print(f" ScraperAPI request successful")
                return response
            else:
                print(f" ScraperAPI request failed with status: {response.status_code}")
                return None
                
        except Exception as e:
            print(f" ScraperAPI request failed: {str(e)}")
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

class ComprehensiveEmailExtractor:
    def __init__(self):
        self.email_pattern = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', re.IGNORECASE)
        self.visited_urls = set()
        self.all_found_emails = []
        self.lock = threading.Lock()
        self.high_quality_found = threading.Event()
        self.driver_pool = []
        self.max_workers = 3
        self.early_exit_score = 150  # Exit early if we find email with this score
        
    def find_best_email_on_website(self, driver, max_pages=8, timeout=10):
        """
        Comprehensive email extraction from entire website
        Returns: Single best email string
        """
        print("Starting comprehensive website email extraction...")
        
        self.visited_urls.clear()
        self.all_found_emails.clear()
        self.high_quality_found.clear()
        
        try:
            # Get base URL
            base_url = driver.current_url
            base_domain = urlparse(base_url).netloc
            
            print(f"Base URL: {base_url}")
            print(f"Base Domain: {base_domain}")
            
            # Step 1: Extract from current page (fast check)
            self._extract_from_current_page(driver)
            
            # Check for early exit
            if self._check_early_exit():
                print("High-quality email found on main page - exiting early")
                return self._select_best_email()
            
            # Step 2: Parallel processing of priority pages
            try:
                self._parallel_email_extraction(driver, base_url, base_domain, max_pages)
            except Exception as e:
                print(f"Parallel processing failed, falling back to single-threaded: {str(e)}")
                # Fallback to original single-threaded approach
                self._fallback_extraction(driver, base_url, base_domain, max_pages)
            
            # Return best email
            best_email = self._select_best_email()
            
            print(f"Email extraction complete. Found {len(self.all_found_emails)} total emails")
            print(f"Best email selected: {best_email}")
            
            return best_email
            
        except Exception as e:
            print(f"Error in comprehensive email extraction: {str(e)}")
            return ""
        finally:
            self._cleanup_driver_pool()
    
    def _parallel_email_extraction(self, main_driver, base_url, base_domain, max_pages):
        """Parallel processing of URLs for faster extraction"""
        print("Starting parallel email extraction...")
        
        # Gather priority URLs
        priority_urls = self._gather_priority_urls(main_driver, base_url, base_domain, max_pages)
        
        if not priority_urls:
            print("No priority URLs found")
            return
        
        print(f"Found {len(priority_urls)} priority URLs to process")
        
        # Create driver pool
        self._create_driver_pool(min(self.max_workers, len(priority_urls)))
        
        # Process URLs in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            
            for url in priority_urls[:max_pages]:
                if self.high_quality_found.is_set():
                    break
                    
                future = executor.submit(self._process_url_threaded, url, base_domain)
                futures.append(future)
            
            # Wait for completion or early exit
            for future in concurrent.futures.as_completed(futures, timeout=30):
                try:
                    future.result(timeout=1)
                    if self.high_quality_found.is_set():
                        print("High-quality email found - cancelling remaining tasks")
                        break
                except Exception as e:
                    print(f"Thread execution error: {str(e)}")
                    continue
    
    def _gather_priority_urls(self, driver, base_url, base_domain, max_pages):
        """Gather URLs with priority-based selection"""
        priority_urls = []
        base_clean = base_url.rstrip('/')
        
        try:
            # Priority 1: Common contact pages (highest priority)
            contact_pages = [
                '/contact', '/contact-us', '/contact_us', '/contacts',
                '/about', '/about-us', '/about_us', '/aboutus',
                '/support', '/help', '/customer-service',
                '/reach-us', '/get-in-touch', '/connect'
            ]
            
            for page in contact_pages[:5]:  # Limit to top 5
                test_url = base_clean + page
                if test_url not in self.visited_urls:
                    priority_urls.append(('high', test_url))
            
            # Priority 2: Navigation menu links (medium priority)
            nav_links = self._get_limited_navigation_links(driver, base_domain, 10)
            for link in nav_links:
                if link not in self.visited_urls:
                    priority_urls.append(('medium', link))
            
            # Priority 3: Other internal links (low priority)
            other_links = self._get_limited_internal_links(driver, base_domain, 5)
            for link in other_links:
                if link not in self.visited_urls:
                    priority_urls.append(('low', link))
            
            # Sort by priority
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            priority_urls.sort(key=lambda x: priority_order[x[0]])
            
            return [url for _, url in priority_urls]
            
        except Exception as e:
            print(f"Error gathering priority URLs: {str(e)}")
            return []
    
    def _get_limited_navigation_links(self, driver, base_domain, limit=10):
        """Get limited navigation links for performance"""
        nav_links = set()
        
        # Reduced selectors for performance
        nav_selectors = [
            'nav a', 'header a', '.navbar a', '.navigation a', 
            '[class*="nav"] a', '[class*="menu"] a'
        ]
        
        try:
            for selector in nav_selectors[:3]:  # Limit selectors
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)[:limit]  # Limit elements
                    for element in elements:
                        try:
                            href = element.get_attribute('href')
                            if href and self._is_internal_link(href, base_domain):
                                nav_links.add(href)
                                if len(nav_links) >= limit:
                                    return list(nav_links)
                        except:
                            continue
                except:
                    continue
        except:
            pass
            
        return list(nav_links)
    
    def _get_limited_internal_links(self, driver, base_domain, limit=5):
        """Get limited internal links for performance"""
        internal_links = set()
        
        try:
            links = driver.find_elements(By.TAG_NAME, 'a')[:20]  # Limit to first 20 links
            for link in links:
                try:
                    href = link.get_attribute('href')
                    if href and self._is_internal_link(href, base_domain):
                        internal_links.add(href)
                        if len(internal_links) >= limit:
                            break
                except:
                    continue
        except:
            pass
            
        return list(internal_links)
    
    def _create_driver_pool(self, pool_size):
        """Create a pool of WebDriver instances"""
        try:
            for i in range(pool_size):
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--disable-images')
                options.add_argument('--disable-javascript')  # Faster loading
                options.add_argument('--page-load-strategy=eager')
                
                driver = webdriver.Chrome(options=options)
                driver.set_page_load_timeout(5)  # Reduced timeout
                self.driver_pool.append(driver)
                
            print(f"Created driver pool with {len(self.driver_pool)} drivers")
            
        except Exception as e:
            print(f"Error creating driver pool: {str(e)}")
            # Clear any partially created drivers
            self._cleanup_driver_pool()
            raise
    
    def _process_url_threaded(self, url, base_domain):
        """Process URL in a separate thread"""
        driver = None
        try:
            # Get driver from pool
            with self.lock:
                if self.driver_pool:
                    driver = self.driver_pool.pop()
                else:
                    print("No available drivers in pool")
                    return
            
            if self.high_quality_found.is_set():
                return
            
            print(f"Processing URL in thread: {url}")
            
            # Visit and extract
            success = self._visit_and_extract_fast(driver, url)
            
            if success and self._check_early_exit():
                self.high_quality_found.set()
                print(f"High-quality email found on {url}")
            
        except Exception as e:
            print(f"Error processing {url} in thread: {str(e)}")
        finally:
            # Return driver to pool
            if driver:
                with self.lock:
                    self.driver_pool.append(driver)
    
    def _visit_and_extract_fast(self, driver, url):
        """Fast version of visit and extract"""
        try:
            # Check if already visited (thread-safe)
            with self.lock:
                if url in self.visited_urls:
                    return False
                self.visited_urls.add(url)
            
            # Quick page load with timeout
            driver.get(url)
            
            # Quick check for 404 or errors
            try:
                WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                print(f"Page load timeout: {url}")
                return False
            
            # Quick 404 detection
            if "404" in driver.title.lower() or "not found" in driver.title.lower():
                print(f"Page not found: {url}")
                return False
            
            # Fast email extraction
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            emails = self._extract_emails_from_soup_fast(soup, url)
            
            if emails:
                with self.lock:
                    self.all_found_emails.extend(emails)
                    print(f"Found {len(emails)} emails on {url}")
            
            return True
            
        except Exception as e:
            print(f"Error in fast visit {url}: {str(e)}")
            return False
    
    def _extract_emails_from_soup_fast(self, soup, source_url):
        """Optimized email extraction with early exit"""
        found_emails = []
        
        try:
            # Priority 1: mailto links (fastest)
            mailto_links = soup.find_all('a', href=lambda x: x and x.lower().startswith('mailto:'))
            for a in mailto_links[:5]:  # Limit to first 5
                href = a['href']
                email = href.split(':', 1)[1].split('?')[0].strip()
                email = self._clean_email(email)
                if self._is_valid_business_email(email):
                    score = self._calculate_priority_score(email, 'mailto')
                    found_emails.append({
                        'email': email,
                        'source': 'mailto',
                        'source_url': source_url,
                        'priority_score': score
                    })
                    # Early exit for high-quality mailto
                    if score >= self.early_exit_score:
                        return found_emails
            
            # Priority 2: Contact sections (if no high-quality mailto found)
            if not found_emails or max(e['priority_score'] for e in found_emails) < 120:
                contact_selectors = [
                    '[class*="contact"]', 'footer', '[id*="contact"]'
                ]
                
                for selector in contact_selectors[:2]:  # Limit selectors
                    try:
                        elements = soup.select(selector)[:3]  # Limit elements
                        for element in elements:
                            section_text = element.get_text(" ", strip=True)[:1000]  # Limit text length
                            emails = self.email_pattern.findall(section_text)
                            for email in emails[:3]:  # Limit emails per section
                                email = self._clean_email(email)
                                if self._is_valid_business_email(email):
                                    score = self._calculate_priority_score(email, 'contact_section')
                                    found_emails.append({
                                        'email': email,
                                        'source': 'contact_section',
                                        'source_url': source_url,
                                        'priority_score': score
                                    })
                                    # Early exit for high-quality contact email
                                    if score >= self.early_exit_score:
                                        return found_emails
                    except:
                        continue
            
            # Priority 3: Limited full page scan (only if needed)
            if not found_emails:
                page_text = soup.get_text(" ", strip=True)[:2000]  # Limit text scan
                emails = self.email_pattern.findall(page_text)
                for email in emails[:5]:  # Limit to first 5 emails
                    email = self._clean_email(email)
                    if self._is_valid_business_email(email):
                        found_emails.append({
                            'email': email,
                            'source': 'full_page',
                            'source_url': source_url,
                            'priority_score': self._calculate_priority_score(email, 'full_page')
                        })
            
            # Remove duplicates
            unique_emails = {}
            for email_data in found_emails:
                email = email_data['email']
                if email not in unique_emails or email_data['priority_score'] > unique_emails[email]['priority_score']:
                    unique_emails[email] = email_data
            
            return list(unique_emails.values())
            
        except Exception as e:
            print(f"Error in fast extraction: {str(e)}")
            return []
    
    def _check_early_exit(self):
        """Check if we should exit early based on email quality"""
        with self.lock:
            if not self.all_found_emails:
                return False
            
            # Check for high-quality emails
            max_score = max(email['priority_score'] for email in self.all_found_emails)
            return max_score >= self.early_exit_score
    
    def _fallback_extraction(self, driver, base_url, base_domain, max_pages):
        """Fallback to original single-threaded approach"""
        print("Using fallback single-threaded extraction...")
        
        # Reduced scope fallback
        self._explore_navigation_menus(driver, base_domain, min(max_pages, 4))
        
        if not self._check_early_exit():
            self._visit_common_pages(driver, base_url, base_domain, min(max_pages, 4))
    
    def _cleanup_driver_pool(self):
        """Clean up driver pool"""
        try:
            for driver in self.driver_pool:
                try:
                    driver.quit()
                except:
                    pass
            self.driver_pool.clear()
            print("Driver pool cleaned up")
        except Exception as e:
            print(f"Error cleaning up driver pool: {str(e)}")
    
    # Keep all original methods for backward compatibility
    def _extract_from_current_page(self, driver):
        """Extract emails from current page"""
        try:
            current_url = driver.current_url
            print(f"Extracting from current page: {current_url}")
            
            # Mark as visited
            self.visited_urls.add(current_url)
            
            # Get page source
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            
            # Extract emails
            emails = self._extract_emails_from_soup(soup, current_url)
            self.all_found_emails.extend(emails)
            
            print(f"Found {len(emails)} emails on current page")
            
        except Exception as e:
            print(f"Error extracting from current page: {str(e)}")
    
    def _explore_navigation_menus(self, driver, base_domain, max_pages):
        """Find and explore all navigation menus and dropdowns"""
        try:
            print("Exploring navigation menus...")
            
            # Navigation selectors - comprehensive list
            nav_selectors = [
                'nav a', 'header a', 'footer a',
                '[class*="nav"] a', '[class*="menu"] a', '[class*="header"] a',
                '[id*="nav"] a', '[id*="menu"] a', '[id*="header"] a',
                '.navbar a', '.navigation a', '.main-menu a', '.header-menu a',
                '[role="navigation"] a', '.top-menu a', '.primary-menu a',
                '.site-navigation a', '.main-nav a', '.header-nav a'
            ]
            
            # Find all menu links
            menu_links = set()
            for selector in nav_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        try:
                            href = element.get_attribute('href')
                            if href and self._is_internal_link(href, base_domain):
                                menu_links.add(href)
                        except:
                            continue
                except:
                    continue
            
            print(f"Found {len(menu_links)} menu links")
            
            # Visit menu links
            visited_count = 0
            for link in list(menu_links)[:max_pages]:
                if visited_count >= max_pages:
                    break
                    
                if link not in self.visited_urls:
                    self._visit_and_extract(driver, link)
                    visited_count += 1
                    
        except Exception as e:
            print(f"Error exploring navigation menus: {str(e)}")
    
    def _visit_common_pages(self, driver, base_url, base_domain, max_pages):
        """Visit common pages where emails are usually found"""
        try:
            print("Visiting common pages...")
            
            base_clean = base_url.rstrip('/')
            
            # Common page patterns
            common_pages = [
                '/contact', '/contact-us', '/contact_us', '/contacts',
                '/about', '/about-us', '/about_us', '/aboutus',
                '/support', '/help', '/customer-service',
                '/reach-us', '/get-in-touch', '/connect',
                '/team', '/staff', '/management',
                '/info', '/information', '/details',
                '/office', '/location', '/address'
            ]
            
            # Try each common page
            visited_count = 0
            for page in common_pages:
                if visited_count >= max_pages:
                    break
                    
                test_url = base_clean + page
                if test_url not in self.visited_urls:
                    if self._visit_and_extract(driver, test_url):
                        visited_count += 1
                        
        except Exception as e:
            print(f"Error visiting common pages: {str(e)}")
    
    def _deep_crawl_internal_links(self, driver, base_domain, max_pages):
        """Deep crawl internal links found on pages"""
        try:
            print("Deep crawling internal links...")
            
            # Go back to main page to find all internal links
            all_internal_links = set()
            
            for visited_url in list(self.visited_urls):
                try:
                    driver.get(visited_url)
                    WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    
                    # Find all links on this page
                    links = driver.find_elements(By.TAG_NAME, 'a')
                    for link in links:
                        try:
                            href = link.get_attribute('href')
                            if href and self._is_internal_link(href, base_domain):
                                all_internal_links.add(href)
                        except:
                            continue
                            
                except:
                    continue
            
            print(f"Found {len(all_internal_links)} total internal links")
            
            # Visit unvisited internal links
            visited_count = 0
            for link in all_internal_links:
                if visited_count >= max_pages:
                    break
                    
                if link not in self.visited_urls:
                    if self._visit_and_extract(driver, link):
                        visited_count += 1
                        
        except Exception as e:
            print(f"Error in deep crawling: {str(e)}")
    
    def _visit_and_extract(self, driver, url):
        """Visit URL and extract emails"""
        try:
            print(f"Visiting: {url}")
            
            driver.get(url)
            WebDriverWait(driver, 5).until(  # Reduced timeout
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(0.5)  # Reduced sleep
            
            # Check if page loaded successfully
            if "404" in driver.title.lower() or "not found" in driver.title.lower():
                print(f"Page not found: {url}")
                return False
            
            # Mark as visited
            self.visited_urls.add(url)
            
            # Extract emails
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            emails = self._extract_emails_from_soup(soup, url)
            
            if emails:
                self.all_found_emails.extend(emails)
                print(f"Found {len(emails)} emails on {url}")
            
            return True
            
        except Exception as e:
            print(f"Error visiting {url}: {str(e)}")
            return False
    
    def _extract_emails_from_soup(self, soup, source_url):
        """Extract all emails from BeautifulSoup object"""
        found_emails = []
        
        try:
            # Priority 1: mailto links
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.lower().startswith('mailto:'):
                    email = href.split(':', 1)[1].split('?')[0].strip()
                    email = self._clean_email(email)
                    if self._is_valid_business_email(email):
                        found_emails.append({
                            'email': email,
                            'source': 'mailto',
                            'source_url': source_url,
                            'priority_score': self._calculate_priority_score(email, 'mailto')
                        })
            
            # Priority 2: Contact sections
            contact_sections = []
            contact_selectors = [
                'footer', '[class*="contact"]', '[class*="footer"]',
                '[id*="contact"]', '[class*="contact-info"]', '[class*="contact-details"]',
                '.contact', '.footer', '.contact-us', '.reach-us', '.get-in-touch'
            ]
            
            for selector in contact_selectors:
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        contact_sections.append(element.get_text(" ", strip=True))
                except:
                    pass
            
            # Extract from contact sections
            for section_text in contact_sections:
                emails = self.email_pattern.findall(section_text)
                for email in emails:
                    email = self._clean_email(email)
                    if self._is_valid_business_email(email):
                        found_emails.append({
                            'email': email,
                            'source': 'contact_section',
                            'source_url': source_url,
                            'priority_score': self._calculate_priority_score(email, 'contact_section')
                        })
            
            # Priority 3: Full page text
            if not found_emails:  # Only if no emails found in priority sections
                page_text = soup.get_text(" ", strip=True)
                emails = self.email_pattern.findall(page_text)
                for email in emails:
                    email = self._clean_email(email)
                    if self._is_valid_business_email(email):
                        found_emails.append({
                            'email': email,
                            'source': 'full_page',
                            'source_url': source_url,
                            'priority_score': self._calculate_priority_score(email, 'full_page')
                        })
            
            # Remove duplicates while preserving highest priority
            unique_emails = {}
            for email_data in found_emails:
                email = email_data['email']
                if email not in unique_emails or email_data['priority_score'] > unique_emails[email]['priority_score']:
                    unique_emails[email] = email_data
            
            return list(unique_emails.values())
            
        except Exception as e:
            print(f"Error extracting emails from soup: {str(e)}")
            return []
    
    def _is_internal_link(self, href, base_domain):
        """Check if link is internal to the website"""
        try:
            if not href:
                return False
                
            if not href.startswith(('http://', 'https://', '/')):
                return False
                
            if href.startswith('/'):
                return True
                
            link_domain = urlparse(href).netloc
            return link_domain == base_domain or link_domain == f"www.{base_domain}" or base_domain == f"www.{link_domain}"
            
        except:
            return False
    
    def _clean_email(self, email):
        """Clean and normalize email"""
        if not email:
            return ""
            
        email = email.strip().strip('.,;:"\'<>[]{} ()')
        email = re.sub(r'^(mailto:|email:|contact:)', '', email, flags=re.IGNORECASE)
        email = re.sub(r'\s+', '', email)
        
        match = self.email_pattern.search(email)
        if match:
            return match.group(0).lower()
            
        return email.lower()
    
    def _is_valid_business_email(self, email):
        """Check if email is valid for business use"""
        if not email or '@' not in email:
            return False
            
        email = email.lower().strip()
        
        invalid_patterns = [
            r'\.png$', r'\.jpg$', r'\.jpeg$', r'\.gif$', r'\.pdf$',
            r'example\.com$', r'test\.com$', r'domain\.com$',
            r'@test', r'@example', r'@localhost', r'@domain',
            r'noreply', r'no-reply', r'donotreply', r'bounce',
            r'@gmail\.com$', r'@yahoo\.com$', r'@hotmail\.com$',  
            r'postmaster@', r'webmaster@', r'admin@'  
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, email):
                return False
        
        if email.count('@') != 1:
            return False
            
        local, domain = email.split('@')
        if len(local) < 2 or len(domain) < 4 or '.' not in domain:
            return False
            
        return True
    
    def _calculate_priority_score(self, email, source):
        """Calculate priority score for email"""
        score = 50  
        
        email_lower = email.lower()
        local_part = email_lower.split('@')[0]
        domain_part = email_lower.split('@')[1]
        
        source_scores = {
            'mailto': 100,
            'contact_section': 80,
            'full_page': 40
        }
        score += source_scores.get(source, 0)
        
        # Local part priority
        high_priority = ['info', 'contact', 'hello', 'sales', 'business', 'office', 'admin', 'enquiry', 'inquiry']
        medium_priority = ['support', 'help', 'service', 'team', 'mail', 'general', 'reception']
        low_priority = ['marketing', 'newsletter', 'subscribe', 'noreply']
        
        if any(keyword in local_part for keyword in high_priority):
            score += 50
        elif any(keyword in local_part for keyword in medium_priority):
            score += 30
        elif any(keyword in local_part for keyword in low_priority):
            score -= 20
        
        # Domain priority (business domains preferred)
        personal_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
        if not any(domain_part.endswith(pd) for pd in personal_domains):
            score += 30  # Business domain bonus
        else:
            score -= 10  # Personal domain penalty
        
        # Penalize very generic emails
        if local_part in ['admin', 'webmaster', 'postmaster', 'root']:
            score -= 30
            
        return max(score, 0)  # Ensure non-negative
    
    def _select_best_email(self):
        """Select the single best email from all found emails"""
        if not self.all_found_emails:
            return ""
        
        # Remove exact duplicates
        unique_emails = {}
        for email_data in self.all_found_emails:
            email = email_data['email']
            if email not in unique_emails or email_data['priority_score'] > unique_emails[email]['priority_score']:
                unique_emails[email] = email_data
        
        if not unique_emails:
            return ""
        
        # Sort by priority score
        sorted_emails = sorted(unique_emails.values(), key=lambda x: x['priority_score'], reverse=True)
        
        best_email_data = sorted_emails[0]
        best_email = best_email_data['email']
        
        print(f"Email selection complete:")
        print(f"  Total unique emails found: {len(unique_emails)}")
        print(f"  Best email: {best_email}")
        print(f"  Source: {best_email_data['source']}")
        print(f"  Priority score: {best_email_data['priority_score']}")
        print(f"  Found on: {best_email_data['source_url']}")
        
        return best_email

# Replace the existing find_emails_on_website function with this:
def find_emails_on_website(driver, max_pages=8):
    """
    Main function to find the best email on a website
    Returns: Single best email string
    """
    extractor = ComprehensiveEmailExtractor()
    return extractor.find_best_email_on_website(driver, max_pages)

def create_driver_with_proxy():
    print(" Initializing Chrome driver...")
    
    try:
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        
        driver = webdriver.Chrome(options=chrome_options)
        return driver
        
    except Exception as e:
        print(f"Chrome setup failed: {str(e)}")
        raise Exception("Chrome driver creation failed")

def click_more_businesses_and_navigate(driver):
    """
    Scroll down, find and click the 'More businesses' link to navigate to full listings
    """
    try:
        print("Looking for 'More businesses' link...")
        
        # Scroll down to make sure the link is visible
        body = driver.find_element(By.TAG_NAME, "body")
        for i in range(3):
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(random.uniform(0.5, 1.5))
        
        more_businesses_selectors = [
            "//span[text()='More businesses']/ancestor::a",
            "//span[contains(@class, 'tJaMb') and contains(text(), 'More businesses')]/ancestor::a",
            "a[href*='search'][href*='udm=1']"  # Fallback selector
        ]
        
        for selector in more_businesses_selectors:
            try:
                if selector.startswith("//"):
                    more_businesses_link = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    more_businesses_link = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                
                print("Found 'More businesses' link, clicking...")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_businesses_link)
                time.sleep(1)
                more_businesses_link.click()
                time.sleep(random.uniform(3, 5))
                return True
                
            except TimeoutException:
                continue
        
        print("Could not find 'More businesses' link")
        return False
        
    except Exception as e:
        print(f"Error clicking 'More businesses': {str(e)}")
        return False

def scrape_google_maps(query, max_businesses):
    """
    Main function to scrape Google Maps for business information
    """
    print("=" * 60)
    print("  GOOGLE BUSINESS SCRAPER WITH ROTATING PROXIES")
    print("=" * 60)
    print(f" ScraperAPI Key: {SCRAPER_API_KEY[:10]}...")
    print(f" Proxy URL: {SCRAPER_API_URL}")
    print("=" * 60)
    
    driver = create_driver_with_proxy()
    results = []
    
    try:
        print(f"\n Searching for: {query}")
        print(f" Target businesses: {max_businesses}")
        
        print("  Opening Google Search...")
        driver.get(f"https://www.google.com/search?q={query}")
    
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "search"))
        )
        time.sleep(random.uniform(3, 7))
    
        # Click "More businesses" to get to full listings page
        if "captcha" in driver.page_source.lower() or "unusual traffic" in driver.page_source.lower():
            print("CAPTCHA detected. Pausing for manual solve...")
            input("Press Enter after solving CAPTCHA...")
        
        if not click_more_businesses_and_navigate(driver):
            print("Failed to navigate to full business listings. Exiting...")
            return results
            
        time.sleep(3)
        print("Loading listings...")
        body = driver.find_element(By.TAG_NAME, "body")
        for _ in range(10):
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(random.uniform(0.5, 2.5))
        
        page_count = 0
        total_processed = 0
    
        while total_processed < max_businesses:
            page_count += 1
            print(f"\n Processing page {page_count}")
            print(f" Progress: {total_processed}/{max_businesses} businesses collected")
    
            try:
                WebDriverWait(driver, 7.5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-cid]'))
                )
            except TimeoutException:
                print(" No more listings found")
                break
    
            listings = []
            retry_count = 0
            max_retries = 3
            
            while not listings and retry_count < max_retries:
                listings = driver.find_elements(By.CSS_SELECTOR, '[data-cid]')
                if not listings:
                    print(f" No listings found, retrying... ({retry_count + 1}/{max_retries})")
                    time.sleep(2)
                    body = driver.find_element(By.TAG_NAME, "body")
                    for i in range(5):
                        body.send_keys(Keys.PAGE_DOWN)
                        time.sleep(0.3)
                    retry_count += 1
            
            if not listings:
                print(" No listings found after retries, moving to next page or ending")
                continue
                
            print(f" Found {len(listings)} listings on this page")
            print(f" Need to process {min(len(listings), max_businesses - total_processed)} from this page")
    
            listings_to_process = min(len(listings), max_businesses - total_processed)
            print(f" Processing {listings_to_process} listings from this page")
            
            for idx in range(listings_to_process):
                if total_processed >= max_businesses:
                    print(f" Reached target of {max_businesses} businesses!")
                    break
                    
                business_data = {
                    "company_name": "",
                    "phone": "",
                    "emails": [],
                }
                
                try:
                    print(f"\n{'='*50}")
                    print(f" Processing business {total_processed+1} of {max_businesses}")
                    print(f" Current Proxy: {proxy_manager.current_proxy}")
                    
                    try:
                        # Get fresh listing reference
                        current_listings = driver.find_elements(By.CSS_SELECTOR, '[data-cid]')
                        if idx >= len(current_listings):
                            print(" Listing index out of range, skipping")
                            continue
                            
                        listing = current_listings[idx]
                        
                        try:
                            # Prioritized selectors based on the HTML structure you provided
                            name_selectors = [
                                'span.OSrXXb',  # ADD THIS LINE - matches your HTML exactly
                                'h2[data-attrid="title"] span',  # Direct match for your HTML structure
                                'h2.qrShPb span',  # Class-based selector
                                'h2[class*="qrShPb"] span',  # Partial class match
                                'h3[class*="fontHeadline"]',  # Alternative heading
                                '[data-attrid="title"] span',  # Generic data attribute
                                '.qBF1Pd',  # Common class
                                'h3.fontHeadlineSmall',  # Alternative title
                                '[role="heading"] span',  # Generic heading
                            ]
                            
                            business_name = None
                            for selector in name_selectors:
                                try:
                                    name_elem = listing.find_element(By.CSS_SELECTOR, selector)
                                    business_name = name_elem.text.strip()
                                    if business_name and len(business_name) > 1:  # Valid name found
                                        print(f"✓ Found business name with selector: '{selector}'")
                                        break
                                except:
                                    continue  # Try next selector
                            
                            if business_name and len(business_name) > 1:
                                business_data["company_name"] = business_name
                                print(f" Business name: {business_data['company_name']}")
                            else:
                                # Final fallback: try XPath if CSS selectors fail
                                try:
                                    name_elem = listing.find_element(By.XPATH, ".//h2//span[text()]")
                                    business_data["company_name"] = name_elem.text.strip()
                                    print(f" Business name (XPath fallback): {business_data['company_name']}")
                                except:
                                    business_data["company_name"] = "Name not found"
                                    print(" Business name not found with any selector")
                                
                        except Exception as e:
                            print(f" Business name extraction error: {str(e)}")
                            business_data["company_name"] = "Name not found"
                        # Scroll to listing and click
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", listing)
                        time.sleep(0.5)
                        listing.click()
                        time.sleep(2)
                        
                    except StaleElementReferenceException:
                        print(" Listing element stale, skipping to next")
                        continue
    
                    
                    # Extract phone number from the opened panel
                    try:
                        phone_selectors = [
                            "//span[contains(@aria-label, 'Call phone number')]",
                            "//a[starts-with(@href, 'tel:')]//span",
                            "//div[contains(@data-attrid, 'phone')]//span",
                            "//*[contains(text(), '+') and contains(text(), '-')]",
                            "//span[contains(text(), '(') and contains(text(), ')')]"
                        ]
                        
                        phone_found = False
                        for selector in phone_selectors:
                            try:
                                phone_elem = driver.find_element(By.XPATH, selector)
                                
                                if "aria-label" in selector:
                                    aria_text = phone_elem.get_attribute('aria-label')
                                    if aria_text and 'Call phone number' in aria_text:
                                        phone_text = aria_text.replace('Call phone number', '').strip()
                                    else:
                                        phone_text = phone_elem.text.strip()
                                else:
                                    phone_text = phone_elem.text.strip()
                                
                                if phone_text and ('+' in phone_text or '(' in phone_text or 
                                                len(re.sub(r'[^\d]', '', phone_text)) >= 10):
                                    business_data["phone"] = phone_text
                                    print(f" Phone: {business_data['phone']}")
                                    phone_found = True
                                    break
                            except:
                                continue
                        
                        if not phone_found:
                            business_data["phone"] = "Not found"
                            print(" Phone number not found")
                            
                    except Exception as e:
                        print(f" Phone number extraction error: {str(e)}")
                        business_data["phone"] = "Not found"
                    
                    # Extract website URL
                    website_url = None
                    try:
                        website_selectors = [
                            "//a[contains(@aria-label, 'Website')]",
                            "//span[contains(text(), 'Website')]/ancestor::a",
                            "//div[contains(@data-attrid, 'website')]//a",
                            "//a[contains(@href, 'http') and not(contains(@href, 'google'))]"
                        ]
                        
                        for selector in website_selectors:
                            try:
                                website_elem = driver.find_element(By.XPATH, selector)
                                website_url = website_elem.get_attribute("href")
                                if website_url and "google" not in website_url.lower():
                                    print(f" Found website: {website_url}")
                                    break
                            except:
                                continue
                                
                    except Exception as e:
                        print(f" Website extraction error: {str(e)}")
                    
                    # Process website for emails (same logic as Bing)
                    if website_url:
                        business_data["website"] = website_url
                        
                        print(f" Opening website with proxy...")
                        driver.execute_script("window.open('');")
                        driver.switch_to.window(driver.window_handles[-1])
                        
                        try:
                            driver.get(website_url)
                            WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.TAG_NAME, "body"))
                            )
                            time.sleep(3)  
                            
                            business_data["emails"] = [find_emails_on_website(driver)]
                            print(f" Found {len(business_data['emails'])} emails: {business_data['emails']}")
                            
                        except Exception as e:
                            print(f" Website processing error: {str(e)}")
                        finally:
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                    else:
                        print(" No website found for this business")
            
                    results.append(business_data)
                    total_processed += 1
                    print(f" Completed business: {business_data['company_name']}")
                    
                except Exception as e:
                    print(f" Error processing listing {idx+1}: {str(e)}")
                finally:
                    # Close business panel - simplified approach
                    try:
                        # Method 1: Press Escape key
                        actions = ActionChains(driver)
                        actions.send_keys(Keys.ESCAPE).perform()
                        time.sleep(1)
                    except:
                        try:
                            # Method 2: Click on map area to close panel
                            map_area = driver.find_element(By.CSS_SELECTOR, "#search, [role='main']")
                            map_area.click()
                            time.sleep(1)
                        except:
                            pass
                    
                    time.sleep(random.uniform(1, 3))
    
            # Navigate to next page if needed (same logic as Bing)
            if total_processed < max_businesses:
                print(f" Looking for next page... Need {max_businesses - total_processed} more businesses")
                
                if click_next_page(driver):
                    print(" New page loaded successfully")
                    print(" Ready to process next page listings")
                else:
                    print(" No more pages available or pagination failed")
                    break
            else:
                print(f" Target of {max_businesses} businesses reached!")
                break
                
    except Exception as e:
        print(f"Error during Google Maps scraping: {str(e)}")
    finally:
        print("\nClosing driver and cleaning up...")
        driver.quit()
        proxy_manager.cleanup()
        
        print("\n" + "=" * 60)
        print("SCRAPING COMPLETE")
        print("=" * 60)
        print(f" Scraping complete! Collected {len(results)} businesses.")
        print(f" Connection method used: {proxy_manager.current_proxy}")
        print("=" * 60)
    
    return results