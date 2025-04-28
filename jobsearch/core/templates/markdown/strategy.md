# Job Search Strategy - {{ date }}

{{ content }}

## Today's Top Job Matches

{% for job in jobs %}
### {{ loop.index }}. {{ job.title }} at {{ job.company }}

**Priority**: {{ job.application_priority | upper }} | **Match Score**: {{ job.match_score }}%
**Key Requirements**: {{ job.key_requirements | join(', ') }}
**Career Growth**: {{ job.career_growth_potential }}

{% if job.url != '#' %}[View Job]({{ job.url }}){% endif %}

{% if company_insights[job.company] %}
{% set insight = company_insights[job.company] %}
{% if insight.glassdoor %}
#### Company Culture Insights (Glassdoor)
**Work-Life Balance**: {{ insight.glassdoor.work_life_balance }}
**Management Quality**: {{ insight.glassdoor.management_quality }}
{% if insight.glassdoor.red_flags %}**Potential Concerns**: {{ insight.glassdoor.red_flags | join(', ') }}{% endif %}
**Overall Assessment**: {{ insight.glassdoor.recommendation }}
{% endif %}

{% if insight.techcrunch %}
#### Market Insights (TechCrunch)
**Market Position**: {{ insight.techcrunch.market_position }}
**Growth Trajectory**: {{ insight.techcrunch.growth_trajectory }}
{% if insight.techcrunch.key_developments %}**Recent Developments**: {{ insight.techcrunch.key_developments | join(', ') }}{% endif %}
**News Sentiment**: {{ insight.techcrunch.news_sentiment }}
{% if insight.techcrunch.recommendation %}**Overall Assessment**: {{ insight.techcrunch.recommendation }}{% endif %}
{% endif %}
{% endif %}

{% endfor %}

{% if weekly_focus %}
## Weekly Focus

{{ weekly_focus }}
{% endif %}
