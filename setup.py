from setuptools import setup, find_packages

setup(
    name='neomodel',
    version='1.0.1',
    description='An object mapper for the neo4j graph database.',
    long_description=open('README.rst').read(),
    author='Robin Edwards',
    author_email='robin.ge@gmail.com',
    zip_safe=True,
    url='http://github.com/robinedwards/neomodel',
    license='MIT',
    packages=find_packages(),
    keywords='graph neo4j py2neo ORM',
    tests_require=['nose==1.1.2'],
    test_suite='nose.collector',
    install_requires=['py2neo==1.6.4', 'pytz==2014.2'],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Topic :: Database",
    ])
