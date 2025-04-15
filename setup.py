from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="scrapfly-crawler",
    version="0.1.0",
    author="Scrapfly",
    author_email="support@scrapfly.io",
    description="A robust web crawler implementation using the Scrapfly API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/robertDouglass/scrapfly-crawler",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.7",
    install_requires=[
        "scrapfly-sdk>=0.8.5",
        "python-dotenv>=0.19.0",
        "aiohttp>=3.8.0",
    ],
    entry_points={
        "console_scripts": [
            "scrapfly-crawler=scrapfly_crawler.cli:main",
        ],
    },
)