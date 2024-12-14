from setuptools import setup, find_packages

# Read the long description from README.md
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="python-finance-buddy",
    version="1.0.0",
    author="Michael DeGuzis",
    author_email="mdeguzis@gmail.com",  # Replace with your email
    description="A toolkit for financial calculations and analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mdeguzis/Python-finance-buddy",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "numpy>=1.20",
        "pandas>=1.2",
        "matplotlib>=3.4",
    ],
    entry_points={
        "console_scripts": [
            # Define CLI commands
            "finance-buddy=finance_buddy:main"
        ],
    },
)
