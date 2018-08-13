from setuptools import setup, find_packages
import sys, os

version = '0.1.0'

setup(name='binaryrpc',
      version=version,
      description="A basic binary RPC for Python",
      long_description="",
      classifiers=['Development Status :: 4 - Beta',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
                   'Programming Language :: Python :: 3',
                   'Topic :: Software Development :: Libraries'], 
      keywords='RPC binary',
      author='Ian Haywood',
      author_email='ian@haywood.id.au',
      url='https://github/ihaywood3/binaryrpc/',
      license='LGPLv3',
      py_modules=['binaryrpc'],
      include_package_data=True,
      zip_safe=True,
      install_requires=[]
      )
