"""Setup configuration for Ricky AI Assistant."""
from setuptools import setup, find_packages
import os

# Read the README file for the long description
def read_file(filename):
    filepath = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

setup(
    name="ricky-assistant",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A personal AI assistant for email, 3D printing, and verbal inquiries",
    long_description=read_file("README.md"),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ricky-assistant",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Office/Business",
    ],
    python_requires=">=3.8",
    install_requires=[
        # Core dependencies (speech_recognition is optional)
        # All others are standard library
    ],
    extras_require={
        "voice": ["SpeechRecognition>=3.10.0"],
        "dev": ["pytest>=7.0", "black>=22.0", "flake8>=4.0"],
    },
    entry_points={
        "console_scripts": [
            "ricky-cli=ricky.cli:main",
            "ricky-web=ricky.web_server:main",
            "ricky-status=ricky.status_server:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
