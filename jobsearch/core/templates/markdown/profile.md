# Professional Profile Summary
*Generated on {{ date }}*

## Career Summary

{{ career_summary }}

## Work Experience

{% for exp in experiences %}
### {{ exp.title }} at {{ exp.company }}
*{{ exp.start_date }} - {{ exp.end_date }}*

{{ exp.description }}

{% if exp.skills %}**Key Skills**: {{ exp.skills | join(', ') }}{% endif %}

{% endfor %}

## Professional Skills

{% for skill in skills %}
- **{{ skill.name }}**: {{ skill.proficiency | title }}{% if skill.years %} ({{ skill.years }} years){% endif %}
{% endfor %}

## Target Roles

{% for role in target_roles %}
### {{ role.title }}
**Match Score**: {{ role.match_score }}%

{% if role.requirements %}
**Key Requirements**:
{% for req in role.requirements %}
- {{ req }}
{% endfor %}
{% endif %}

{% endfor %}
