"""Job search feature implementation using base feature class."""
from typing import List, Optional
from pydantic import BaseModel

from jobsearch.core.feature import BaseFeature, FeatureContext
from jobsearch.core.models import JobCache, Experience, Skill, TargetRole

class JobSearchContext(FeatureContext):
    """Context for job search operations."""
    search_queries: List[str] = []
    max_results: int = 100
    company_size: Optional[str] = None

class JobListing(BaseModel):
    """Schema for job search results."""
    url: str
    title: str
    company: str
    location: str
    description: str
    post_date: Optional[str] = None
    source: str
    search_query: str

class JobSearchFeature(BaseFeature):
    """Job search and analysis feature."""
    
    def __init__(self):
        super().__init__(
            name="job_search",
            system_prompt="""You are a specialized job search assistant.
            Your role is to analyze job postings and candidate profiles to find optimal matches.
            Use the provided context and tools to search, analyze, and score job opportunities.""",
            context_type=JobSearchContext,
            output_type=List[JobListing]
        )
        
    @property
    def system_context(self) -> dict:
        """Get the current system context for AI operations."""
        with self.context.db() as session:
            experiences = session.query(Experience).all()
            skills = session.query(Skill).all()
            target_roles = session.query(TargetRole).all()
            
            return {
                'experiences': [e.__dict__ for e in experiences],
                'skills': [s.__dict__ for s in skills],
                'target_roles': [r.__dict__ for r in target_roles]
            }
    
    async def generate_search_queries(self) -> List[str]:
        """Generate optimized job search queries."""
        try:
            self.monitoring.increment('generate_queries')
            
            result = await self.agent.run(
                "Generate optimal job search queries based on the profile",
                context=self.system_context
            )
            
            if isinstance(result, list):
                self.context.search_queries = result
                self.monitoring.track_success('generate_queries')
                return result
                
            raise ValueError("Invalid query generation result")
            
        except Exception as e:
            self.monitoring.track_error('generate_queries', str(e))
            self.logger.error(f"Error generating queries: {str(e)}")
            return []
            
    async def search_jobs(self, queries: List[str]) -> List[JobListing]:
        """Search for jobs using the provided queries."""
        try:
            self.monitoring.increment('search_jobs')
            
            result = await self.agent.run(
                "Search for jobs using these queries",
                context={
                    **self.system_context,
                    'queries': queries,
                    'max_results': self.context.max_results
                }
            )
            
            if isinstance(result, list) and all(isinstance(j, JobListing) for j in result):
                self.monitoring.track_success('search_jobs')
                return result
                
            raise ValueError("Invalid search results")
            
        except Exception as e:
            self.monitoring.track_error('search_jobs', str(e))
            self.logger.error(f"Error searching jobs: {str(e)}")
            return []
            
    async def analyze_jobs(self, jobs: List[JobListing]) -> List[dict]:
        """Analyze job postings for fit and requirements."""
        try:
            self.monitoring.increment('analyze_jobs')
            
            result = await self.agent.run(
                "Analyze these jobs for candidate fit",
                context={
                    **self.system_context,
                    'jobs': [j.dict() for j in jobs]
                }
            )
            
            if isinstance(result, list):
                self.monitoring.track_success('analyze_jobs')
                return result
                
            raise ValueError("Invalid analysis results")
            
        except Exception as e:
            self.monitoring.track_error('analyze_jobs', str(e))
            self.logger.error(f"Error analyzing jobs: {str(e)}")
            return []
            
    async def run(self, company_size: Optional[str] = None) -> List[JobListing]:
        """Run the complete job search process."""
        try:
            self.monitoring.increment('run')
            self.context.company_size = company_size
            
            # Generate search queries
            queries = await self.generate_search_queries()
            if not queries:
                raise ValueError("No search queries generated")
                
            # Search for jobs
            jobs = await self.search_jobs(queries)
            if not jobs:
                self.logger.warning("No jobs found")
                return []
                
            # Analyze and filter jobs
            analyzed = await self.analyze_jobs(jobs)
            
            # Update database
            await self.update_job_cache(jobs, analyzed)
            
            self.monitoring.track_success('run')
            return jobs
            
        except Exception as e:
            self.monitoring.track_error('run', str(e))
            self.logger.error(f"Error in job search: {str(e)}")
            return []
            
    async def update_job_cache(self, jobs: List[JobListing], analyses: List[dict]):
        """Update the job cache with results."""
        try:
            self.monitoring.increment('update_cache')
            
            with self.context.db() as session:
                for job, analysis in zip(jobs, analyses):
                    # Update or create job cache entry
                    cached = session.query(JobCache).filter_by(url=job.url).first()
                    if cached:
                        # Update existing job
                        for key, value in analysis.items():
                            setattr(cached, key, value)
                    else:
                        # Create new job
                        new_job = JobCache(
                            url=job.url,
                            title=job.title,
                            company=job.company,
                            location=job.location,
                            description=job.description,
                            post_date=job.post_date,
                            **analysis
                        )
                        session.add(new_job)
                        
                session.commit()
                
            self.monitoring.track_success('update_cache')
            
        except Exception as e:
            self.monitoring.track_error('update_cache', str(e))
            self.logger.error(f"Error updating cache: {str(e)}")
            
# Example usage:
async def main():
    async with JobSearchFeature() as feature:
        jobs = await feature.run(company_size="startup")
        print(f"Found {len(jobs)} matching jobs")
