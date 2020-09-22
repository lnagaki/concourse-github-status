from setuptools import setup, find_packages
import re

dependencies = ['requests']
locked_dependencies = []
with open('requirements.txt') as f:
    for line in f:
        req = re.match(r'[A-Za-z0-9=><\.]+', line)
        if req:
            locked_dependencies.append(req.group(0))

setup(
    name="concourse-github-status",
    version="0.1",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "out = github_status:main_out",
            "in = github_status:main_in",
            "check = github_status:main_check",
        ]
    },
    dependencies=dependencies,
    install_requires=locked_dependencies,
)
