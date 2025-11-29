from setuptools import setup, find_packages
from setuptools.command.build_py import build_py
import os

# Custom build command
class CustomBuild(build_py):
    def run(self):
        # First, run the standard build
        build_py.run(self)
        
        # Now, run custom C++ builder
        print("Running MiiPy C++ Backend Builder")
        try:
            from miipy.builder import build_backend
            build_backend()
        except Exception as e:
            print(f"❌ C++ build failed: {e}")
            # Depending on strictness, you might want to raise the error
            # raise e

# Read README for long description
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="miipy",
    version="1.0.0",
    author="Daviti Zhgenti",
    description="A Python library to render Nintendo Miis by compiling the FFL-Testing backend.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/miipy",
    packages=find_packages(),
    include_package_data=True, # This tells setuptools to use MANIFEST.in
    
    install_requires=[
        "pillow",
    ],
    
    python_requires=">=3.7",

    # This line hooks our custom builder into the install process
    cmdclass={
        'build_py': CustomBuild,
    },
    
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
    ],
)