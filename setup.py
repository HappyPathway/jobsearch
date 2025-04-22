from setuptools import setup, find_packages

setup(
    name="jobsearch",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "google-cloud-storage",
        "google-generativeai",
        "sqlalchemy",
        "pdfplumber",
        "python-dotenv",
        "python-slugify",
        "google-cloud-secret-manager",
        "beautifulsoup4",
        "requests",
    ],
    extras_require={
        "dev": [
            "pytest",
            "black",
            "isort",
            "mypy",
        ],
    },
    author="",
    author_email="",
    description="Job Search Automation Platform",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    keywords="job search, automation, ai",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)