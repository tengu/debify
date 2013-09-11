
all:

upload:
	python setup.py sdist upload

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
	./debify.py pack_dir yoyodyne_0.1 'sources.list.d' /etc/apt/sources.list.d/

show_files:
	./debify.py show_files yoyodyne_0.1.deb

show_deb_files:
	./debify.py $@ yoyo\*

help:
	./debify.py

examples:
	./debify.py examples


