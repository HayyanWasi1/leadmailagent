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
import os
import zipfile
import tempfile

try:
    from fake_useragent import UserAgent
    ua = UserAgent()
    print("fake_useragent library loaded")
except ImportError:
    print(" fake_useragent not installed. Using static user agents.")
    print(" Install with: pip install fake-useragent")
    ua = None


def click_next_page(driver):
    """Updated next page click function based on working test logic"""
    try:
        print(f"Testing next button availability...")
        

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.listings-item"))
        )
        
        body = driver.find_element(By.TAG_NAME, "body")
        for i in range(5):
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(0.3)
        print("Completed scrolling")
        
 
        time.sleep(3)
        
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "a.bm_rightChevron[aria-label='Next Page']")
            print("SUCCESS: Next button found with exact selector")
            

            print(f"Button is_displayed(): {next_button.is_displayed()}")
            print(f"Button is_enabled(): {next_button.is_enabled()}")
            

            try:
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.bm_rightChevron[aria-label='Next Page']"))
                )
                print("SUCCESS: Next button is clickable")
                

                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(1)
                

                driver.execute_script("arguments[0].click();", next_button)
                print("Clicked next page button")
                

                print("Waiting for page to change...")
                time.sleep(5)
                
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.listings-item"))
                )
                
                try:
                    prev_button = driver.find_element(By.CSS_SELECTOR, "a.bm_leftChevron[aria-label='Previous Page']")
                    if prev_button.is_displayed():
                        print("SUCCESS: Previous button now visible - we moved to next page!")
                        return True
                    else:
                        print("Previous button found but not visible")
                        return False
                except:
                    print("No previous button found - might still be on first page")

                    new_listings = driver.find_elements(By.CSS_SELECTOR, 'a.listings-item')
                    print(f"After click: Found {len(new_listings)} listings")
                    return len(new_listings) > 0
                    
            except TimeoutException:
                print("ERROR: Button found but NOT clickable")
                return False
                
        except NoSuchElementException:
            print("ERROR: Next button not found with exact selector")
            

            all_links = driver.find_elements(By.TAG_NAME, "a")
            pagination_links = []
            
            for link in all_links:
                aria_label = link.get_attribute("aria-label") or ""
                class_name = link.get_attribute("class") or ""
                
                if ("next" in aria_label.lower() or 
                    "chevron" in class_name.lower() or 
                    "bm_" in class_name):
                    pagination_links.append({
                        'element': link,
                        'aria_label': aria_label,
                        'class': class_name
                    })
            
            print(f"Found {len(pagination_links)} potential pagination elements as fallback")
            

            for link_info in pagination_links:
                try:
                    element = link_info['element']
                    if element.is_displayed() and element.is_enabled():
                        print(f"Trying fallback element with class: {link_info['class']}")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", element)
                        time.sleep(5)
                        return True
                except:
                    continue
                    
            return False
            
    except Exception as e:
        print(f"ERROR in click_next_page: {str(e)}")
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
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
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

import re
from urllib.parse import urljoin, urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import time

