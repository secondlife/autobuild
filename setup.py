# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# $/LicenseInfo$

import setuptools

setuptools.setup(
    name='autobuild',
    url='http://wiki.secondlife.com/wiki/Autobuild',
    description='Linden Lab Automated Package Management and Build System',
    platforms=['any'],
    packages=setuptools.find_packages(exclude=['tests']),
    use_scm_version={
        'write_to': 'autobuild/version.py',
        'write_to_template': 'AUTOBUILD_VERSION_STRING = \'{version}\'',
    },
    setup_requires=['setuptools_scm'],
    entry_points={
        'console_scripts': ['autobuild=autobuild.autobuild_main:main']
    },
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: Unix',
    ],
    install_requires=['llbase', 'pydot'],
    extras_require={
        'dev': ['pytest'],
        'build': ['build', 'cx-Freeze', 'setuptools_scm']
    },
    python_requires='>=3.7',
)
