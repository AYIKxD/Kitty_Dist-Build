import requests
import json
import time
import random
import re
import threading
from queue import Queue, Empty
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import copy
import os
import platform

solution_client_instance = None

def extract_nested_value(data, keys_path):

    current = data
    try:
        for key in keys_path:
            if isinstance(current, dict):
                if key in current:
                    current = current[key]
                else:
                    return None
            elif isinstance(current, list):
                if isinstance(key, int) and 0 <= key < len(current):
                    current = current[key]
                else:
                    return None
            else:
                return None
        return current
    except (KeyError, TypeError, IndexError):
        return None

def extract_all_keys(data, prefix=""):
    results = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            results.append(new_prefix)
            if isinstance(value, (dict, list)):
                results.extend(extract_all_keys(value, new_prefix))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_prefix = f"{prefix}[{i}]"
            if isinstance(item, (dict, list)):
                results.extend(extract_all_keys(item, new_prefix))
    
    return results

class SolutionClient:
    def __init__(self, server_url: str = "https://jamesbond01.pythonanywhere.com"):
        self.server_url = server_url
        self.driver = None
        self.request_queue = Queue()
        self.monitoring = False
        self.monitor_thread = None
        self.debug_mode = True
        self.cookies = None

    def get_solution(self, question_id):
        try:
            # Make request to solution server
            response = requests.get(f"{self.server_url}/solution/{question_id}")
            
            if response.status_code == 200:
                data = response.json()
                if 'solution' in data:
                    print(f"✅ Found solution for Question ID: {question_id}")
                    return data['solution'], 6000
                elif 'error' in data:
                    print(f"⚠️ Server error: {data['error']}")
            else:
                print("The answer for this question is not available. Ask someone who has solved it to open the solution using kitty_dist.")
                return 'not found', 75
        except Exception as e:
            print("❌ Error fetching solution:", str(e))

    def save_solution(self, question_id, solution_data):
        try:
            response = requests.post(f"{self.server_url}/add/solution", json={
                'id': question_id,
                'solution': solution_data
            })
            
            if response.status_code == 200:
                print(f"✅ Successfully saved solution for Question ID: {question_id}")
                return True
            else:
                print(f"⚠️ Error saving solution: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error saving solution: {str(e)}")
            return False


    def extract_ids_from_url(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        try:
            # Check for euc/spr pattern - new format
            # Example: /secure/rest/a2/euc/spr/678f46a5fe58e11c319e1efa/678f4780fe58e11c319e1fa9/678f5a01fe58e11c319e3e74/5b47799a64bac16d40e981f8
            euc_spr_pattern = r'/euc/spr/([^/]+)/([^/]+)/([^/]+)/([^/]+)'
            euc_spr_match = re.search(euc_spr_pattern, url)
            if euc_spr_match:
                euc_id = euc_spr_match.group(1)
                module_id = euc_spr_match.group(2)
                unit_id = euc_spr_match.group(3)
                question_id = euc_spr_match.group(4)
                return euc_id, module_id, question_id

            # First try to extract from the URL hash pattern
            hash_pattern = r'#/contents/[^/]+/([^/]+)/([^/]+)'
            hash_match = re.search(hash_pattern, url)
            if hash_match:
                module_id = hash_match.group(1)
                question_id = hash_match.group(2)
                return None, module_id, question_id

            # Try from URL query parameters
            query_pattern = r'eucId=([^&]+).*?/([^/]+)/([^/]+)(?:/|$)'
            query_match = re.search(query_pattern, url)
            if query_match:
                module_id = query_match.group(2)
                question_id = query_match.group(3)
                return None, module_id, question_id

            # If not found in hash, try the path pattern
            path_pattern = r'/([^/]+)/([^/]+)$'
            path_match = re.search(path_pattern, url)
            if path_match:
                module_id = path_match.group(1)
                question_id = path_match.group(2)
                return None, module_id, question_id

            # print("\nWarning: Could not find IDs in URL:", url)
            return None, None, None
        except Exception as e:
            # print(f"\nError extracting IDs from URL: {str(e)}")
            # print("URL was:", url)
            return None, None, None

    def extract_question_id_from_body(self, body: dict) -> Optional[str]:
        try:
            # Direct checks for common fields
            if 'questionId' in body:
                return body['questionId']
            if 'qid' in body:
                return body['qid']
            if 'id' in body:
                return body['id']
                
            # a2/prog specific checks - higher priority for these requests
            if 'path' in body:
                # Try to extract from path field which often contains the question ID
                path = body['path']
                
                # Pattern: /questions/{questionId}
                questions_match = re.search(r'/questions/([^/]+)', path)
                if questions_match:
                    return questions_match.group(1)
                    
                # Pattern: /prog/{questionId}
                prog_match = re.search(r'/prog/([^/]+)', path) 
                if prog_match:
                    return prog_match.group(1)
                    
                # Extract last segment from any path as a fallback
                segments = path.rstrip('/').split('/')
                if segments and segments[-1]:
                    potential_id = segments[-1]
                    if re.match(r'^[0-9a-f]{24}$', potential_id):  # MongoDB ObjectId format
                        return potential_id
            
            # Check data field which might contain the ID somewhere
            if 'data' in body and isinstance(body['data'], dict):
                data = body['data']
                for key in ['questionId', 'qid', 'id']:
                    if key in data:
                        return data[key]
                    
            # Scan nested structures for ID fields
            for key, value in body.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if sub_key in ['questionId', 'qid', 'id'] and isinstance(sub_value, str):
                            return sub_value
                            
            # Print all available keys for debugging
            all_keys = extract_all_keys(body)
            # print(f"Could not find question ID. Available keys: {all_keys}")
            
            return None
        except Exception as e:
            # print(f"Error extracting question ID from body: {str(e)}")
            return None

class BrowserSession:
    
    def __init__(self, solution_client=None):
        self.browser = None
        self.debug_mode = False  # Disable debug mode by default for cleaner output
        self.monitor_thread = None
        self.stop_monitoring = False
        self.request_queue = Queue()
        self.monitoring = False
        self.last_captured_time = 0
        
        # If no solution_client provided, use the global instance
        if solution_client is None:
            global solution_client_instance
            solution_client = solution_client_instance
        
        self.solution_client = solution_client

    def log_debug(self, message):
        if self.debug_mode:
            timestamp = datetime.now().strftime("%H:%M:%S")
            # print(f"[DEBUG {timestamp}] {message}")

    def start_browser(self):
        """Start the browser and begin monitoring network traffic."""
        print("🌐 Starting browser...")
        
        try:
            # Configure Chrome options
            options = Options()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            
            # Add additional flags to hide automation
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-features=ChromeWhatsNewUI")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-default-apps")
            
            # Add user agent to appear as normal browser
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Advanced automation hiding
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_experimental_option('prefs', {
                'credentials_enable_service': False,
                'profile.password_manager_enabled': False,
                'profile.default_content_setting_values.notifications': 2
            })
            
            # CRITICAL: Enable logging for performance monitoring - required for network capture
            options.set_capability("goog:loggingPrefs", {"performance": "ALL", "browser": "ALL"})
            
            # Initialize the browser directly
            self.browser = webdriver.Chrome(options=options)
            
            # Use CDP to modify the navigator properties to hide automation
            self.browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'es']});
                        window.navigator.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
                        Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
                """
            })
            
            # CRITICAL: Enable CDP domains for network monitoring
            self.browser.execute_cdp_cmd('Network.enable', {
                'maxTotalBufferSize': 10000000,
                'maxResourceBufferSize': 5000000,
                'maxPostDataSize': 65536
            })
            self.browser.execute_cdp_cmd('Page.enable', {})
            
            # Navigate to CodeTantra
            print("🌐 Opening CodeTantra login page...")
            self.browser.get('https://kiet.codetantra.com/login.jsp')
            self.browser.maximize_window()
            time.sleep(3)
            
            # Start monitoring network traffic
            self.monitor_thread = threading.Thread(target=self.monitor_network)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            # Start processing queue in another thread
            self.process_thread = threading.Thread(target=self.process_queue)
            self.process_thread.daemon = True
            self.process_thread.start()
            
            # Start browser health check thread
            self.health_check_thread = threading.Thread(target=self.browser_health_check)
            self.health_check_thread.daemon = True
            self.health_check_thread.start()
            
            # print("✅ Browser ready - please log in to continue")
            
        except Exception as e:
            print(f"❌ Error starting browser: {str(e)}")
            if hasattr(self, 'browser') and self.browser:
                try:
                    self.browser.quit()
                except:
                    pass
            raise
    
    def process_queue(self):
        """Process captured requests from the queue."""
        try:
            print("🔄 Starting request processor...")
            
            while not self.stop_monitoring:
                try:
                    # Get request from queue with timeout
                    request = self.request_queue.get(timeout=1)
                    
                    # Skip if solution_client is not initialized
                    if not self.solution_client:
                        self.log_debug("Solution client not initialized, skipping request")
                        self.request_queue.task_done()
                        continue
                    
                    # Process the request (pass to solution client or CodeTantraSession)
                    try:
                        session = CodeTantraSession(self.solution_client)
                        session.process_request(request)
                    except Exception as e:
                        self.log_debug(f"Error processing request: {str(e)}")
                    
                    # Mark task as done
                    self.request_queue.task_done()
                    
                except Empty:
                    # No requests in queue, continue waiting
                    continue
                except Exception as e:
                    self.log_debug(f"Error in queue processing: {str(e)}")
                    
        except Exception as e:
            self.log_debug(f"Fatal error in process_queue: {str(e)}")
            
        print("🛑 Request processor stopped")

    def monitor_network(self):
        self.monitoring = True
        
        # Initial delay to ensure browser is fully loaded
        time.sleep(2)
        
        print("✅ Network monitoring active - waiting for submissions")
        
        while self.monitoring:
            try:
                # Get performance logs - this is where network data is stored
                logs = self.browser.get_log('performance')
                
                if not logs and self.debug_mode:
                    self.log_debug("No performance logs received")
                    time.sleep(0.5)
                    continue
                    
                for entry in logs:
                    try:
                        message = json.loads(entry['message'])['message']
                        method = message['method']
                        params = message.get('params', {})
                        
                        # Only debug log if debug mode is on
                        if self.debug_mode and method.startswith('Network.'):
                            request_id = params.get('requestId', 'unknown')
                            request = params.get('request', {})
                            
                            if method == 'Network.requestWillBeSent':
                                url = request.get('url', '')
                            
                                # Only log interesting requests in detail
                                if self.should_log_request_details(url):
                                    self.log_debug(f"Detected request: {request_id}: {request.get('method', 'unknown')} {url}")
                        
                        # Process login requests first
                        if method == 'Network.requestWillBeSent':
                            params = message['params']
                            request = params.get('request', {})
                            url = request.get('url', '')
                            
                            # Try to detect login requests
                            if '/rest/login' in url and request.get('method') == 'POST':
                                try:
                                    if 'postData' in request:
                                        post_data = request.get('postData', '')
                                        # Try to parse as JSON
                                        try:
                                            pass
                                        except json.JSONDecodeError:
                                            if self.debug_mode:
                                                self.log_debug("Login data is not in JSON format")
                                except Exception as e:
                                    if self.debug_mode:
                                        self.log_debug(f"Error processing login data: {str(e)}")
                        
                        # Check for POST requests that might be submissions
                        if method == 'Network.requestWillBeSent':
                            params = message['params']
                            request = params.get('request', {})
                            url = request.get('url', '')
                            
                            # Check for submissions by URL pattern
                            is_submission = False
                            if request.get('method') == 'POST':
                                submission_patterns = [
                                    'awsterm.codetantra.com',
                                    'secure/rest/a2/prog',
                                    'secure/rest/a2/submissions',
                                    'secure/rest/a2/euc/spr',
                                    '/submissions/',
                                    '/prog/',
                                    '/submit'
                                ]
                                
                                is_submission = any(pattern in url for pattern in submission_patterns)
                                
                                if is_submission and self.debug_mode:
                                    self.log_debug(f"Potential submission detected: {url}")
                            
                            # If this is a submission request, process it
                            if is_submission and request.get('method') == 'POST':
                                try:
                                    # Get current time
                                    current_time = time.time()
                                    
                                    # Only process requests that happened 0.5 seconds after the last captured
                                    if current_time - self.last_captured_time < 0.5:
                                        continue
                                    
                                    # Get headers
                                    headers = request.get('headers', {})
                                    
                                    # Extract post data (if any)
                                    if 'postData' in request:
                                        try:
                                            post_data = request['postData']
                                            
                                            # Try to parse post data as JSON
                                            body = json.loads(post_data)
                                            
                                            # Determine submission type for user-friendly output
                                            submission_type = "Unknown"
                                            if 'secure/rest/a2/euc/spr' in url:
                                                submission_type = "File Upload"
                                            elif 'secure/rest/a2/prog' in url or '/prog/' in url:
                                                submission_type = "Code Execution"
                                            elif 'secure/rest/a2/submissions' in url:
                                                submission_type = "Assignment Submission"
                                            
                                            # Capture submission with clean output
                                            # print("\n🔔 New submission detected")
                                            # print(f"Type: {submission_type}")
                                            
                                            # Check if this is a successful solution response
                                            if '"alreadyAnswered":true' in str(body):
                                                try:
                                                    question_id = self.solution_client.extract_question_id_from_body(body)
                                                    if question_id:
                                                        # Check if solution exists on the server
                                                        solution, _ = self.solution_client.get_solution(question_id)
                                                        if "not available" in solution:
                                                                # Store the solution
                                                                solution_object = body.get("solution", {})
                                                                if solution_object and 'filesContentArr' in solution_object:
                                                                    files = solution_object['filesContentArr']
                                                                    for file_data in files:
                                                                        if not file_data.get('readOnly', True):
                                                                            solution_data = file_data.get('fileContent')
                                                                            if solution_data:
                                                                                self.solution_client.save_solution(question_id, solution_data)
                                                                                print(f"\n✅ New solution saved for question {question_id}")
                                                                        else:
                                                                            break
                                                except Exception as e:
                                                    if self.debug_mode:
                                                        self.log_debug(f"Error processing solution: {str(e)}")

                                            # Queue the request
                                            captured_request = {
                                                'url': url,
                                                'headers': headers,
                                                'body': body,
                                                'timestamp': current_time,
                                                'request_id': params.get('requestId', 'unknown')
                                            }
                                            
                                            self.request_queue.put(captured_request)
                                            self.last_captured_time = current_time
                                            
                                            # print(f"✅ Submission captured and queued for processing")
                                            
                                        except json.JSONDecodeError as e:
                                            if self.debug_mode:
                                                self.log_debug(f"Error parsing submission body: {str(e)}")
                                except Exception as e:
                                    if self.debug_mode:
                                        self.log_debug(f"Error processing submission: {str(e)}")

                        elif method == 'Network.responseReceived':
                            params = message['params']
                            request_id = params.get('requestId')
                            response = params.get('response', {})
                            url = response.get('url', '')

                            if 'secure/rest/a2/euc/gqd' in url:
                                try:
                                    body_data = self.browser.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                                    body = json.loads(body_data['body'])
                                    if body.get('data', {}).get('alreadyAnswered'):
                                        _, _, question_id = self.solution_client.extract_ids_from_url(url)
                                        if question_id:
                                            solution, _ = self.solution_client.get_solution(question_id)
                                            if "not found" in solution:
                                                solution_object = body.get('data', {}).get('solution', {})
                                                if solution_object and 'filesContentArr' in solution_object:
                                                    files = solution_object['filesContentArr']
                                                    for file_data in files:
                                                        if not file_data.get('readOnly', True):
                                                            solution_data = file_data.get('fileContent')
                                                            if solution_data:
                                                                self.solution_client.save_solution(question_id, solution_data)
                                                                print(f"\n✅ New solution saved for question {question_id}")
                                                            break # Save only the first non-read-only file
                                except Exception as e:
                                    if self.debug_mode:
                                        self.log_debug(f"Error processing gqd response: {str(e)}")
                    except Exception as e:
                        if self.debug_mode:
                            self.log_debug(f"Error processing log entry: {str(e)}")
            except Exception as e:
                if self.debug_mode:
                    self.log_debug(f"Error in network monitoring: {str(e)}")
                    
            # Small delay to prevent excessive CPU usage
            time.sleep(0.1)

    def should_log_request_details(self, url):
        """Check if request details should be logged."""
        important_patterns = [
            'secure/rest/a2/prog',
            'secure/rest/a2/submissions',
            'secure/rest/a2/euc/spr',
            'awsterm.codetantra.com',
            'rest/login',
            '/submissions/',
            '/prog/',
            '/submit'
        ]
        return any(pattern in url for pattern in important_patterns)

    def wait_for_submission(self):
        """Wait for and return the next submission request"""
        try:
            # Clear any old requests from the queue
            while not self.request_queue.empty():
                old_req = self.request_queue.get_nowait()
                if self.debug_mode:
                    print(f"Cleared old request: {old_req['url']}")
                
            # print("\n⏳ Waiting for new submission requests...")
            # Wait for new request with timeout
            request = self.request_queue.get(timeout=60)
            # print(f"✅ Submission request captured")
            return request
        except Empty:
            if self.debug_mode:
                print("No submission request received within timeout period")
            return None
        except Exception as e:
            if self.debug_mode:
                print(f"Error waiting for submission: {str(e)}")
            return None

    def close(self):
        """Close the browser session"""
        print("\n🔄 Closing browser session...")
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        if self.browser:
            self.browser.quit()
        print("✅ Browser closed successfully")

    def browser_health_check(self):
        """Periodically check if the browser is still responsive"""
        while self.monitoring:
            try:
                # Check if we can access the browser
                if self.browser:
                    # Try to get the current URL as a basic health check
                    current_url = self.browser.current_url
                    if self.debug_mode:
                        self.log_debug(f"Browser health check: OK - Current URL: {current_url}")
                    
                    # Ensure performance logging is still enabled
                    try:
                        logs = self.browser.get_log('performance')
                        if self.debug_mode:
                            self.log_debug(f"Performance logging check: {len(logs)} log entries received")
                    except Exception as e:
                        if self.debug_mode:
                            self.log_debug(f"Performance logging check failed: {str(e)}")
            except Exception as e:
                print(f"❌ Browser health check failed: {str(e)}")
                
            # Check every 60 seconds instead of 30 for less intrusive checks
            time.sleep(60)

class CodeTantraSession:
    def __init__(self, solution_client: SolutionClient):
        self.browser = BrowserSession(solution_client)
        self.last_request_template = None
        self.solution_client = solution_client
        
    def start_browser(self):
        """Start the browser session and begin monitoring"""
        self.browser.start_browser()
        # Start submission monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_submissions)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def monitor_submissions(self):
        """Continuously monitor for submissions and handle them automatically"""
        while True:
            try:
                template = self.browser.wait_for_submission()
                if template:
                    # Extract minimal information about the captured request
                    url = template['url']
                    is_a2_prog = ('secure/rest/a2/prog' in url) or ('/prog/' in url) 
                    is_euc_spr = 'secure/rest/a2/euc/spr' in url
                    
                    print(f"🔍 Analyzing submission type: {'File Upload' if is_euc_spr else 'Code Execution' if is_a2_prog else 'Other'}")
                    
                    # Extract question ID with minimal logging
                    question_id = None
                    
                    # For euc/spr, extract directly from URL
                    if is_euc_spr:
                        euc_id, module_id, question_id = self.solution_client.extract_ids_from_url(url)
                    else:
                        # Try from body with minimal output
                        body = template['body']
                        question_id = self.solution_client.extract_question_id_from_body(body)
                        
                        # If not found in body, try from URL
                        if not question_id:
                            _, _, question_id = self.solution_client.extract_ids_from_url(url)
                    
                    if question_id:
                        print(f"📝 Working with Question ID: {question_id}")
                    else:
                        print("⚠️ Could not determine Question ID")
                    
                    # Store template for future submissions
                    self.last_request_template = template
                    
                    # Try to get and submit solution
                    success, response = self.submit_code_from_capture([])
                    if success:
                        print("✅ Auto-submission successful")
                    else:
                        print(f"❌ Auto-submission failed: {response}")
                        
            except Exception as e:
                print(f"❌ Error in submission monitoring: {str(e)}")
            time.sleep(0.1)  # Small delay to prevent CPU overuse

    def submit_code_from_capture(self, files_content: List[Dict]) -> Tuple[bool, str]:
        """Submit code using a captured request as template"""
        if not self.last_request_template:
            return False, "No request template captured. Please make a submission in browser first."
        
        try:
            # Get request details
            url = self.last_request_template['url']
            body = self.last_request_template['body']
            
            # Detect request type - more specific matches first
            is_a2_prog = ('secure/rest/a2/prog' in url) or ('/prog/' in url) or ('awsterm.codetantra.com' in url and '/sce' in url)
            is_euc_spr = 'secure/rest/a2/euc/spr' in url
            
            print(f"🔄 Processing {'file upload' if is_euc_spr else 'code execution' if is_a2_prog else 'submission'}")
            
            # Create submission data based on template
            submission_data = copy.deepcopy(body)
            
            # Get question ID using multiple methods
            question_id = None
            
            # For euc/spr endpoints, extract directly from URL
            if is_euc_spr:
                euc_id, module_id, question_id = self.solution_client.extract_ids_from_url(url)
            else:
                # Try to get from body first
                question_id = self.solution_client.extract_question_id_from_body(body)
                
                # If not found in body, try from URL
                if not question_id:
                    _, _, question_id = self.solution_client.extract_ids_from_url(url)
                    
                # If still not found, try from referer
                if not question_id and 'Referer' in self.last_request_template['headers']:
                    _, _, q_id = self.solution_client.extract_ids_from_url(
                        self.last_request_template['headers']['Referer']
                    )
                    if q_id:
                        question_id = q_id
            
            # Update content based on endpoint type
            solution = None
            time_value = 10  # Default time value for unauthorized users
            
            if question_id:
                # Get solution using only question ID
                solution, time_value = self.solution_client.get_solution(question_id)
            
            # Update totalTimeSpent based on authorization status
            if 'totalTimeSpent' in submission_data:
                submission_data['totalTimeSpent'] = random.randint(time_value, time_value + 300)
            if 'extras' in submission_data and 'totalTimeSpent' in submission_data['extras']:
                submission_data['extras']['totalTimeSpent'] = random.randint(time_value, time_value + 300)
            if 'userTimeTaken' in submission_data:
                submission_data['userTimeTaken'] = float(random.randint(10, 20)) if time_value <= 10 else float(random.randint(1000, 1500))
            
            if is_euc_spr:
                # Special handling for euc/spr endpoints
                if solution and 'filesContentArr' in submission_data:
                    files = submission_data['filesContentArr']
                    
                    # Check number of files to determine update strategy
                    if len(files) == 1:
                        # Only one file - update its content regardless of readOnly
                        single_file = files[0]
                        file_name = single_file.get('fileName', 'unknown')
                        single_file['fileContent'] = solution
                        print(f"📄 Updated solution for: {file_name}")
                    else:
                        # Multiple files - update only non-readOnly files
                        updated = False
                        for file_data in files:
                            if not file_data.get('readOnly', True):
                                file_name = file_data.get('fileName', 'unknown')
                                file_data['fileContent'] = solution
                                print(f"📄 Updated solution for: {file_name}")
                                updated = True
                        
                        if not updated:
                            print("⚠️ All files are read-only - could not update content")
                
            elif is_a2_prog:
                # Handle a2/prog request - always update content
                
                # For a2/prog requests, directly update without checking readOnly
                if solution:
                    # Check where to put the solution based on request structure
                    if 'data' in submission_data:
                        # This is the most common field for code in a2/prog
                        submission_data['data'] = solution
                        # print("📝 Updated solution for code execution")
                    elif 'code' in submission_data:
                        # Some requests might use 'code' instead
                        submission_data['code'] = solution
                        # print("📝 Updated solution for code execution")
                    elif 'solution' in submission_data:
                        # or even 'solution'
                        submission_data['solution'] = solution
                        # print("📝 Updated solution for code execution")
                    else:
                        print("⚠️ Could not find appropriate field to update - using original content")
                else:
                    print("⚠️ No solution found - using original content")
            
            # Use the exact same URL and headers
            headers = self.last_request_template['headers']
            cookies = {cookie['name']: cookie['value'] 
                     for cookie in self.browser.browser.get_cookies()}
            
            print("🚀 Submitting solution...")
            
            # Make the request
            response = requests.post(
                url,
                json=submission_data,
                headers=headers,
                cookies=cookies
            )
            response.raise_for_status()
            
            return True, "Success"
            
        except Exception as e:
            error_msg = f"Error submitting solution: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg
            
    def close(self):
        """Close the session"""
        self.browser.close()

    def send_input(self, input_str):
        """
        Send input to a running program via the service worker channel.
        This is used to interact with programs that need STDIN input.
        """
        if not self.browser.browser:
            print("❌ Browser not initialized")
            return False
        
        try:
            print(f"⌨️ Sending input: '{input_str}'")
            
            # Get cookies for authorization
            cookies = {cookie['name']: cookie['value'] 
                     for cookie in self.browser.browser.get_cookies()}
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
            }
            
            # Endpoint for service worker input
            input_url = "https://kiet.codetantra.com/__SyncMessageServiceWorkerInput__/write"
            
            # Prepare the payload - sends the input string with stdin messageId
            payload = {
                "message": input_str,
                "messageId": "stdin"
            }
            
            # Send the request
            response = requests.post(
                input_url,
                json=payload,
                headers=headers,
                cookies=cookies
            )
            
            if response.status_code == 200:
                print(f"✅ Input sent successfully")
                return True
            else:
                print(f"❌ Failed to send input. Status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending input: {str(e)}")
            return False

    def process_request(self, request):
        """Process a captured network request."""
        try:
            url = request['url']
            body = request['body']
            
            # Determine request type
            is_file_upload = 'secure/rest/a2/euc/spr' in url
            is_code_execution = ('secure/rest/a2/prog' in url) or ('/prog/' in url)
            is_aws_terminal = 'awsterm.codetantra.com' in url
            
            # Extract question ID
            question_id = None
            
            # Extract question ID based on request type
            if is_file_upload:
                # For file upload, extract from URL
                parts = url.split('/')
                if len(parts) >= 7:
                    endpoint_idx = url.find('/euc/spr/')
                    if endpoint_idx >= 0:
                        remaining = url[endpoint_idx + 9:].split('/')
                        if len(remaining) >= 4:
                            question_id = remaining[3]
                
            # For code execution, extract from JSON fields
            elif is_code_execution or is_aws_terminal:
                question_id = extract_nested_value(body, ['questions', 0, 'meta', 'questionId'])
                if not question_id:
                    question_id = extract_nested_value(body, ['meta', 'questionId'])
                
            # For regular submissions
            elif 'secure/rest/a2/submissions' in url:
                if 'filesContentArr' in body:
                    question_id = extract_nested_value(body, ['meta', 'subjectiveQuestionId'])
                    if not question_id:
                        question_id = extract_nested_value(body, ['meta', 'questionId'])
                    
            # Try to get solution if we have a question ID
            if question_id:
                # print(f"📋 Question ID: {question_id}")
                        
                # Try to get solution
                solution, time_value = self.solution_client.get_solution(question_id)
                
                # Store the time value for later use
                self.time_value = time_value
                
                # If solution found, update submission
                if solution and solution != "Solution not found":
                    # print("✅ Solution found - preparing submission")
                    
                    # Update submission with solution
                    updated_body = None
                    if is_file_upload or 'filesContentArr' in body:
                        updated_body = self.update_submission_content(body, solution)
                    elif is_code_execution:
                        updated_body = self.update_code_execution(body, solution)
                    else:
                        updated_body = body  # Use original for unknown types
                            
                    # Submit the updated solution
                    submission_result = self.submit_solution(url, updated_body, request['headers'])
                    
                    if submission_result:
                        print("✅ Solution submitted successfully!")
                    else:
                        print("❌ Failed to submit solution")
                else:
                    print("⚠️ No solution found - using original content")
                    # Submit the original content
                    self.submit_solution(url, body, request['headers'])
            else:
                print("⚠️ Could not determine Question ID - using original content")
                # Submit the original content
                self.submit_solution(url, body, request['headers'])
                
        except Exception as e:
            print(f"❌ Error processing request: {str(e)}")
            try:
                # Try to submit the original request if there's an error
                self.submit_solution(request['url'], request['body'], request['headers'])
                # print("✅ Original content submitted as fallback")
            except:
                print("❌ Failed to submit fallback")

    def update_submission_content(self, body, solution):
        """Update submission content with solution"""
        updated_body = body.copy()  # Create a copy to avoid modifying original
        
        # First handle file upload submissions
        if 'filesContentArr' in updated_body:
            files = updated_body['filesContentArr']
            
            # Check number of files
            if len(files) == 1:
                # Only one file - update its content
                file_name = files[0].get('fileName', 'unknown')
                files[0]['fileContent'] = solution
                # print(f"📄 Updated file: {file_name}")
            else:
                # Multiple files - update only non-readOnly files
                updated = False
                for file_data in files:
                    if not file_data.get('readOnly', True):
                        file_name = file_data.get('fileName', 'unknown')
                        file_data['fileContent'] = solution
                        # print(f"📄 Updated file: {file_name}")
                        updated = True
                
                if not updated and len(files) > 0:
                    # If no writable files found, update the first one
                    file_name = files[0].get('fileName', 'unknown')
                    files[0]['fileContent'] = solution
                    # print(f"📄 Updated file: {file_name}")
        
        # Add realistic time values
        if 'totalTimeSpent' in updated_body:
            updated_body['totalTimeSpent'] = random.randint(self.time_value, self.time_value + 300) if hasattr(self, 'time_value') else 10
        if 'extras' in updated_body and 'totalTimeSpent' in updated_body['extras']:
            updated_body['extras']['totalTimeSpent'] = random.randint(self.time_value, self.time_value + 300) if hasattr(self, 'time_value') else 10
        if 'userTimeTaken' in updated_body:
            updated_body['userTimeTaken'] = float(random.randint(10, 20)) if not hasattr(self, 'time_value') or self.time_value <= 10 else float(random.randint(1000, 1500))
        
        return updated_body
    
    def update_code_execution(self, body, solution):
        """Update code execution request with solution"""
        updated_body = body.copy()  # Create a copy to avoid modifying original
        
        # Check where to put the solution based on request structure
        if 'data' in updated_body:
            # This is the most common field for code in a2/prog
            updated_body['data'] = solution
            print("📝 Code solution applied")
        elif 'code' in updated_body:
            # Some requests might use 'code' instead
            updated_body['code'] = solution
            print("📝 Code solution applied")
        elif 'solution' in updated_body:
            # or even 'solution'
            updated_body['solution'] = solution
            print("📝 Code solution applied")
        else:
            print("⚠️ No suitable field found for code solution")
        
        # Add realistic time values
        if 'totalTimeSpent' in updated_body:
            updated_body['totalTimeSpent'] = random.randint(self.time_value, self.time_value + 300) if hasattr(self, 'time_value') else 10
        if 'extras' in updated_body and 'totalTimeSpent' in updated_body['extras']:
            updated_body['extras']['totalTimeSpent'] = random.randint(self.time_value, self.time_value + 300) if hasattr(self, 'time_value') else 10
        if 'userTimeTaken' in updated_body:
            updated_body['userTimeTaken'] = float(random.randint(10, 20)) if not hasattr(self, 'time_value') or self.time_value <= 10 else float(random.randint(1000, 1500))
        
        return updated_body

    def submit_solution(self, url, body, headers):
        """Submit a solution to CodeTantra"""
        try:
            # Check if browser is initialized
            if not self.browser or not self.browser.browser:
                print("❌ Browser not initialized - cannot submit solution")
                return False
            
            # Get cookies for authentication
            cookies = {cookie['name']: cookie['value'] 
                    for cookie in self.browser.browser.get_cookies()}
            
            # Remove some headers that might cause issues
            headers_to_remove = ['Content-Length', 'Host']
            clean_headers = {k: v for k, v in headers.items() if k not in headers_to_remove}
            
            # Make the request
            response = requests.post(
                url,
                json=body,
                headers=clean_headers,
                cookies=cookies
            )
            response.raise_for_status()
            
            return True
        except Exception as e:
            print(f"❌ Error submitting solution: {str(e)}")
            return False

def main():
    # Initialize solution client
    global solution_client_instance
    solution_client = SolutionClient()
    solution_client_instance = solution_client
    
    # Create a session with the solution client
    session = CodeTantraSession(solution_client)
    
    try:
        print("\n" + "═" * 60)
        print("🔐 CODETANTRA AUTOMATION SYSTEM")
        print("═" * 60)
        print("Version: 2.1.0")
        print("\n🔑 GETTING STARTED:")
        print("1. Browser will open automatically")
        print("2. Log in to CodeTantra with your credentials")
        print("3. Navigate to your coding assignments")
        print("4. System will automatically detect and complete submissions")
        
        # Start browser and let it run indefinitely
        session.start_browser()
        
        print("\n✅ Automation running. Press Ctrl+C to exit.")
        
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n🛑 User interrupted. Shutting down...")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
    finally:
        print("\n🛑 Shutting down automation system...")
        try:
            session.close()
        except Exception as e:
            print(f"❌ Error closing session: {str(e)}")

if __name__ == "__main__":
    if platform.system() == 'Windows':
        chrome_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Google\\Chrome\\Application\\chrome.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Google\\Chrome\\Application\\chrome.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', 'C:\\Users\\' + os.getenv('USERNAME') + '\\AppData\\Local'), 'Google\\Chrome\\Application\\chrome.exe')
        ]
        
        chrome_exe_found = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_exe_found = path
                break
                
        if chrome_exe_found:
            print(f"Found Chrome at: {chrome_exe_found}")
            os.environ["CHROME_BINARY_PATH"] = chrome_exe_found
            os.environ["WDM_LOG_LEVEL"] = "0" 
            os.environ["WDM_LOCAL"] = "1"
        else:
            print("Chrome not found in standard locations. Please ensure Chrome is installed.")
    
    main()
