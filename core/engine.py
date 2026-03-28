from core.shared_utils import nlp

class CareerEngine:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.jobs_data = []
        self.courses_data = []
        self.refresh_cache()

    def refresh_cache(self):
        """Syncs jobs AND courses from Supabase and pre-computes vectors."""
        try:
            print("🔍 Engine: Syncing jobs from Supabase...")
            job_res = self.supabase.table('jobs').select("*").execute()
            raw_jobs = job_res.data or []

            processed = []
            for job in raw_jobs:
                title_text  = job.get('title', '')
                skills_text = job.get('skills', '')
                job['title_doc']  = nlp(title_text)  if title_text  else nlp('')
                job['skills_doc'] = nlp(skills_text) if skills_text else nlp('')
                processed.append(job)

            self.jobs_data = processed
            print(f"✅ Engine: Cached {len(self.jobs_data)} jobs.")

            # ✅ NEW: Cache courses too for faster lookup
            print("🔍 Engine: Syncing courses from Supabase...")
            course_res = self.supabase.table('courses').select("*").execute()
            self.courses_data = course_res.data or []
            print(f"✅ Engine: Cached {len(self.courses_data)} courses.")

        except Exception as e:
            print(f"❌ Engine Cache Error: {e}")

    def recommend_by_job(self, user_job_title):
        """Find top matching jobs for a given job title."""
        if not self.jobs_data:
            return {"error": "No jobs found in cache"}

        user_doc = nlp(user_job_title)

        matches = []
        for job in self.jobs_data:
            try:
                score = user_doc.similarity(job['title_doc'])
            except Exception:
                score = 0.0

            matches.append({
                "matched_job": job.get('title', ''),
                "industry":    job.get('industry', ''),
                "accuracy":    round(score * 100, 2),
                "url":         job.get('link', '#'),
                "skills":      job.get('skills', ''),
            })

        # Return top result (single job match, preserved for API contract)
        return sorted(matches, key=lambda x: x['accuracy'], reverse=True)[0]

    def recommend_by_skills(self, user_skills_raw):
        """
        Full gap analysis:
        - Returns top 8 job matches (was 3)
        - Finds missing skills per job
        - Recommends up to 3 courses per missing skill (was 1 skill, 2 courses)
        - Falls back to keyword search across title+description if DB courses are empty
        """
        if not self.jobs_data:
            return []

        user_doc        = nlp(user_skills_raw)
        user_skills_set = {s.strip().lower() for s in user_skills_raw.split(',') if s.strip()}

        # ── Score every job ──────────────────────────────────────────────────
        job_matches = []
        for job in self.jobs_data:
            try:
                # Blend title similarity + skills similarity (60/40 weight)
                title_score  = user_doc.similarity(job['title_doc'])
                skills_score = user_doc.similarity(job['skills_doc'])
                score = (title_score * 0.4) + (skills_score * 0.6)
            except Exception:
                score = 0.0
            job_matches.append({**job, "score": score})

        # ✅ Return top 8 instead of 3
        top_jobs = sorted(job_matches, key=lambda x: x['score'], reverse=True)[:8]

        results = []
        for job in top_jobs:
            raw_skills  = job.get('skills', '')
            job_skills  = [s.strip() for s in raw_skills.split(',') if s.strip()]
            missing     = [s for s in job_skills if s.lower() not in user_skills_set]

            # ── Course recommendations ───────────────────────────────────────
            # ✅ Search top 3 missing skills (was 1), 3 courses each (was 2)
            courses = []
            seen_course_ids = set()

            for skill in missing[:3]:
                skill_lower = skill.lower()

                # 1. Try cached courses first (fast)
                local_hits = [
                    c for c in self.courses_data
                    if skill_lower in (c.get('title', '') + ' ' + c.get('skills', '') + ' ' + c.get('field', '')).lower()
                ][:3]

                for c in local_hits:
                    cid = c.get('id') or c.get('title')
                    if cid not in seen_course_ids:
                        seen_course_ids.add(cid)
                        courses.append({
                            "title":    c.get('title', ''),
                            "link":     c.get('link') or c.get('url') or '#',
                            "provider": c.get('provider', ''),
                            "skill":    skill,
                        })

                # 2. Fallback: DB query if local cache gave nothing
                if not local_hits:
                    try:
                        # Try exact skill match first
                        res = self.supabase.table('courses').select("*") \
                            .ilike('title', f'%{skill}%').limit(3).execute()
                        db_courses = res.data or []

                        # Broaden to field if still empty
                        if not db_courses:
                            res2 = self.supabase.table('courses').select("*") \
                                .ilike('field', f'%{skill}%').limit(3).execute()
                            db_courses = res2.data or []

                        for c in db_courses:
                            cid = c.get('id') or c.get('title')
                            if cid not in seen_course_ids:
                                seen_course_ids.add(cid)
                                courses.append({
                                    "title":    c.get('title', ''),
                                    "link":     c.get('link') or c.get('url') or '#',
                                    "provider": c.get('provider', ''),
                                    "skill":    skill,
                                })
                    except Exception as e:
                        print(f"⚠️ Course fetch error for '{skill}': {e}")

            results.append({
                "job":              job.get('title', ''),
                "industry":         job.get('industry', ''),
                "url":              job.get('link', '#'),
                "match_confidence": round(job['score'] * 100, 2),
                "missing_skills":   missing[:6],   # show up to 6 missing skills
                "courses":          courses[:6],   # cap at 6 course suggestions
            })

        return results
