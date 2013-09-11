from setuptools import setup
    
setup(
    name = "debify",
    # packages = ["debify"],
    py_modules = ["debify"],
    scripts = ["debify.py"],
    version = "0.1.2",
    license = "LGPL",
    platforms = ['POSIX', 'Windows'],
    install_requires=["baker"]
    description = "pack a set of files into a .deb file with minimal fuss.",
    author = "karasuyamatengu",
    author_email = "karasuyamatengu@gmail.com",
    url = "https://github.com/tengu/debify",
    keywords = ["debian", "package"],
    classifiers = [
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: POSIX :: Linux", # debian, to be specific
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Topic :: Utilities",
        "Topic :: Software Development",
        ],
    long_description = """\

"""
    )
