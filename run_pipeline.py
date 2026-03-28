import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client
from scrap import scrape_detailed_naukri, SECTORS
from scrap_courses import scrape_coursera, scrape_swayam_nptel, scrape_youtube, MSME_SECTORS

load_dotenv()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# ─── COURSE PIPELINE (MSME Focus) ─────────────────────────────────────────────
# Add scrape_youtube to your imports


def run_course_pipeline():
    print(f"📚 Course Pipeline started at {datetime.now()}")
    
    selected_key = random.choice(MSME_SECTORS)
    all_courses = []
    
    try:
        # 1. Scrape from all three sources
        all_courses.extend(scrape_coursera(keyword=selected_key, limit=5))
        all_courses.extend(scrape_swayam_nptel(keyword=selected_key, limit=5))
        all_courses.extend(scrape_youtube(keyword=selected_key, limit=5))

        if not all_courses:
            print(f"No courses found for: {selected_key}")
            return

        # 2. Format for Supabase (Handling link duplicates)
        # ── Confirmed Supabase courses columns ──────────────────────────────────
        # id, title, provider, duration, level, image, rating, students,
        # field, skills, link, created_at
        #
        # RULES:
        # - 'skills'   → list []  (Supabase type is text[]; string '[]' → CRASHES)
        # - 'description', 'updated_at', 'last_updated' → NOT sent (don't exist)
        # - 'id', 'created_at' → NOT sent (Supabase auto-fills)
        # - upsert on_conflict="link" works because you ran:
        #   ALTER TABLE courses ADD CONSTRAINT courses_link_key UNIQUE (link);
        db_entries = []
        seen_links = set()
        for c in all_courses:
            if not c.get('link') or c['link'] in seen_links:
                continue
            skills_val = c.get('skills', [])
            # Guard: if something accidentally passed a string, convert to list
            if isinstance(skills_val, str):
                skills_val = [s.strip() for s in skills_val.split(',') if s.strip()]
            db_entries.append({
                "title":    c.get('title', ''),
                "link":     c['link'],
                "provider": c.get('provider', ''),
                "field":    c.get('field', selected_key),
                "level":    c.get('level', 'Beginner'),
                "skills":   skills_val,   # text[] → must be Python list
                "duration": c.get('duration', ''),
                "image":    c.get('image', ''),
                "rating":   c.get('rating', None),
                "students": c.get('students', None),
            })
            seen_links.add(c['link'])

        # 3. Upsert into Supabase (requires UNIQUE constraint on 'link')
        supabase.table('courses').upsert(db_entries, on_conflict="link").execute()
        print(f"✅ Courses DB Updated. Processed {len(db_entries)} courses for {selected_key}.")

    except Exception as e:
        print(f"❌ Course Pipeline Error: {e}")

# ─── DATA CLEANING LOGIC (AI Optimization) ────────────────────────────────────

def clean_data(text, is_skills=False):
    """Normalizes text for better AI matching and matching consistency."""
    if not text or text == "Not Found": return ""
    if is_skills:
        # Deduplicate and sort skills alphabetically
        skills = {s.strip().title() for s in str(text).split(',')}
        return ", ".join(sorted(list(skills)))
    
    # Remove junk from titles that shifts AI vectors
    noise = ["Immediate Joiner", "Urgent Hiring", "Hiring For", "Urgent Requirement"]
    clean_title = text.title()
    for word in noise:
        clean_title = clean_title.replace(word.title(), "")
    return clean_title.strip()

# ─── JOB PIPELINE (Jharkhand Diversity) ───────────────────────────────────────

def run_automated_pipeline():
    print(f"🚀 Starting Multi-Source Job Pipeline at {datetime.now()}")
    try:
        # 1. Scraping Phase
        raw_jobs = []
        
        # A. Naukri General Feed
        raw_jobs.extend(scrape_detailed_naukri(keyword="jobs", limit=15))
        
        # B. TimesJobs (Added this)
        from scrap import scrape_timesjobs
        raw_jobs.extend(scrape_timesjobs(keyword="Engineering", limit=10))
        
        # C. Shine.com (Added this)
        from scrap import scrape_shine
        raw_jobs.extend(scrape_shine(keyword="Management", limit=10))
        
        # D. Random MSME Sector
        sector = random.choice([s for s in SECTORS if s not in ["IT", "Software"]])
        raw_jobs.extend(scrape_detailed_naukri(keyword=sector, limit=5))


        # 2. Cleaning & Deduplicating by Link
        unique_entries = {}
        for job in raw_jobs:
            link = job.get("Link")
            if not link: continue
            
            unique_entries[link] = {
                "title": clean_data(job.get("Job Title")),
                "link": link,
                "industry": job.get("Industry"),
                "skills": clean_data(job.get("Key Skills"), is_skills=True),
                "description": job.get("Description", ""),
                "last_seen": datetime.now().isoformat()
            }

        # 3. Push to Supabase
        db_entries = list(unique_entries.values())
        if db_entries:
            supabase.table('jobs').upsert(db_entries, on_conflict="link").execute()
            print(f"✅ Upserted {len(db_entries)} unique, cleaned jobs.")
            
    except Exception as e:
        print(f"❌ Pipeline Error: {e}")

# ─── MAIN EXECUTION ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run both pipelines to ensure data variety
    run_automated_pipeline()
    run_course_pipeline()