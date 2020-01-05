
all:

pkg=tkm-debify_0.1

upload:
	python setup.py sdist upload

install:
	sudo install debify.py /usr/local/bin/

%.html: %.md
	markdown $< > $@

pack-paths:
	find /usr/local/lib/python2.7/dist-packages/[Bb]aker* \
	| ./debify.py pack_paths opt-baker_0.1 'python baker'

installed_pkgs:
	./debify.py show_installed_pkgs yoyo\*

show_modified:
	./debify.py show_modified yoyodyne

show-diff:
	./debify.py show_diff yoyodyne  # --fmt=json

pack-dir:
	./debify.py pack_dir $(pkg) 'sources.list.d' /etc/apt/sources.list.d/

show_files:
	./debify.py show_files $(pkg).deb

x_show_deb_files:
	./debify.py $@ deb\*

cf-depends:
	echo debify.py | ./debify.py pack_paths tkm-debify_0.1 'a .deb packer' --cf_depends=py-baker

default-command:
	echo debify.py | ./debify.py tkm-debify_0.1 'a .deb packer' --cf_depends=py-baker

with-dest:
	echo debify.py | ./debify.py tkm-debify_0.1 'a .deb packer' /usr/local/bin/
	dpkg --contents  tkm-debify_0.1.deb
t:
	echo /usr/local/bin/rg  | python3 debify.py tkm-rg_11.0.2 'rip-grep'
