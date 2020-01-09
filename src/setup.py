import setuptools

setuptools.setup(
    name="fang-server",
    version="2020.0.1",
    packages=setuptools.find_packages("src/"),
    package_dir={'': 'src/'},
    author="Suhendi",
    author_email="suhendi999@gmail.com",
    description="A small server to serve APIs",
    install_requires=[
        'peewee>=3.11.2',
        'Werkzeug>=0.16.0',
    ]
)


