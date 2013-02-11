from setuptools import setup, find_packages

setup(
        name='neomodel',
        version='0.2.5',
        description='A high level wrapper around py2neo, providing a formal definition for your data model.',
        author='Robin Edwards',
        author_email='robin.ge@gmail.com',
        url='http://github.com/robinedwards/neomodel',
        license='MIT',
        packages=find_packages(),
        keywords='graph neo4j py2neo model',
        zip_safe=True,
        install_requires=['lucene-querybuilder==0.1.6', 'py2neo==1.4.6', 'pytz==2012g'],
        classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Topic :: Software Development :: Libraries :: Python Modules',
            ],
        )
