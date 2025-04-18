// Load all data when the page loads
document.addEventListener('DOMContentLoaded', () => {
    loadExperiences();
    loadSkills();
    loadSections();
    loadKeywords();
    loadComplimentaryKeywords();
});

function randomFontSize() {
    // Tag cloud: font size between 1em and 2.2em
    return (1 + Math.random() * 1.2).toFixed(2) + 'em';
}
function randomColor() {
    // Soft random pastel color
    const hue = Math.floor(Math.random() * 360);
    return `hsl(${hue}, 60%, 70%)`;
}

async function loadExperiences() {
    try {
        const response = await fetch('/api/experiences');
        const data = await response.json();
        // AI summary
        document.getElementById('ai-experiences-summary').innerText = data.summary;
        // Display LinkedIn experiences
        const linkedinContainer = document.getElementById('linkedin-experiences');
        linkedinContainer.innerHTML = data.linkedin.map(exp => `
            <div class="experience-item">
                <div class="experience-title">${exp.title}</div>
                <div class="experience-company">${exp.company}</div>
                <div class="experience-date">${exp.start_date} - ${exp.end_date}</div>
                <div class="experience-description">${exp.description}</div>
            </div>
        `).join('');
        // Display Resume experiences
        const resumeContainer = document.getElementById('resume-experiences');
        resumeContainer.innerHTML = data.resume.map(exp => `
            <div class="experience-item">
                <div class="experience-title">${exp.title}</div>
                <div class="experience-company">${exp.company}</div>
                <div class="experience-date">${exp.start_date} - ${exp.end_date}</div>
                ${exp.location ? `<div class="experience-location">${exp.location}</div>` : ''}
                <div class="experience-description">${exp.description}</div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading experiences:', error);
        document.getElementById('ai-experiences-summary').innerText = 'Error loading summary';
        document.getElementById('linkedin-experiences').innerHTML = 'Error loading experiences';
        document.getElementById('resume-experiences').innerHTML = 'Error loading experiences';
    }
}

async function loadSkills() {
    try {
        const response = await fetch('/api/skills');
        const data = await response.json();
        // Tag cloud rendering
        const skillsContainer = document.getElementById('skills-container');
        skillsContainer.innerHTML = data.skills.map(skill => `
            <span class="skill-tag" style="font-size:${randomFontSize()};color:${randomColor()}">${skill}</span>
        `).join(' ');
    } catch (error) {
        console.error('Error loading skills:', error);
        document.getElementById('skills-container').innerHTML = 'Error loading skills';
    }
}

async function loadSections() {
    try {
        const response = await fetch('/api/sections');
        const sections = await response.json();
        const container = document.getElementById('other-sections');
        container.innerHTML = sections.map(section => `
            <div class="section-item mb-4">
                <h3 class="section-title">${section.section_name}</h3>
                <div class="section-content">${section.content}</div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading sections:', error);
        document.getElementById('other-sections').innerHTML = 'Error loading sections';
    }
}

async function loadKeywords() {
    try {
        const response = await fetch('/api/keywords');
        const data = await response.json();
        const container = document.getElementById('keywords-container');
        if (data.keywords && data.keywords.length > 0) {
            // Split by comma and render as tags
            const tags = data.keywords.split(',').map(k => k.trim()).filter(Boolean);
            container.innerHTML = tags.map(tag => `<span class="skill-tag keyword-tag">${tag}</span>`).join(' ');
        } else {
            container.innerHTML = 'No keywords found.';
        }
    } catch (error) {
        document.getElementById('keywords-container').innerHTML = 'Error loading keywords';
    }
}

async function loadComplimentaryKeywords() {
    try {
        const response = await fetch('/api/complimentary_keywords');
        const data = await response.json();
        const container = document.getElementById('complimentary-keywords-container');
        if (data.complimentary_keywords && data.complimentary_keywords.length > 0) {
            // Split by comma and render as tags
            const tags = data.complimentary_keywords.split(',').map(k => k.trim()).filter(Boolean);
            container.innerHTML = tags.map(tag => `<span class="skill-tag keyword-tag">${tag}</span>`).join(' ');
        } else {
            container.innerHTML = 'No complimentary keywords found.';
        }
    } catch (error) {
        document.getElementById('complimentary-keywords-container').innerHTML = 'Error loading complimentary keywords';
    }
}