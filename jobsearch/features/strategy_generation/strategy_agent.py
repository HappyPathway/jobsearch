"""Strategy generation using monitored LLM interactions."""
from typing import Optional, List, Dict
from datetime import datetime

from jobsearch.core.llm_agent import BaseLLMAgent
from jobsearch.core.schemas import (
    DailyStrategy, FocusArea, NetworkingTarget,
    ActionItem
)
from jobsearch.core.logging import setup_logging

logger = setup_logging('strategy_agent')

class StrategyGenerationAgent(BaseLLMAgent):
    """Agent for generating job search strategies."""
    
    def __init__(self):
        super().__init__(
            feature_name='strategy_gen',
            output_type=DailyStrategy
        )
        
    async def generate_daily_strategy(
        self,
        profile_data: Dict,
        recent_applications: List[Dict],
        priority_jobs: List[Dict]
    ) -> Optional[DailyStrategy]:
        """Generate a daily job search strategy.
        
        Args:
            profile_data: Candidate profile information
            recent_applications: Recent job applications
            priority_jobs: Priority job opportunities
            
        Returns:
            Structured daily strategy, or None on error
        """
        example_data = DailyStrategy(
            daily_focus=FocusArea(
                primary_goal="Apply to 3 high-priority cloud engineering roles",
                secondary_goals=[
                    "Complete AWS certification practice exam",
                    "Follow up on pending applications"
                ]
            ),
            target_companies=[
                "Example Tech Co",
                "Innovation Labs",
                "Cloud Services Inc"
            ],
            networking_targets=[
                NetworkingTarget(
                    role="Cloud Engineer",
                    company="Tech Corp",
                    connection_strategy="Shared background in cloud infrastructure"
                )
            ],
            action_items=[
                ActionItem(
                    description="Apply to Senior Cloud Architect role at TechCorp",
                    priority="high",
                    deadline="EOD",
                    metrics=[
                        "Application submitted",
                        "Resume customized",
                        "Cover letter tailored"
                    ]
                )
            ]
        ).model_dump()
        
        prompt = f"""Generate a daily job search strategy based on the candidate's profile and current opportunities.

Profile Data:
{profile_data}

Recent Applications (Last 7 Days):
{recent_applications}

Priority Jobs:
{priority_jobs}

Create a detailed strategy that includes:
1. Primary and secondary goals for the day
2. Specific companies to target
3. Networking opportunities
4. Prioritized action items with deadlines
5. Success metrics for each action

Focus on high-impact activities and clear, measurable outcomes."""

        return await self.generate(
            prompt=prompt,
            expected_type=DailyStrategy,
            example_data=example_data
        )
