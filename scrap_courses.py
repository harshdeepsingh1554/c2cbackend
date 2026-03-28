import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

# ─── MSME-Focused Sectors ─────────────────────────────────────────────────────
MSME_SECTORS = [
 "Operations Management",
    "Project Management", "Digital Marketing",
    "Data Analytics", "Business Analytics", "Artificial Intelligence",
    "Machine Learning", "Cyber Security", "Cloud Computing", "Industrial Safety",
    "Quality Control", "Manufacturing Engineering", "Mining Engineering",
    "Civil Engineering", "Mechanical Engineering", "Electrical Engineering","computer science",
    "Human Resource Management", "Entrepreneurship"
]


# ─── Chrome Driver Factory ─────────────────────────────────────────────────────
def get_driver():
    """Headless anti-bot Chrome driver."""
    opts = Options()
    opts.binary_location = "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"
    opts.add_argument("--headless=new")                          # ✅ headless enabled
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


# ─── Shared course dict builder ────────────────────────────────────────────────
def make_course(title, link, provider, keyword, level="Free"):
    """
    Builds a course dict with ONLY columns that exist in the Supabase courses table:
        id, title, provider, duration, level, image, rating, students, field, skills, link, created_at

    Rules:
    - 'skills'  → always a Python list []  (Supabase column type is text[])
                  NEVER a string like '[]' → causes: malformed array literal error
    - 'description' → NOT included (column does not exist → causes PGRST204)
    - 'updated_at' / 'last_updated' → NOT included (don't exist → causes PGRST204)
    - 'created_at'  → NOT included (Supabase auto-fills on insert)
    - 'id'          → NOT included (Supabase auto-fills on insert)
    """
    return {
        "title":    title,
        "link":     link,
        "provider": provider,
        "field":    keyword,
        "level":    level,
        "skills":   [],      # text[] column → must be list, not string
        "duration": "",
        "image":    "",
        "rating":   None,
        "students": None,
    }


# ─── YouTube Scraper ───────────────────────────────────────────────────────────
def scrape_youtube(keyword, limit=10):
    """
    Scrapes YouTube for full course videos and playlists.
    - Scrolls 3x to force lazy-loaded titles into the DOM before collecting.
    - Uses JS innerText fallback when .text returns empty (YouTube lazy renders).
    - Skips Shorts (/shorts/ in URL).
    """
    print(f"📡 YouTube: Searching for '{keyword}' courses...")
    driver = get_driver()
    course_list = []
    url = (
        f"https://www.youtube.com/results?search_query="
        f"{keyword.replace(' ', '+')}+full+course+tutorial"
    )

    try:
        driver.get(url)

        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a#video-title"))
            )
        except Exception:
            print(f"   ⚠️  YouTube timed out for '{keyword}'")
            return []

        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(0.8)

        elements = driver.find_elements(By.CSS_SELECTOR, "a#video-title")

        for el in elements:
            if len(course_list) >= limit:
                break
            try:
                title = (
                    el.text.strip()
                    or driver.execute_script("return arguments[0].innerText;", el).strip()
                )
                link = el.get_attribute("href") or ""

                if not title or not link or "/shorts/" in link:
                    continue

                course_list.append(make_course(title, link, "YouTube", keyword, "Free"))
                print(f"   ✅ Found: {title[:60]}...")

            except (StaleElementReferenceException, Exception):
                continue

        print(f"   📊 YouTube total for '{keyword}': {len(course_list)}")
        return course_list

    finally:
        driver.quit()


# ─── Coursera Scraper ──────────────────────────────────────────────────────────
def scrape_coursera(keyword, limit=10):
    """
    Scrapes Coursera search results.

    DOM structure (verified from Chrome inspect screenshot):
        div[data-testid="product-card-cds"]        ← wait target & card root
          div.cds-CommonCard-clickArea
            ancestor <a href="/learn/...">          ← LINK
          div.cds-ProductCard-body
            div.cds-CommonCard-bodyContent
              p > strong                            ← TITLE
    """
    print(f"📡 Coursera: Searching for '{keyword}'...")
    driver = get_driver()
    course_list = []
    url = (
        f"https://www.coursera.org/search?query={keyword.replace(' ', '%20')}"
        f"&productTypeDescription=Courses"
    )

    try:
        driver.get(url)

        try:
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[data-testid='product-card-cds']")
                )
            )
        except Exception:
            print(f"   ⚠️  Coursera timed out for '{keyword}'")
            return []

        time.sleep(2)

        cards = driver.find_elements(
            By.CSS_SELECTOR, "div[data-testid='product-card-cds']"
        )

        seen_links = set()
        for card in cards:
            if len(course_list) >= limit:
                break
            try:
                title = ""
                for sel in [
                    "div.cds-CommonCard-bodyContent p",
                    "div.cds-ProductCard-body p",
                    "p",
                ]:
                    try:
                        title = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if title:
                            break
                    except NoSuchElementException:
                        continue

                if not title:
                    continue

                href = ""
                try:
                    click_area = card.find_element(
                        By.CSS_SELECTOR, "div.cds-CommonCard-clickArea"
                    )
                    parent_a = click_area.find_element(By.XPATH, "./ancestor::a[1]")
                    href = parent_a.get_attribute("href") or ""
                except NoSuchElementException:
                    try:
                        href = card.find_element(By.TAG_NAME, "a").get_attribute("href") or ""
                    except NoSuchElementException:
                        pass

                if not href or href in seen_links:
                    continue
                if href.startswith("/"):
                    href = "https://www.coursera.org" + href

                seen_links.add(href)
                course_list.append(make_course(title, href, "Coursera", keyword, "Paid/Audit"))
                print(f"   ✅ Found: {title[:60]}...")

            except (StaleElementReferenceException, Exception):
                continue

        print(f"   📊 Coursera total for '{keyword}': {len(course_list)}")
        return course_list

    finally:
        driver.quit()


