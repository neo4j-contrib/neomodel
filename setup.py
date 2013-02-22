from setuptools import setup, find_packages

setup(
    name='neomodel',
    version='0.2.6',
    description='An object mapper for the neo4j graph database.',
    long_description=open('README.rst').read(),
    author='Robin Edwards',
    author_email='robin.ge@gmail.com',
    url='http://github.com/robinedwards/neomodel',
    license='MIT',
    packages=find_packages(),
    keywords='graph neo4j py2neo model',
    tests_require=['nose==1.1.2'],
    install_requires=['lucene-querybuilder==0.1.6', 'py2neo==1.4.6', 'pytz==2012g'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        ])
