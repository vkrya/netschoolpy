from setuptools import setup


with open("README.md", encoding="utf-8") as f:
    long_description = f.read()


setup(
    name="netschoolpy",
    version="7.1.2",
    description="Асинхронный клиент для «Сетевого города»",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Vladcom4iiik",
    url="https://github.com/Vladcom4iiik/netschoolpy",
    project_urls={
        "Source": "https://github.com/Vladcom4iiik/netschoolpy",
        "Issues": "https://github.com/Vladcom4iiik/netschoolpy/issues",
    },
    license="GPLv3",
    keywords=[
        "netschool",
        "netschoolpy",
        "sgo",
        "сетевой город",
        "дневник",
        "госуслуги",
        "esia",
        "education",
        "api",
        "web Education",
        "ir-tech",
        "электронный журнал",
        "school",
        "web2edu",
        "region",
    ],
    packages=["netschoolpy"],
    package_data={"netschoolpy": ["py.typed"]},
    classifiers=[
        "Natural Language :: Russian",
        "Topic :: Education",
        "Programming Language :: Python :: 3",
    ],
    install_requires=[
        "httpx>=0.23",
        "websockets>=12.0",
    ],
    extras_require={
        "qr": ["qrcode>=7.0"],
    },
    python_requires=">=3.10",
)
