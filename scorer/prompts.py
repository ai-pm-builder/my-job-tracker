"""
Prompt templates for the Job Scorer Module.
"""

from langchain_core.prompts import PromptTemplate

# ──────────────────────────── Profile Extraction ────────────────────────────

PROFILE_EXTRACTION_TEMPLATE = """
You are an expert technical recruiter. Your task is to extract a comprehensive professional profile from the provided resume text.
Output a valid JSON matching the schema precisely.

Instructions:
1. Extract the candidate's core technical and soft skills.
2. Summarize their experience, emphasizing measurable achievements (metrics, scale).
3. Identify all proof points (concrete examples of impact, e.g., "Reduced latency by 40%").
4. Identify which of these "AI/Tech Archetypes" best fit this candidate (select up to 3):
   - AI Platform / LLMOps Engineer
   - Agentic Workflows / Automation Engineer
   - Technical AI Product Manager
   - AI Solutions Architect
   - AI Forward Deployed Engineer
   - AI Transformation Lead
   - Generalist Software Engineer
   - Traditional Product Manager

Resume Text:
```
{resume_text}
```
"""

PROFILE_PROMPT = PromptTemplate(
    template=PROFILE_EXTRACTION_TEMPLATE,
    input_variables=["resume_text"]
)


# ──────────────────────────── Job Evaluation (Career-Ops style) ────────────────────────────

JOB_EVALUATION_TEMPLATE = """
You are an expert AI Career Coach evaluating a job opportunity for the candidate.
Read the candidate's profile and the Job Description (JD). Evaluate the match strictly on a 1.0 to 5.0 scale across 5 dimensions, and produce 7 structured text blocks.

Candidate Profile:
```json
{candidate_profile}
```

Job Description:
```
{job_description}
```

Follow these instructions to produce the evaluation fields:

### Scale Context (for scores 1.0 - 5.0)
- 5.0: Exceptional, top 5% match.
- 4.0: Strong match, core requirements met.
- 3.0: Acceptable, some gaps but manageable.
- 2.0: Poor match, significant blockers.
- 1.0: Irrelevant role.

### Fields to generate:
1. **archetype**: Classify the role into one of the 6 AI/Tech archetypes (or hybrid).
2. **domain**: Domain of the company/role (e.g., "SaaS", "Enterprise AI", "B2B").
3. **seniority**: Level inferred (e.g., "Senior", "Lead", "Staff", "Manager").
4. **remote_policy**: "Full Remote", "Hybrid", or "Onsite".
5. **role_tldr**: 1-sentence summary of what the person will actually do.
6. **cv_match**: Score (1.0-5.0) for skill/experience match.
7. **north_star_alignment**: Score (1.0-5.0) for how well this fits the candidate's profile archetypes.
8. **compensation**: Score (1.0-5.0). If you have no data, guess 3.0 based on general market context.
9. **cultural_signals**: Score (1.0-5.0) for company culture/growth trajectory (assume 3.5 if neutral).
10. **red_flags**: Score (1.0-5.0). Inverted: 5.0 means NO red flags, 1.0 means critical red flags.
11. **overall_score**: Calculate the weighted average based on these weights:
    [cv_match: 0.35, north_star_alignment: 0.25, compensation: 0.15, cultural_signals: 0.15, red_flags: 0.10]
12. **matching_skills**: List of exact candidate skills found in JD.
13. **skill_gaps**: List of JD requirements the candidate lacks.
14. **gap_analysis**: How can the candidate mitigate these gaps? Is it a blocker or nice-to-have?
15. **personalization_plan**: List top 5 resume adaptations needed for this specific role.
16. **interview_prep**: Draft 2-3 STAR+R (Situation, Task, Action, Result + Reflection) stories the candidate should use, mapped perfectly to the JD requirements. Keep them concise but impactful.
17. **legitimacy**: "High Confidence", "Proceed with Caution", or "Suspicious". Check for ghost job signals (generic JD, contradictions, hyper-inflated requirements).
18. **legitimacy_signals**: Brief explanation of the legitimacy rating.
19. **reasoning**: A detailed evaluation narrative connecting everything together.

Return ONLY the JSON matching the required schema. Ensure the JSON is well-formed.
"""

JOB_EVAL_PROMPT = PromptTemplate(
    template=JOB_EVALUATION_TEMPLATE,
    input_variables=["candidate_profile", "job_description"]
)
