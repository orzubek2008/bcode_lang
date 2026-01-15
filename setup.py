from setuptools import setup, find_packages

setup(
    name="bcode",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["requests"],
    python_requires=">=3.8",
    description="BCode — интерпретатор твоего собственного языка программирования",
    author="Твоё имя",
    url="https://github.com/username/bcode_lang",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
)