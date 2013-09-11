debify
======
Pack software into .deb with one command. 
Plus other commands to make working with debian packages easier.

        $ debify.py examples
        debify usage examples:

* Pack files into debian package by path:
        find /usr/local/yoyodyne | debify.py yoyodyne_0.1 'custom install of yoyodyne'

* Install first and then pack

  With a few commands, software installed from source can be packaged so you can track and de-install it later:

        # the usual tgz install flow
        wget ..../yoyodyne-0.1.tgz
        tar xzf yoyodyne-0.1.tgz
        cd yoyodyne-0.1
        ./conifigure

        # Take a pre-install snapshot of /usr/local. 
        # You have to know that this package only installs to /usr/local. Expand the scope as necessary.
        find /usr/local | sort > x.pre-yoyodyne-files

        # go ahead and install
        sudo make install

        # take a post-install snapshot
        find /usr/local | sort > x.post-yoyodyne-files

        # take the diff
        comm -23 x.post-yoyodyne-files x.pre-yoyodyne-files > x.yoyodyne-files

        # inspect
        less x.yoyodyne-files

        # package what's been installed
        cat x.yoyodyne-files | debify.py opt-yoyodyne_0.1 'custom install of yoyodyne'

        # Install the package so that the dpkg metadata is registered.
        sudo dpkg -i opt-yoyodyne_0.1.deb

* Show files that have been modified

        debify.py show_modified yoyodyne
        yoyodyne=0.1	/etc/yoyodyne.conf


* Show diff of modified files

        debify.py show_diff yoyodyne
        /etc/yoyodyne.conf
        < listen=127.0.0.1
        ---
        > listen=0.0.0.0

* Show installed package,version

        debify.py show_installed_pkgs yoyo\*
        yoyodyne=0.1
        yoyodyne-dev=0.1
        yoyodyne-doc=0.1

   The output can be passed to apt-get install to duplicate the same configuration
   for pkg_version in `ssh stage debify.py show_installed_pkgs yoyo\*`; do sudo apt-get install $pkg_version; done


### TODO
* remove dependency on baker so that it could be a self-contained script
* pypi --> deb
* diff deb files


