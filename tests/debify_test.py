import os
import sys
import unittest
import subprocess as sp
import debify

class DebifyTest(unittest.TestCase):

    def setUp(self):

        # todo: probe
        self.ar_cmd='/usr/bin/ar'
        self.tar_cmd='/bin/tar'

    def test_pack_paths(self):
        """
        """

        input_paths="debify.py"
        deb_file='debify_0.1.deb'

        if os.path.exists(deb_file):
            os.unlink(deb_file)

        p=sp.Popen([sys.executable, debify.__file__, 'pack_paths', 'debify_0.1', 'a package maker'], stdin=sp.PIPE, stderr=sp.PIPE)
        out,err=p.communicate(input_paths)

        # was it created?
        self.assertTrue(os.path, deb_file)
        
        # check archive listing
        out, err = sp.Popen([self.ar_cmd, 'tf', deb_file], stdout=sp.PIPE).communicate()
        triple = out.strip().split('\n')
        # xx on older system, last one could be data.tar.gz
        self.assertEqual(triple, ['debian-binary', 'control.tar.gz', 'data.tar.xz'])

        data_entry=triple[2]

        # check the data
        # cmd=['{ar} pf {deb_file} data.tar.gz | {gunzip} | {tar} tf -'.format(deb_file=deb_file, **cmds)]
        ar_p = sp.Popen([self.ar_cmd, 'pf', deb_file, data_entry], stdin=sp.PIPE, stdout=sp.PIPE)
        tar_p = sp.Popen([self.tar_cmd, 'tfJ', '-'], stdin=ar_p.stdout, stdout=sp.PIPE)
        out, err = tar_p.communicate()
        content_files=out.strip().split('\n')

        # Note that file named in input_paths was packed up in the current directory.
        # For realistic packing, either files are installed in 
        # target location and packed or 'dest' parameter is specified.
        # However, debify is performing correctly and this excercises a lot of functions.
        self.assertEqual( content_files, ['./', './debify.py'] )

        # todo: 
        #   place pkg in tempnam dir.
        #   clean up in finally clause.     


    def test_examples(self):

        p=sp.Popen([sys.executable, debify.__file__, 'examples'], stdout=sp.PIPE, stderr=sp.PIPE)
        out,err=p.communicate()
        self.assertTrue('usage examples' in out)
        
