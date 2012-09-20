from setuptools import setup

setup(
        name='neomodel',
        version='0.0.1',
        description='Graph model for neo4j, wraps py2neo',
        author='Robin Edwards',
        author_email='robin.ge@gmail.com',
        url='http://github.com/robinedwards/neomodel',
        license='MIT',
        py_modules=['neomodel'],
        zip_safe=True,
        classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Topic :: Software Development :: Libraries :: Python Modules',
            ],
        )
