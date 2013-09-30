"""
analects
-----

Pull, update the latest source code projects for study and development.


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
    name='analects',
    version='0.1-dev',
    url='http://github.com/tony/analects/',
    license='BSD',
    author='Tony Narlock',
    author_email='tony@git-pull.com',
    description='',
    include_package_data=True,
    install_requires=requirements('requirements.pip'),
    packages=['analects'],
    entry_points=dict(console_scripts=['analects=analects:main']),
    classifiers=[
        'Development Status :: 3 - Alpha',
        "License :: OSI Approved :: BSD License",
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        "Topic :: Software Development",
    ],
)
