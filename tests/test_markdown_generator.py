"""Test cases for the MarkdownGenerator class."""
from datetime import datetime
from pathlib import Path
import pytest
from jobsearch.core.markdown import MarkdownGenerator

@pytest.fixture
def markdown_generator():
    return MarkdownGenerator()

def test_generate_strategy(markdown_generator):
    """Test strategy document generation."""
    date = datetime(2024, 4, 28)
    content = "Today's job search strategy focuses on tech roles."
    jobs = [
        {
            'title': 'Senior Developer',
            'company': 'Tech Corp',
            'application_priority': 'high',
            'match_score': 85,
            'key_requirements': ['Python', 'AWS'],
            'career_growth_potential': 'Strong leadership track',
            'url': 'http://example.com/job1'
        }
    ]
    company_insights = {
        'Tech Corp': {
            'glassdoor': {
                'work_life_balance': 'Good',
                'management_quality': 'Excellent',
                'recommendation': 'Highly recommended'
            }
        }
    }
    weekly_focus = "Focus on cloud certifications this week."
    
    result = markdown_generator.generate_strategy(
        content=content,
        date=date,
        jobs=jobs,
        company_insights=company_insights,
        weekly_focus=weekly_focus
    )
    
    assert result is not None
    assert 'Job Search Strategy - 2024-04-28' in result
    assert "Today's job search strategy focuses on tech roles" in result
    assert 'Senior Developer at Tech Corp' in result
    assert 'Python, AWS' in result
    assert 'Focus on cloud certifications' in result

def test_generate_article(markdown_generator):
    """Test article generation."""
    result = markdown_generator.generate_article(
        title="Understanding Cloud Architecture",
        subtitle="A Deep Dive into Modern Infrastructure",
        content="Cloud architecture has become essential...",
        tags=['cloud', 'architecture', 'tech'],
        author_bio="Experienced cloud architect",
        preview=True
    )
    
    assert result is not None
    assert 'Understanding Cloud Architecture' in result
    assert 'A Deep Dive into Modern Infrastructure' in result
    assert 'PREVIEW DRAFT' in result
    assert '#cloud' in result
    assert 'Experienced cloud architect' in result

def test_generate_readme(markdown_generator):
    """Test README generation."""
    job_info = {
        'title': 'Senior Developer',
        'company': 'Tech Corp',
        'url': 'http://example.com/job',
        'description': 'Exciting role...',
        'match_score': 85,
        'application_priority': 'high',
        'key_requirements': ['Python', 'AWS'],
        'culture_indicators': ['Remote-friendly', 'Innovation'],
        'career_growth_potential': 'Strong'
    }
    
    result = markdown_generator.generate_readme(job_info)
    
    assert result is not None
    assert 'Job Application: Senior Developer at Tech Corp' in result
    assert 'Remote-friendly' in result
    assert 'Python, AWS' in result
    assert job_info['url'] in result

def test_generate_profile_summary(markdown_generator):
    """Test profile summary generation."""
    experiences = [
        {
            'title': 'Senior Developer',
            'company': 'Tech Corp',
            'start_date': '2020-01',
            'end_date': 'Present',
            'description': 'Led development team...',
            'skills': ['Python', 'AWS']
        }
    ]
    skills = [
        {
            'name': 'Python',
            'proficiency': 'expert',
            'years': 5
        }
    ]
    career_summary = "Experienced software engineer..."
    target_roles = [
        {
            'title': 'Lead Developer',
            'match_score': 90,
            'requirements': ['Team leadership', 'Architecture']
        }
    ]
    
    result = markdown_generator.generate_profile_summary(
        experiences=experiences,
        skills=skills,
        career_summary=career_summary,
        target_roles=target_roles
    )
    
    assert result is not None
    assert 'Professional Profile Summary' in result
    assert 'Experienced software engineer' in result
    assert 'Senior Developer at Tech Corp' in result
    assert 'Python: Expert (5 years)' in result
    assert 'Lead Developer' in result
    assert 'Team leadership' in result

def test_template_not_found(markdown_generator):
    """Test handling of missing templates."""
    result = markdown_generator.generate_markdown('nonexistent.md', {})
    assert result is None

def test_local_template_loading(tmp_path):
    """Test loading templates from a local directory."""
    template_dir = tmp_path / 'templates'
    template_dir.mkdir()
    
    template_content = "# {{ title }}\n\n{{ content }}"
    (template_dir / 'test.md').write_text(template_content)
    
    generator = MarkdownGenerator(template_dir=template_dir)
    result = generator.generate_markdown('test.md', {
        'title': 'Test Doc',
        'content': 'Test content'
    })
    
    assert result is not None
    assert '# Test Doc\n\nTest content' == result

def test_template_caching(tmp_path):
    """Test that templates are properly cached."""
    template_dir = tmp_path / 'templates'
    template_dir.mkdir()
    
    template_content = "# {{ title }}"
    template_path = template_dir / 'test.md'
    template_path.write_text(template_content)
    
    generator = MarkdownGenerator(template_dir=template_dir)
    
    # First load should read from file
    content1 = generator.get_template_content('test.md')
    assert content1 == template_content
    
    # Change file content
    template_path.write_text("Different content")
    
    # Second load should use cache
    content2 = generator.get_template_content('test.md')
    assert content2 == template_content  # Should still have old content
    
    # Verify it's the same object in cache
    assert id(content1) == id(content2)
