"""Document generation using monitored LLM interactions."""
from typing import Optional, Tuple
from pydantic import BaseModel

from jobsearch.core.llm_agent import BaseLLMAgent
from jobsearch.core.schemas import ResumeContent, CoverLetterContent
from jobsearch.core.logging import setup_logging

logger = setup_logging('document_generation_agent')

class JobMatch(BaseModel):
    """Job match information for document generation."""
    title: str
    company: str
    description: str
    requirements: list[str]
    match_score: float
    key_skills: list[str]

class DocumentGenerationAgent(BaseLLMAgent):
    """Agent for generating resumes and cover letters."""
    
    def __init__(self):
        super().__init__(
            feature_name='document_gen',
            output_type=None  # Will vary by method
        )
        
    async def generate_resume(
        self,
        resume_content: ResumeContent,
        job_match: Optional[JobMatch] = None
    ) -> Optional[str]:
        """Generate a polished resume.
        
        Args:
            resume_content: Structured resume content
            job_match: Optional job to tailor resume for
            
        Returns:
            Formatted resume text, or None on error
        """
        prompt = f"""You are an expert resume writer. Take this structured resume content and write it as a polished, professional document.
Follow these rules:
1. Use clear, action-oriented language
2. Quantify achievements where possible
3. Maintain professional tone
4. Keep formatting minimal
5. Focus on relevance to the target role

Content to write:
{resume_content.model_dump_json(indent=2)}

{f'Target Job:\n{job_match.model_dump_json(indent=2)}' if job_match else ''}

Write a complete, properly formatted resume. Use standard section headers and bullet points."""

        return await self.generate_text(prompt=prompt)
        
    async def generate_cover_letter(
        self,
        content: CoverLetterContent,
        job_match: JobMatch
    ) -> Optional[str]:
        """Generate an engaging cover letter.
        
        Args:
            content: Structured cover letter content
            job_match: Job to target the letter for
            
        Returns:
            Formatted cover letter text, or None on error
        """
        prompt = f"""You are an expert cover letter writer. Take this structured content and write it as a compelling letter FROM the job applicant TO the hiring manager.
Follow these rules:
1. Write FROM the applicant perspective
2. Maintain professional but engaging tone
3. Show enthusiasm and personality
4. Connect experience to job requirements
5. Keep paragraphs focused and concise
6. End with a clear call to action
7. Include a proper signature line

Job Details:
{job_match.model_dump_json(indent=2)}

Content to write:
{content.model_dump_json(indent=2)}

Write a complete, properly formatted cover letter, including greeting, body, and signature."""

        return await self.generate_text(prompt=prompt)
        
    async def generate_documents(
        self,
        resume_content: ResumeContent,
        cover_letter_content: CoverLetterContent,
        job_match: JobMatch
    ) -> Tuple[Optional[str], Optional[str]]:
        """Generate both resume and cover letter for a job.
        
        Args:
            resume_content: Resume content
            cover_letter_content: Cover letter content
            job_match: Target job information
            
        Returns:
            Tuple of (resume_text, cover_letter_text), either may be None on error
        """
        resume = await self.generate_resume(resume_content, job_match)
        cover_letter = await self.generate_cover_letter(cover_letter_content, job_match)
        
        return resume, cover_letter
