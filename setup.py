import os
from codecs import open

from setuptools import setup, find_packages

ENV = os.environ.get('MOE_DEPLOYMENT_ENV') or 'prod'

package_name = 'moe-neomodel' + '-' + ENV

# Get the long description from the README file
with open('README.rst', encoding='utf-8') as f:
    long_description = f.read()

with open('VERSION', encoding='utf-8') as f:
    package_version = f.read()

print "**************************************************"
print "Installing package: " + package_name + " version: " + package_version
print "**************************************************"

setup(
    name=package_name,
    version=package_version,
    description='An object mapper for the neo4j graph database.',
    long_description=long_description,
    author='Robin Edwards',
    author_email='robin.ge@gmail.com',
    zip_safe=True,
    url='http://github.com/robinedwards/neomodel',
    license='MIT',
    packages=find_packages(exclude=('tests',)),
    keywords='graph neo4j ORM OGM',
    scripts=['scripts/neomodel_install_labels'],
    tests_require=['nose==1.3.7'],
    test_suite='nose.collector',
    install_requires=['neo4j-driver==1.2.1', 'pytz>=2016'],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Database",
    ])
