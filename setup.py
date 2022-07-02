from setuptools import setup

setup(
    name='starlette_async_wstc',
    version='0.1.0',
    packages=['starlette_async_wstc'],
    author='Rostyslav Misiura',
    author_email='rostislav9999@gmail.com',
    maintainer='Rostyslav Misiura',
    maintainer_email='rostislav9999@gmail.com',
    url='https://github.com/Randomneo/starlette_async_wstc',
    description='Modification of Starlette TestClient to support async calls',
    long_description=open('readme.md').read(),
    long_description_content_type='text/markdown',
    license=u'GNU Affero General Public License, version 3',
    install_requires=[
        'starlette',
        'requests',
        'anyio',
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.6',
    ],
)