class ComprehensiveEmailExtractor:
    def __init__(self):
        self.email_pattern = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', re.IGNORECASE)
        self.visited_urls = set()
        self.all_found_emails = []
        
    def find_best_email_on_website(self, driver, max_pages=8, timeout=10):
        """
        Comprehensive email extraction from entire website
        Returns: Single best email string
        """
        print("Starting comprehensive website email extraction...")
        
        self.visited_urls.clear()
        self.all_found_emails.clear()
        
        try:
            # Get base URL
            base_url = driver.current_url
            base_domain = urlparse(base_url).netloc
            
            print(f"Base URL: {base_url}")
            print(f"Base Domain: {base_domain}")
            
            # Step 1: Extract from current page
            self._extract_from_current_page(driver)
            
            # Step 2: Find and explore navigation menus
            self._explore_navigation_menus(driver, base_domain, max_pages)
            
            # Step 3: Find and visit common pages
            self._visit_common_pages(driver, base_url, base_domain, max_pages)
            
            # Step 4: Deep crawl internal links
            self._deep_crawl_internal_links(driver, base_domain, max_pages)
            
            # Step 5: Return best email
            best_email = self._select_best_email()
            
            print(f"Email extraction complete. Found {len(self.all_found_emails)} total emails")
            print(f"Best email selected: {best_email}")
            
            return best_email
            
        except Exception as e:
            print(f"Error in comprehensive email extraction: {str(e)}")
            return ""
    
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
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(1)
            
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
                
            # Skip non-http links
            if not href.startswith(('http://', 'https://', '/')):
                return False
                
            # Relative links are internal
            if href.startswith('/'):
                return True
                
            # Check domain
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
        
        # Extract clean email using regex
        match = self.email_pattern.search(email)
        if match:
            return match.group(0).lower()
            
        return email.lower()
    
    def _is_valid_business_email(self, email):
        """Check if email is valid for business use"""
        if not email or '@' not in email:
            return False
            
        email = email.lower().strip()
        
        # Invalid patterns
        invalid_patterns = [
            r'\.png$', r'\.jpg$', r'\.jpeg$', r'\.gif$', r'\.pdf$',
            r'example\.com$', r'test\.com$', r'domain\.com$',
            r'@test', r'@example', r'@localhost', r'@domain',
            r'noreply', r'no-reply', r'donotreply', r'bounce',
            r'@gmail\.com$', r'@yahoo\.com$', r'@hotmail\.com$',  # Personal emails have lower priority
            r'postmaster@', r'webmaster@', r'admin@'  # Generic admin emails
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, email):
                return False
        
        # Must have valid structure
        if email.count('@') != 1:
            return False
            
        local, domain = email.split('@')
        if len(local) < 2 or len(domain) < 4 or '.' not in domain:
            return False
            
        return True
    
    def _calculate_priority_score(self, email, source):
        """Calculate priority score for email"""
        score = 50  # Base score
        
        email_lower = email.lower()
        local_part = email_lower.split('@')[0]
        domain_part = email_lower.split('@')[1]
        
        # Source priority
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


def get_clean_website_name_from_title(driver):
    """
    Extract and clean website name from page title
    Returns: Clean website name string
    """
    try:
        # Get page title
        title = driver.title.strip()
        
        if not title:
            # Fallback to domain name if no title
            current_url = driver.current_url
            from urllib.parse import urlparse
            domain = urlparse(current_url).netloc
            return domain.replace('www.', '').replace('.com', '').replace('.co.uk', '')
        
        # Clean common title patterns
        title = title.replace(' - ', ' | ').replace(' – ', ' | ')
        
        # Remove common suffixes
        suffixes_to_remove = [
            '| Home', '- Home', 'Home -', 'Home |',
            '| Welcome', '- Welcome', 'Welcome -', 'Welcome |',
            '| Official Site', '- Official Site',
            '| Contact Us', '- Contact Us',
            '| About Us', '- About Us'
        ]
        
        for suffix in suffixes_to_remove:
            if suffix in title:
                title = title.replace(suffix, '').strip()
        
        # Split by common separators and take first part (usually company name)
        separators = ['|', '-', '–', ':', '•']
        for sep in separators:
            if sep in title:
                parts = title.split(sep)
                if len(parts) > 1 and len(parts[0].strip()) > 2:
                    title = parts[0].strip()
                    break
        
        # Clean up remaining text
        title = title.strip()
        
        # Remove common website-related words from the end
        website_words = ['Website', 'Site', 'Online', 'Web', 'Page']
        for word in website_words:
            if title.endswith(f' {word}'):
                title = title[:-len(f' {word}')].strip()
        
        # Limit length
        if len(title) > 50:
            title = title[:50].strip()
        
        return title if title else "Unknown Website"
        
    except Exception as e:
        print(f"Error extracting website name: {str(e)}")
        try:
            # Fallback to domain extraction
            current_url = driver.current_url
            from urllib.parse import urlparse
            domain = urlparse(current_url).netloc
            return domain.replace('www.', '').replace('.com', '').replace('.co.uk', '')
        except:
            return "Unknown Website"



def create_driver_with_proxy():
    print(" Initializing Chrome driver...")
    
    approaches = [
        ("Chrome Extension Proxy", "extension"),
        ("Direct Connection", "direct"),
    ]
    
    for approach_name, approach_type in approaches:
        try:
            print(f" Trying {approach_name}...")
            
            if approach_type == "extension":
                chrome_options = proxy_manager.configure_selenium_with_extension()
            else:  
                chrome_options = proxy_manager.configure_selenium_without_proxy()
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.maximize_window()
            
            print(f" {approach_name} successful!")
            return driver
                
        except Exception as e:
            print(f" {approach_name} setup failed: {str(e)}")
            continue
    
    raise Exception("All connection methods failed")

