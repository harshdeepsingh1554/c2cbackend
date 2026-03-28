import pandas as pd
import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import random

# 1. Broadened Sectors for Jharkhand (Mining, Steel, Sales, etc.)
SECTORS = [
    "Manufacturing", "MSME", "Mining", "Steel", "Power", "Logistics", 
    "Automobile", "Construction", "Agriculture", "Sales", "Banking", 
    "Healthcare", "Retail", "Teaching", "Office-Assistant", "Security",
    "Hospitality", "Data-Entry"
]

chrome_options = Options()
chrome_options.add_argument("--headless") 
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
chrome_options.add_argument("--start-maximized")

def get_meta_data(driver, label_name):
    strategies = [
        f"//*[contains(text(), '{label_name}')]/following-sibling::*[1]",
        f"//*[contains(text(), '{label_name}')]/../*[2]",
        f"//div[contains(@class, 'details')]//label[contains(text(), '{label_name}')]/following-sibling::span"
    ]
    for xpath in strategies:
        try:
            element = driver.find_element(By.XPATH, xpath)
            text = element.text.strip()
            if text and len(text) > 1: return text
        except: continue
    return "Not Found"

def get_text_by_label(driver, label_text):
    try:
        xpath = f"//*[contains(text(), '{label_text}')]/following-sibling::*"
        element = driver.find_element(By.XPATH, xpath)
        return element.text.strip()
    except: return "Not Found"

def scrape_detailed_naukri(keyword="jobs", limit=20):
    """
    keyword="jobs" will trigger the generic 'jobs-in-jharkhand' search
    """
    driver = webdriver.Chrome(options=chrome_options)
    job_list = []
    
    # URL Logic: If keyword is 'jobs', it fetches the general feed
    search_term = f"{keyword.lower()}-" if keyword.lower() != "jobs" else ""
    url = f"https://www.naukri.com/{search_term}jobs-in-jharkhand"
    
    print(f"🌐 Accessing: {url}")
    
    try:
        driver.get(url)
        time.sleep(5) 

        # Scroll to load dynamic content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        jobs = driver.find_elements(By.CLASS_NAME, "srp-jobtuple-wrapper")
        
        # Limit the search to prevent infinite loops
        for i in range(min(len(jobs), limit)):
            try:
                current_jobs = driver.find_elements(By.CLASS_NAME, "srp-jobtuple-wrapper")
                job_card = current_jobs[i]
                
                title_el = job_card.find_element(By.CLASS_NAME, "title")
                title = title_el.text
                job_url = title_el.get_attribute("href")

                # Navigate to detail page
                driver.execute_script("arguments[0].click();", title_el)
                time.sleep(3)
                driver.switch_to.window(driver.window_handles[1])
                driver.execute_script("window.scrollTo(0, 600);")
                time.sleep(2)

                # Extract Details
                description = "Not Found"
                try:
                    desc_el = driver.find_element(By.CLASS_NAME, "job-desc")
                    description = desc_el.text.strip()
                except:
                    description = "Contact employer for details."

                job_list.append({
                    "Job Title": title,
                    "Link": job_url,
                    "Role": get_meta_data(driver, "Role"),
                    "Industry": get_meta_data(driver, "Industry Type"),
                    "Department": get_meta_data(driver, "Department"),
                    "Education (UG)": get_text_by_label(driver, "UG:"),
                    "Education (PG)": get_text_by_label(driver, "PG:"),
                    "Key Skills": ", ".join([s.text for s in driver.find_elements(By.XPATH, "//*[contains(text(), 'Key Skills')]/following-sibling::div//a")]) or "Not Found",
                    "Description": description[:2000]
                })
                
                print(f"   ✅ Captured: {title[:30]}...")
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            except Exception as e:
                if len(driver.window_handles) > 1: driver.close()
                driver.switch_to.window(driver.window_handles[0])
                continue

        return job_list
    finally:
        driver.quit()

