"""Job analysis using monitored LLM interactions."""
from typing import Optional, List
from pydantic import BaseModel

from jobsearch.core.llm_agent import BaseLLMAgent
from jobsearch.core.schemas import JobAnalysis, CompanyAnalysis
from jobsearch.core.logging import setup_logging

logger = setup_logging('job_analysis_agent')

class JobInfo(BaseModel):
    """Job posting information."""
    title: str
    company: str
    description: str
    location: Optional[str] = None
    salary_range: Optional[str] = None
    posting_date: Optional[str] = None

class JobAnalysisAgent(BaseLLMAgent):
    """Agent for analyzing job postings."""
    
    def __init__(self):
        super().__init__(
            feature_name='job_analysis',
            output_type=JobAnalysis
        )
        
    async def analyze_job(
        self,
        job_info: JobInfo,
        company_data: Optional[CompanyAnalysis] = None
    ) -> Optional[JobAnalysis]:
        """Analyze a job posting with comprehensive monitoring.
        
        Args:
            job_info: Job posting information
            company_data: Optional additional company information
            
        Returns:
            Structured job analysis, or None on error
        """
        # Example data for consistent outputs
        example_data = JobAnalysis(
            match_score=85.0,
            key_requirements=[
                "5+ years cloud infrastructure experience",
                "Expert level Terraform knowledge",
                "CI/CD pipeline development"
            ],
            culture_indicators=[
                "Strong emphasis on collaboration",
                "Focus on continuous learning",
                "Remote-friendly environment"
            ],
            career_growth_potential="high",
            total_years_experience=5,
            candidate_gaps=[
                "Limited experience with specific cloud provider",
                "No direct experience with required industry"
            ],
            location_type="hybrid",
            company_size="midsize",
            company_stability="high",
            development_opportunities=[
                "Leadership track available",
                "Training budget provided",
                "Mentorship program"
            ],
            reasoning="Strong match based on technical skills and culture fit..."
        ).model_dump()
        
        prompt = f"""Analyze this job posting. Consider both explicit requirements and implicit indicators.
Focus on technical requirements, company culture, growth potential, and potential skill gaps.

Job Title: {job_info.title}
Company: {job_info.company}
Description: {job_info.description}

{f'Additional Company Information:\n{company_data.model_dump_json(indent=2)}' if company_data else ''}

Analyze the posting and return a structured analysis including:
1. Overall match score (0-100)
2. Key technical and non-technical requirements
3. Culture indicators from the job description
4. Career growth potential (high/medium/low)
5. Total years experience required
6. Any potential gaps in candidate qualifications
7. Location type (remote/hybrid/onsite)
8. Company size indication (startup/midsize/large/enterprise)
9. Company stability assessment (high/medium/low)
10. Development and growth opportunities"""

        result = await self.generate(
            prompt=prompt,
            expected_type=JobAnalysis,
            example_data=example_data
        )
        
        if result:
            logger.info(f"Successfully analyzed job: {job_info.title}")
        else:
            logger.error(f"Failed to analyze job: {job_info.title}")
            
        return result

    async def analyze_jobs_batch(
        self,
        jobs: List[JobInfo]
    ) -> List[Optional[JobAnalysis]]:
        """Analyze multiple jobs in batch.
        
        Args:
            jobs: List of jobs to analyze
            
        Returns:
            List of job analyses, with None for failed analyses
        """
        results = []
        for job in jobs:
            analysis = await self.analyze_job(job)
            results.append(analysis)
            
        success_count = len([r for r in results if r is not None])
        logger.info(f"Batch analysis complete. {success_count}/{len(jobs)} successful")
        
        return results
