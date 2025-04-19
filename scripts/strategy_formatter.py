import os
import json
from datetime import datetime
from logging_utils import setup_logging

logger = setup_logging('strategy_formatter')

def format_strategy_output_plain(strategy, include_weekly_focus=True):
    """Format strategy output in plain text format for backwards compatibility"""
    output = []
    output.append(f"Job Search Strategy - {datetime.now().strftime('%Y-%m-%d')}")
    
    # Daily Focus
    daily_focus = strategy.get('daily_focus', {})
    output.append(f"\nToday's Focus: {daily_focus.get('title', 'Daily Planning')}")
    output.append(f"Reasoning: {daily_focus.get('reasoning', '')}")
    
    output.append("\nSuccess Metrics:")
    for metric in daily_focus.get('success_metrics', []):
        output.append(f"- {metric}")
    
    # Target Roles
    output.append("\nTarget Roles:")
    for role in strategy.get('target_roles', []):
        output.append(f"\n{role['title']}")
        output.append(f"Reasoning: {role.get('reasoning', '')}")
        output.append("\nKey Skills:")
        for skill in role.get('key_skills_to_emphasize', []):
            output.append(f"- {skill}")
        output.append("\nTarget Companies:")
        for company in role.get('suggested_companies', []):
            output.append(f"- {company}")
        if role.get('current_opportunities'):
            output.append("\nCurrent Opportunities:")
            for opp in role['current_opportunities']:
                output.append(f"- {opp['title']} at {opp['company']}")
                output.append(f"  URL: {opp.get('url', 'No URL')}")
    
    # Networking Strategy
    network = strategy.get('networking_strategy', {})
    output.append("\nNetworking Strategy:")
    output.append(f"Daily Connections Target: {network.get('daily_connections', 3)}")
    output.append("\nTarget Individuals:")
    for target in network.get('target_individuals', []):
        output.append(f"- {target}")
    
    # Skill Development
    output.append("\nSkill Development:")
    for skill in strategy.get('skill_development', []):
        output.append(f"\n- {skill['skill']}")
        output.append(f"  Goal: {skill['action']}")
        output.append(f"  Timeline: {skill['timeline']}")
        if skill.get('status'):
            output.append(f"  Status: {skill['status']}")
    
    # Application Strategy
    app_strategy = strategy.get('application_strategy', {})
    output.append("\nApplication Strategy:")
    output.append(f"Daily Target: {app_strategy.get('daily_target', 1)} application(s)")
    
    output.append("\nQuality Checklist:")
    for item in app_strategy.get('quality_checklist', []):
        output.append(f"- {item}")
    
    return "\n".join(output)

def format_strategy_output_markdown(strategy, weekly_focus=None):
    """Format strategy output in Markdown format with enhanced formatting"""
    current_date = datetime.now().strftime('%B %d, %Y')
    output = []
    
    # Header and Focus
    output.append(f"# Job Search Strategy - {current_date}\n")
    output.append(f"## Today's Focus: {strategy.get('daily_focus', {}).get('title', 'Daily Planning')}")
    output.append(f"*Why*: {strategy.get('daily_focus', {}).get('reasoning', '')}\n")
    
    # Success Metrics
    output.append("### Success Metrics")
    for metric in strategy.get('daily_focus', {}).get('success_metrics', []):
        output.append(f"- [ ] {metric}")
    output.append("")
    
    # Morning Tasks
    output.append("## Morning Tasks\n")
    output.append("### High Priority")
    for task in strategy.get('daily_focus', {}).get('morning', []):
        if task.get('priority') == 'High':
            output.append(f"1. **{task['task']}** ⏱️ {task['time']}min  ")
            output.append(f"   *Why*: {task['reasoning']}")
    
    output.append("\n### Medium Priority")
    for task in strategy.get('daily_focus', {}).get('morning', []):
        if task.get('priority') == 'Medium':
            output.append(f"1. **{task['task']}** ⏱️ {task['time']}min  ")
            output.append(f"   *Why*: {task['reasoning']}")
    output.append("")
    
    # Afternoon Tasks
    output.append("## Afternoon Tasks\n")
    output.append("### High Priority")
    for task in strategy.get('daily_focus', {}).get('afternoon', []):
        if task.get('priority') == 'High':
            output.append(f"1. **{task['task']}** ⏱️ {task['time']}min  ")
            output.append(f"   *Why*: {task['reasoning']}")
    
    output.append("\n### Medium Priority")
    for task in strategy.get('daily_focus', {}).get('afternoon', []):
        if task.get('priority') == 'Medium':
            output.append(f"1. **{task['task']}** ⏱️ {task['time']}min  ")
            output.append(f"   *Why*: {task['reasoning']}")
    output.append("")
    
    # Target Roles & Opportunities
    output.append("## Target Roles & Current Opportunities\n")
    for role in strategy.get('target_roles', []):
        output.append(f"### {role['title']}")
        output.append(f"*Why*: {role['reasoning']}\n")
        
        output.append("#### Key Skills to Emphasize")
        for skill in role.get('key_skills_to_emphasize', []):
            output.append(f"- {skill}")
        output.append("")
        
        output.append("#### Target Companies")
        for company in role.get('suggested_companies', []):
            output.append(f"- {company}")
        output.append("")
        
        output.append("#### Active Opportunities")
        for idx, job in enumerate(role.get('current_opportunities', []), 1):
            output.append(f"{idx}. [{job['title']}]({job['url']})")
            output.append(f"   - Company: {job['company']}")
            output.append(f"   - Status: To Apply")
            if job.get('notes'):
                output.append(f"   - Notes: {job['notes']}")
            output.append("")
    
    # Networking Strategy
    output.append("## Networking Strategy")
    network = strategy.get('networking_strategy', {})
    output.append(f"**Daily Connection Target**: {network.get('daily_connections', 3)}\n")
    
    output.append("### Platforms")
    for platform in network.get('platforms', []):
        output.append(f"- {platform}")
    output.append("")
    
    output.append("### Outreach Template")
    output.append("```")
    output.append(network.get('message_template', ''))
    output.append("```\n")
    
    output.append("### Target Connections")
    for target in network.get('target_individuals', []):
        output.append(f"- {target}")
    output.append("")
    
    # Skill Development
    output.append("## Skill Development Plan\n")
    for skill in strategy.get('skill_development', []):
        output.append(f"### Current Focus: {skill['skill']}")
        output.append(f"- **Goal**: {skill['action']}")
        output.append(f"- **Timeline**: {skill['timeline']}")
        if skill.get('status'):
            output.append(f"- **Status**: {skill['status']}")
        output.append("")
    
    # Application Strategy
    app_strategy = strategy.get('application_strategy', {})
    output.append("## Application Strategy")
    output.append(f"**Daily Target**: {app_strategy.get('daily_target', 1)} high-quality application\n")
    
    output.append("### Quality Checklist")
    for item in app_strategy.get('quality_checklist', []):
        output.append(f"- [ ] {item}")
    output.append("")
    
    output.append("### Customization Points")
    for point in app_strategy.get('customization_points', []):
        output.append(f"- {point}")
    output.append("")
    
    output.append("### Tracking")
    output.append(app_strategy.get('tracking_method', ''))
    
    return "\n".join(output)

# For backwards compatibility
format_strategy_output = format_strategy_output_markdown