def scrape_timesjobs(keyword="jobs", limit=10):
    """Scraper for TimesJobs - Generally easier to parse than LinkedIn."""
    driver = webdriver.Chrome(options=chrome_options)
    job_list = []
    
    # URL targeting Jharkhand specifically
    search_term = keyword.replace(" ", "+")
    url = f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={search_term}&txtLocation=Jharkhand"
    
    print(f"🌐 Accessing TimesJobs: {url}")
    
    try:
        driver.get(url)
        time.sleep(5)
        
        jobs = driver.find_elements(By.CLASS_NAME, "job-flex")
        
        for i in range(min(len(jobs), limit)):
            try:
                job_card = jobs[i]
                title_el = job_card.find_element(By.TAG_NAME, "h2").find_element(By.TAG_NAME, "a")
                title = title_el.text.strip()
                job_url = title_el.get_attribute("href")
                company = job_card.find_element(By.CLASS_NAME, "joblist-comp-name").text.strip()
                
                job_list.append({
                    "Job Title": title,
                    "Link": job_url,
                    "Role": keyword.capitalize(),
                    "Industry": "Various",
                    "Department": "Not Specified",
                    "Education (UG)": "See Link",
                    "Education (PG)": "See Link",
                    "Key Skills": "Check description",
                    "Description": f"Job at {company}. View details on TimesJobs."
                })
                print(f"   ✅ TimesJobs: {title[:20]}...")
            except: continue
            
        return job_list
    finally:
        driver.quit()

def scrape_shine(keyword="jobs", limit=10):
    """Scraper for Shine.com - Major Indian portal."""
    driver = webdriver.Chrome(options=chrome_options)
    job_list = []
    
    # Targeting Jharkhand
    url = f"https://www.shine.com/job-search/{keyword.lower()}-jobs-in-jharkhand"
    
    print(f"🌐 Accessing Shine: {url}")
    
    try:
        driver.get(url)
        time.sleep(5)
        
        # Shine uses different card classes; searching for the main container
        jobs = driver.find_elements(By.CSS_SELECTOR, "div[itemprop='itemListElement']")
        
        for i in range(min(len(jobs), limit)):
            try:
                job_card = jobs[i]
                title_el = job_card.find_element(By.TAG_NAME, "h2").find_element(By.TAG_NAME, "a")
                title = title_el.text.strip()
                job_url = title_el.get_attribute("href")
                
                job_list.append({
                    "Job Title": title,
                    "Link": job_url,
                    "Role": keyword.capitalize(),
                    "Industry": "Check Shine.com",
                    "Department": "Check Shine.com",
                    "Education (UG)": "Not Listed",
                    "Education (PG)": "Not Listed",
                    "Key Skills": "Check Shine.com",
                    "Description": f"Active vacancy found on Shine.com for {title}."
                })
                print(f"   ✅ Shine: {title[:20]}...")
            except: continue
            
        return job_list
    finally:
        driver.quit()

if __name__ == "__main__":
    # 1. Always start with a General search to ensure variety
    print("🚀 Starting Diverse Job Scrape for Jharkhand...")
    all_results = []
    
    # Scrape general jobs first
    print("\n➡️ Phase 1: Scraping General Jharkhand Job Feed")
    all_results.extend(scrape_detailed_naukri(keyword="jobs", limit=10))

    # 2. Pick 3 random non-IT sectors
    diverse_sectors = [s for s in SECTORS if s not in ["IT", "Software"]]
    selected = random.sample(diverse_sectors, 3)
    
    for sector in selected:
        print(f"\n➡️ Phase 2: Scraping Sector: {sector}")
        all_results.extend(scrape_detailed_naukri(keyword=sector, limit=5))

    # 3. Shuffle results so the dashboard feels random
    random.shuffle(all_results)

    # 4. Save to CSV (for the AI Engine to read)
    filename = "data/jharkhand_jobs.csv"
    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame(all_results)
    df.to_csv(filename, index=False)
    
    print(f"\n🎉 Successfully saved {len(all_results)} diverse jobs to {filename}")