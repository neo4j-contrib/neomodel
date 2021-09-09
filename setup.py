import sys

from setuptools import setup, find_packages

setup(
    name='neomodel',
    version='4.0.6',
    description='An object mapper for the neo4j graph database.',
    long_description=open('README.rst').read(),
    author='Robin Edwards',
    author_email='robin.ge@gmail.com',
    zip_safe=True,
    url='http://github.com/neo4j-contrib/neomodel',
    license='MIT',
    packages=find_packages(exclude=('test', 'test.*')),
    keywords='graph neo4j ORM OGM',
    scripts=['scripts/neomodel_install_labels',
             'scripts/neomodel_remove_labels'],
    setup_requires=[
        'pytest-runner'] if any(x in ('pytest', 'test') for x in sys.argv) else [],
    tests_require=['pytest>=6.2.4', 'shapely', 'neobolt'],
    install_requires=['neo4j-driver==4.3.1', 'pytz>=2021.1',
                      "neobolt==1.7.17", "Shapely==1.7.1", "six==1.16.0"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Database",
    ])
