from setuptools import setup
    
setup(
    name = "debify",
    # packages = ["debify"],
    py_modules = ["debify"],
    scripts = ["debify.py"],
    version = "0.1.3",
    license = "LGPL",
    platforms = ['POSIX', 'Windows'],
    install_requires=["baker"],
    setup_requires=["nose"],
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
debify: pack a set of files into a .deb file with minimal fuss.

* usage:
  $ find /usr/lib/python2.6/site-packages/foo | python debify.py pack paths py-foo_0.1 'foo for python'
  py-foo_0.1.deb is created

* Why would I want to use this?
  Because you just want to package these files, with one command invocation, without having to go through 
  a tutorial first.

* examples:
  * round up everything under a directory
    package everything under /user/lib/foo to be installed to /alt/lib/foo and save it as foo_0.1.deb.
    $ debify.py pack dir foo_0.1 '<desc>' /usr/lib/foo --dest=/alt/lib
  * path stream
    $ find /usr/lib/foo | debify.py pack paths foo_0.1 '<desc>'
  * cpio
    $ (cd /usr/lib; find foo | cpio -o) | debify.py pack cpio foo_1.0 '<desc>' --dest==/alt/lib

* Motivation
  Keeping track of a set of related files as a package in a single namespace gets you 80% of the 
  benefit of packaging with minimal efforts.  This is true even if you leave out facilities 
  such as dependency management. Consider the alternative: without a convenient way to package files, 
  one often ends up resorting to unmanaged installation options.  

* The goal 
  is to reduce packing friction so that it is practical to manage the apps and dependencies 
  with the OS-native package management system.
  This gives
  - a single name space to manage applications and dependencies
  - ability to deinstall them 
  - archive of dependencies as .deb files for efficient and reproducible of a configuration

* These goals are not achieved by installation and deployment methods such as:
  - rsync
  - ./configure; make install
  - language-specific installers: cpan, setuptools
  - fabric
  These methods install, copy, automate but they do not manage packages.

* The approach
  is to work with application-specific installation methods to pack the bits into .deb packages.
  Right now, the user has to build the list of files installed. 
  The plan is to support automated capture and packaging of common installation methods such as:
  - make install
  - easy_install
  - cpan

* How do I capture installed files?
  To capture installed files, you can do something like:
    # take a snapshot. most things install somehere under /usr/..
  $ find /usr/ | sort > x.pre
  $ sudo make install          # or easy_install or cpan...
  $ find /usr/ | sort > x.post
  $ comm -23 x.post x.pre > x.installed-files
    # inspect the list to see if it makes sense.
  $ less x.installed-files
    # debify
  $ cat x.installed-files | debify.py pack paths foo_0.1 '<desc>'
    # Install the package over the current image (installed files).
    # This has the effect of taking the unmanaged app under the control of debian package system.
  $ sudo dpkg -i foo_0.1.deb
    # You can clean it up like this. The .deb file can be stashed away for later deployment.
  $ sudo dpkg -r foo_0.1

  Having a jail/chroot sandbox environment would make this much faster and more flexible.
  But that would be another project..

"""
    )