# ─── SWAYAM / NPTEL Scraper ────────────────────────────────────────────────────
def scrape_swayam_nptel(keyword, limit=10):
    """Tries SWAYAM first, falls back to NPTEL directly."""
    print(f"📡 NPTEL/SWAYAM: Searching for '{keyword}'...")
    results = _scrape_swayam(keyword, limit)
    if not results:
        print(f"   ↩️  SWAYAM empty — trying NPTEL directly...")
        results = _scrape_nptel(keyword, limit)
    print(f"   📊 NPTEL/SWAYAM total for '{keyword}': {len(results)}")
    return results


def _scrape_swayam(keyword, limit):
    """
    DOM structure (verified from Chrome inspect screenshot):
        course-card  (Vue custom element)           ← wait target & card root
          a.style-scope.course-card[href="..."]     ← LINK (wraps all content)
            div.shadowBox > div.content
              h4.courseTitle > span[title="..."]
                strong                              ← TITLE TEXT
    """
    driver = get_driver()
    course_list = []
    url = f"https://swayam.gov.in/explorer?searchText={keyword.replace(' ', '%20')}"

    try:
        driver.get(url)

        try:
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "course-card"))
            )
        except Exception:
            return []

        time.sleep(2)
        cards = driver.find_elements(By.CSS_SELECTOR, "course-card")

        for card in cards:
            if len(course_list) >= limit:
                break
            try:
                title = ""
                for sel in ["h4.courseTitle span strong", "h4.courseTitle span", "h4.courseTitle"]:
                    try:
                        el = card.find_element(By.CSS_SELECTOR, sel)
                        title = el.text.strip() or el.get_attribute("title") or ""
                        if title:
                            break
                    except NoSuchElementException:
                        continue

                if not title:
                    continue

                href = ""
                try:
                    anchor = card.find_element(By.CSS_SELECTOR, "a.course-card")
                    href = anchor.get_attribute("href") or ""
                except NoSuchElementException:
                    try:
                        href = card.find_element(By.TAG_NAME, "a").get_attribute("href") or ""
                    except NoSuchElementException:
                        pass

                if not href:
                    continue
                if href.startswith("/"):
                    href = "https://swayam.gov.in" + href

                course_list.append(make_course(title, href, "NPTEL/SWAYAM", keyword, "Free"))
                print(f"   ✅ Found: {title[:60]}...")

            except (StaleElementReferenceException, Exception):
                continue

        return course_list

    finally:
        driver.quit()


def _scrape_nptel(keyword, limit):
    """Fallback: NPTEL's own search at nptel.ac.in."""
    driver = get_driver()
    course_list = []
    url = f"https://nptel.ac.in/courses/search?keyword={keyword.replace(' ', '%20')}"

    try:
        driver.get(url)

        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "li.course-item, div.course-item, div.col-sm-3")
                )
            )
        except Exception:
            return []

        time.sleep(2)
        cards = driver.find_elements(
            By.CSS_SELECTOR, "li.course-item, div.course-item, div.col-sm-3"
        )

        for card in cards:
            if len(course_list) >= limit:
                break
            try:
                title = ""
                for sel in ["p.title", "h5", "h4", "span.title", "p"]:
                    try:
                        title = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if title and len(title) > 5:
                            break
                    except NoSuchElementException:
                        continue

                href = ""
                try:
                    href = card.find_element(By.TAG_NAME, "a").get_attribute("href") or ""
                except NoSuchElementException:
                    pass

                if not title or not href:
                    continue
                if href.startswith("/"):
                    href = "https://nptel.ac.in" + href

                course_list.append(make_course(title, href, "NPTEL/SWAYAM", keyword, "Free"))
                print(f"   ✅ Found (NPTEL): {title[:60]}...")

            except (StaleElementReferenceException, Exception):
                continue

        return course_list

    finally:
        driver.quit()
