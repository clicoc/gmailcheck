from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import chromedriver_autoinstaller
import time
import os
from threading import Lock, Semaphore  # 🔒 Added for concurrency protection

# Global locks to prevent concurrent Chrome execution
selenium_lock = Lock()
semaphore = Semaphore(1)

app = Flask(__name__)

def check_gmails_with_emailscan(gmails):
    with selenium_lock:  # 🔒 Prevent concurrent Chrome drivers
        print("DEBUG: Received gmails:", gmails, flush=True)

        # 1. Set Chrome and Chromedriver path
        os.environ["PATH"] += os.pathsep + "/usr/bin"
        os.environ["GOOGLE_CHROME_BIN"] = "/usr/bin/google-chrome"

        # 2. Configure Chrome options
        chrome_options = Options()
        chrome_options.binary_location = "/usr/bin/google-chrome"
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        valid_emails = []

        try:
            driver_path = chromedriver_autoinstaller.install()
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)

            for i in range(0, len(gmails), 10):  # Batch in groups of 10
                batch = gmails[i:i+10]
                print(f"DEBUG: Batch {i//10+1} sent to emailscan.in:", batch, flush=True)
                gmails_input = "\n".join(batch)
                driver.get("https://emailscan.in")
                time.sleep(2)

                try:
                    textarea = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/main/div/div[2]/div/div[1]/div/textarea')
                    textarea.clear()
                    textarea.send_keys(gmails_input)
                    print("DEBUG: Textarea filled.", flush=True)
                except Exception as e:
                    print("ERROR: Unable to fill textarea:", e, flush=True)
                    continue

                try:
                    check_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div[2]/main/div/div[2]/div/div[2]/div[2]/div[2]/button[2]'))
                    )
                    driver.execute_script("arguments[0].click();", check_button)
                    print("DEBUG: 'Check' button clicked via JS.", flush=True)
                except Exception as e:
                    print("ERROR: Unable to click 'Check':", e, flush=True)
                    continue

                time.sleep(5)

                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.XPATH, '//div[@class="font-semibold max-w-[50vw] whitespace-nowrap text-green-500"]')
                        )
                    )

                    result_divs = driver.find_elements(
                        By.XPATH,
                        '//div[@class="font-semibold max-w-[50vw] whitespace-nowrap text-green-500"]'
                    )

                    print("DEBUG: Number of green results detected:", len(result_divs), flush=True)

                    batch_valid = []
                    for el in result_divs:
                        text = el.text.strip()
                        print(" - Result line:", text, flush=True)
                        if "|" in text and "@gmail.com" in text:
                            parts = text.split("|")
                            if len(parts) > 1:
                                email = parts[1].strip()
                                batch_valid.append(email)

                    print("DEBUG: Valid emails extracted from green results:", batch_valid, flush=True)
                    valid_emails.extend(batch_valid)
                except Exception as e:
                    print("ERROR: Could not extract valid emails from green results:", e, flush=True)

                time.sleep(2)
        except Exception as e:
            print("GLOBAL SELENIUM ERROR:", e, flush=True)
        finally:
            try:
                driver.quit()
            except:
                pass

        print("DEBUG: Total valid emails:", valid_emails, flush=True)
        return valid_emails


@app.route('/check_gmails', methods=['POST'])
def check_gmails():
    data = request.get_json()
    print("DEBUG: Received request data:", data, flush=True)

    emails_raw = data.get("emails", [])
    if not isinstance(emails_raw, list):
        gmails = [e.strip() for e in str(emails_raw).replace(",", "\n").splitlines() if e.strip()]
    else:
        gmails = emails_raw

    with semaphore:  # 🔒 Prevent concurrent access
        valid_gmails = check_gmails_with_emailscan(gmails)

    print("DEBUG: Valid emails returned:", valid_gmails, flush=True)
    return jsonify({"valid_emails": valid_gmails})


app.static_folder = "."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
