import setuptools

with open("README.md", "r") as fh:

    long_description = fh.read()

install_requires = [
       'numpy==1.26.4', 'matplotlib', 'opencv-python==4.7.0.72', 'keyboard', 'pyserial'
    ]

setuptools.setup(
    name='RobotAutonome',
    version='0.1',
    scripts=[] ,
    author="",
    author_email="",
    description="Python code ",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jomarin38/RobotAutonome",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: GPL v3",
        "Operating System :: OS Independent",
     ],
    install_requires=install_requires
 )
