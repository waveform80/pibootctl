from setuptools import setup, find_packages

setup(
    name="pictl",
    version="0.1",
    description="pictl enables and disables hardware components on the Raspberry Pi",
    license="GPLv2+",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "pictl = pictl:main",
        ],
    }
)
