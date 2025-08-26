"""Setup script for the Pydantic AI Telegram Bot."""

from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

with open("README.md") as f:
    long_description = f.read()

setup(
    name="pydantic-ai-telegram-bot",
    version="1.0.0",
    description="A modular Telegram bot with Pydantic AI and Gemini integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="AI Assistant",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=requirements,
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "telegram-ai-bot=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
