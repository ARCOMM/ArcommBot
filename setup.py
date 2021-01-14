import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="arcommbot-TomBurch",
    version="0.0.1",
    author="Tom Burch",
    description="ArcommBot",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ARCOMM/ArcommBot",
    packages=setuptools.find_packages(),
    python_requires='>=3.6',
)