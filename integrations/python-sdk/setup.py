from setuptools import setup, find_packages

setup(
    name="contramind-decider",
    version="1.0.0",
    description="Contramind Decision API SDK with JWS verification",
    packages=find_packages(),
    install_requires=[
        "requests>=2.32.0",
        "pynacl>=1.5.0",
        "fastapi>=0.115.0",
        "pydantic>=2.8.0",
    ],
    python_requires=">=3.8",
    author="Contramind",
    license="MIT",
    keywords=["contramind", "decision", "jws", "verification"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