print("=" * 60)
print("  ENHANCED WEB SCRAPER WITH ROTATING PROXIES")
print("=" * 60)
print(f" ScraperAPI Key: {SCRAPER_API_KEY[:10]}...")
print(f" Proxy URL: {SCRAPER_API_URL}")
print("=" * 60)

query = input("Enter what you want to search: ")
max_businesses = int(input("How many businesses do you want to scrape? "))

driver = create_driver_with_proxy()

try:
    print(f"\n Searching for: {query}")
    print(f" Target businesses: {max_businesses}")
    
    print("  Opening Bing Maps...")
    driver.get(f"https://www.bing.com/maps?q={query}")
    
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "mapContainer"))
    )
    time.sleep(3)

    print( "Loading listings...")
    body = driver.find_element(By.TAG_NAME, "body")
    for _ in range(10):
        body.send_keys(Keys.PAGE_DOWN)
        time.sleep(0.5)
    
    results = []
    page_count = 0
    total_processed = 0

    while total_processed < max_businesses:
        page_count += 1
        print(f"\n Processing page {page_count}")
        print(f" Progress: {total_processed}/{max_businesses} businesses collected")

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a.listings-item'))
            )
        except TimeoutException:
            print(" No more listings found")
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

        listings = driver.find_elements(By.CSS_SELECTOR, 'a.listings-item')
        print(f" Found {len(listings)} listings on this page")


        listings_to_process = min(len(listings), max_businesses - total_processed)
        print(f" Processing {listings_to_process} listings from this page")
        
        for idx in range(listings_to_process):
            if total_processed >= max_businesses:
                print(f" Reached target of {max_businesses} businesses!")
                break
                
            business_data = {
                "shop_name": "",
                "phone": "",
                "emails": [],
            }
            
            try:
                print(f"\n{'='*50}")
                print(f" Processing business {total_processed+1} of {max_businesses}")
                print(f" Current Proxy: {proxy_manager.current_proxy}")
                
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
                    print(" Listing element stale, skipping to next")
                    continue
                
                try:
                    phone_elem = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.CLASS_NAME, "longNum"))
                    )
                    business_data["phone"] = phone_elem.text.strip()
                    print(f" Phone: {business_data['phone']}")
                    
                except (TimeoutException, NoSuchElementException) as e:
                    print(f" Phone number not found")
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
                        print(f" Found website (aria-label): {website_url}")
                    except:
                        try:
                            website_elem = WebDriverWait(driver, 3).until(
                                EC.presence_of_element_located((By.XPATH, 
                                    "//div[contains(., 'Website')]//a[contains(@href, 'http')]"
                                ))
                            )
                            website_url = website_elem.get_attribute("href")
                            print(f" Found website (text): {website_url}")
                        except:
                            anchors = driver.find_elements(By.CSS_SELECTOR, "div.b_infocardMainDiv a[href^='http']")
                            for a in anchors:
                                href = a.get_attribute("href")
                                if href and "bing.com" not in href:
                                    website_url = href
                                    print(f" Found website (fallback): {website_url}")
                                    break
                
                except Exception as e:
                    print(f" Website extraction error: {str(e)}")
                
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
                        
                        business_data["website_name"] = get_clean_website_name_from_title(driver)
                        print(f"  Website name: {business_data['website_name']}")
                        
                        business_data["emails"] = find_emails_on_website(driver)
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
                print(f" Completed business: {business_data['shop_name']}")
                
            except Exception as e:
                print(f" Error processing listing {idx+1}: {str(e)}")
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
            print(f" Looking for next page... Need {max_businesses - total_processed} more businesses")
            
            if click_next_page(driver):
                print(" New page loaded successfully")
                # Reset listings for the new page - let the next iteration handle finding them
                print(" Ready to process next page listings")
            else:
                print(" No more pages available or pagination failed")
                break
        else:
            print(f" Target of {max_businesses} businesses reached!")
            break





finally:
    print("\ Closing driver and cleaning up...")
    driver.quit()
    proxy_manager.cleanup()
    
    print("\n" + "=" * 60)
    print( "SAVING RESULTS")
    print("=" * 60)
    
    with open("bing_maps_leads_with_proxy.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print(f" Scraping complete! Collected {len(results)} businesses.")
    print(f" Results saved to: bing_maps_leads_with_proxy.json")
    print(f" Connection method used: {proxy_manager.current_proxy}")
    print("=" * 60)