# {{ title }}

{% if subtitle %}
## {{ subtitle }}
{% endif %}

*Published on {{ date }}{% if preview %} - PREVIEW DRAFT{% endif %}*

{{ content }}

{% if tags %}
**Tags**: {{ tags | map('regex_replace', '^', '#') | join(', ') }}
{% endif %}

{% if author_bio %}
---

*About the author:* {{ author_bio }}
{% endif %}
