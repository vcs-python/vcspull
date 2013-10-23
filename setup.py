"""
pullv
-----

Obtain and update multiple git, mercurial and subversions repositories
simultaneously.

"""
from setuptools import setup
try:
    from pip.req import parse_requirements
except ImportError:
    def requirements(f):
        reqs = open(f, 'r').read().splitlines()
        reqs = [r for r in reqs if not r.strip().startswith('#')]
        return reqs
else:
    def requirements(f):
        install_reqs = parse_requirements(f)
        reqs = [str(r.req) for r in install_reqs]
        return reqs

setup(
    name='pullv',
    version='0.1.0-dev',
    url='http://github.com/tony/pullv/',
    download_url='https://pypi.python.org/pypi/pullv',
    license='BSD',
    author='Tony Narlock',
    author_email='tony@git-pull.com',
    description='Obtain and update multiple git, mercurial and subversions '
                'repositories simultaneously from a YAML / JSON file.',
    long_description=open('README.rst').read(),
    include_package_data=True,
    install_requires=requirements('requirements.pip'),
    packages=['pullv', 'pullv.repo'],
    entry_points=dict(console_scripts=['pullv=pullv:main']),
    classifiers=[
        'Development Status :: 3 - Alpha',
        "License :: OSI Approved :: BSD License",
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        "Topic :: Software Development",
    ],
)
