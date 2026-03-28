from core.shared_utils import nlp
import spacy

class CareerEngine:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.jobs_data = []
        self.refresh_cache()

    def refresh_cache(self):
        """Syncs jobs from Supabase and pre-computes vectors."""
        try:
            print("🔍 Engine: Syncing with Supabase...")
            response = self.supabase.table('jobs').select("*").execute()
            raw_data = response.data or []
            
            processed = []
            for job in raw_data:
                # Store spaCy docs in memory for instant similarity checks
                job['title_doc'] = nlp(job.get('title', ''))
                job['skills_doc'] = nlp(job.get('skills', ''))
                processed.append(job)
            
            self.jobs_data = processed
            print(f"✅ Engine: Cached {len(self.jobs_data)} jobs.")
        except Exception as e:
            print(f"❌ Engine Cache Error: {e}")

    def recommend_by_job(self, user_job_title):
        if not self.jobs_data: return {"error": "No jobs found"}
        user_doc = nlp(user_job_title)
        
        matches = []
        for job in self.jobs_data:
            score = user_doc.similarity(job['title_doc'])
            matches.append({
                "matched_job": job['title'],
                "industry": job.get('industry'),
                "accuracy": round(score * 100, 2),
                "url": job.get('link')
            })
        return sorted(matches, key=lambda x: x['accuracy'], reverse=True)[0]

    def recommend_by_skills(self, user_skills_raw):
        """Gap analysis using real courses from Supabase."""
        user_doc = nlp(user_skills_raw)
        user_skills_set = {s.strip().lower() for s in user_skills_raw.split(',')}
        
        job_matches = []
        for job in self.jobs_data:
            score = user_doc.similarity(job['skills_doc'])
            job_matches.append({**job, "score": score})
        
        top_jobs = sorted(job_matches, key=lambda x: x['score'], reverse=True)[:3]
        results = []
        for job in top_jobs:
            job_skills = [s.strip() for s in job.get('skills', '').split(',')]
            missing = list({s.lower() for s in job_skills} - user_skills_set)
            
            # Fetch matching courses from Supabase
            courses = []
            if missing:
                res = self.supabase.table('courses').select("*").ilike('title', f'%{missing[0]}%').limit(2).execute()
                courses = [{"title": c['title'], "link": c['link']} for c in res.data]

            results.append({
                "job": job['title'],
                "match_confidence": round(job['score'] * 100, 2),
                "missing_skills": missing[:5],
                "courses": courses
            })
        return results