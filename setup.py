from setuptools import setup

setup(
        name='neomodel',
        version='0.0.1',
        description='A high level wrapper around to py2neo, providing a formal definition for your data model.',
        author='Robin Edwards',
        author_email='robin.ge@gmail.com',
        url='http://github.com/robinedwards/neomodel',
        license='MIT',
        py_modules=['neomodel'],
        zip_safe=True,
        install_requires=['lucene-querybuilder==0.1.6', 'py2neo==1.3.5'],
        classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Topic :: Software Development :: Libraries :: Python Modules',
            ],
        )
