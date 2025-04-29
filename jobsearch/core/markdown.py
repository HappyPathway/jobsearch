"""Markdown content generation and formatting using core components."""
from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime

from jobsearch.core.logging import setup_logging
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.schemas import (
    DailyStrategy, 
    ActionItem,
    NetworkingTarget,
    ProfileData,
    GithubPagesSummary,
    JobAnalysis,
    CompanyAnalysis
)

# Initialize core components
logger = setup_logging('markdown_generator')
monitoring = setup_monitoring('markdown')

class MarkdownGenerator:
    """Generates and formats markdown content.
    
    This class provides methods to generate and format markdown content for various purposes,
    including job search strategies, profiles, job analyses, and GitHub Pages.
    It uses templates and structured data to create consistent output.
    
    Attributes:
        templates_loaded (dict): A cache of loaded templates.
        template_dir (Path, optional): Directory where templates are stored.
    """
    
    def format_strategy(self, strategy: DailyStrategy) -> str:
        """Format a job search strategy as markdown.
        
        Converts a DailyStrategy object into a formatted markdown document with sections
        for daily focus, target companies, networking targets, and action items.
        
        Args:
            strategy (DailyStrategy): The strategy object containing all components
                of a daily job search strategy.
                
        Returns:
            str: The formatted markdown content.
            
        Raises:
            Exception: If there's an error during formatting.
        """
        try:
            monitoring.increment('strategy_format')
            
            md = [
                f"# Job Search Strategy - {datetime.now().strftime('%Y-%m-%d')}\n",
                "## Today's Focus\n",
                f"{strategy.daily_focus.description}\n",
                "### Key Metrics\n"
            ]
            
            for metric in strategy.daily_focus.metrics:
                md.append(f"- {metric}\n")
                
            md.extend([
                "\n## Target Companies\n",
                *[f"- {company}\n" for company in strategy.target_companies],
                "\n## Networking Targets\n"
            ])
            
            for target in strategy.networking_targets:
                md.extend([
                    f"### {target.name} - {target.title}\n",
                    f"Company: {target.company}\n",
                    f"Source: {target.source}\n",
                    f"Notes: {target.notes}\n\n"
                ])
                
            md.extend([
                "## Action Items\n",
                "| Priority | Task | Deadline | Metrics |\n",
                "|----------|------|----------|----------|\n"
            ])
            
            for item in strategy.action_items:
                metrics = ", ".join(item.metrics)
                md.append(f"| {item.priority} | {item.description} | {item.deadline} | {metrics} |\n")
                
            monitoring.track_success('strategy_format')
            return "".join(md)
            
        except Exception as e:
            monitoring.track_error('strategy_format', str(e))
            logger.error(f"Error formatting strategy: {str(e)}")
            return ""
            
    def format_profile(self, profile: ProfileData) -> str:
        """Format profile data as markdown."""
        try:
            monitoring.increment('profile_format')
            
            md = [
                "# Professional Profile\n\n",
                "## Skills\n",
                ", ".join(profile.skills),
                "\n\n## Target Roles\n",
                *[f"- {role}\n" for role in profile.target_roles],
                "\n## Experience\n"
            ]
            
            for exp in profile.experiences:
                md.extend([
                    f"### {exp['title']} at {exp['company']}\n",
                    f"{exp['description']}\n",
                    "**Skills:** " + ", ".join(exp['skills']) + "\n\n"
                ])
                
            monitoring.track_success('profile_format')
            return "".join(md)
            
        except Exception as e:
            monitoring.track_error('profile_format', str(e))
            logger.error(f"Error formatting profile: {str(e)}")
            return ""
            
    def format_job_analysis(self, analysis: JobAnalysis) -> str:
        """Format job analysis as markdown."""
        try:
            monitoring.increment('analysis_format')
            
            md = [
                f"# Job Analysis\n\n",
                f"Match Score: {analysis.match_score}%\n\n",
                "## Key Requirements\n",
                *[f"- {req}\n" for req in analysis.key_requirements],
                "\n## Culture Indicators\n",
                *[f"- {ind}\n" for ind in analysis.culture_indicators],
                f"\n## Career Growth: {analysis.career_growth_potential}\n",
                f"Experience Required: {analysis.total_years_experience} years\n",
                f"Location Type: {analysis.location_type}\n",
                f"Company Size: {analysis.company_size}\n",
                f"Company Stability: {analysis.company_stability}\n\n"
            ]
            
            if analysis.candidate_gaps:
                md.extend([
                    "## Areas for Development\n",
                    *[f"- {gap}\n" for gap in analysis.candidate_gaps]
                ])
                
            monitoring.track_success('analysis_format')
            return "".join(md)
            
        except Exception as e:
            monitoring.track_error('analysis_format', str(e))
            logger.error(f"Error formatting job analysis: {str(e)}")
            return ""
            
    def format_github_pages(self, summary: GithubPagesSummary) -> str:
        """Format content for GitHub Pages."""
        try:
            monitoring.increment('pages_format')
            
            md = [
                f"# {summary.headline}\n\n",
                *[f"{para}\n\n" for para in summary.summary],
                "## Key Points\n",
                *[f"- {point}\n" for point in summary.key_points],
                "\n## Target Roles\n",
                *[f"- {role}\n" for role in summary.target_roles]
            ]
            
            monitoring.track_success('pages_format')
            return "".join(md)
            
        except Exception as e:
            monitoring.track_error('pages_format', str(e))
            logger.error(f"Error formatting GitHub Pages: {str(e)}")
            return ""
