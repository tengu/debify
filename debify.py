#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys,os
import re
from subprocess import Popen, PIPE
from tempfile import mkdtemp

"""
"""

control_fields=[
    ('package', None),
    ('version', None),
    ('section', "base"),
    ('priority', "optional"),
    ('architecture', "all"),    # xx default to the building machines.
    ('depends', ["libc6"]),
    ('maintainer', "taro <taro@example.com>"),
    ('description', None),
    ]

def _pack(name_version, 
          description, 
          workdir=None,
          cpio_stream=sys.stdin,
          dest=None,
          postinst=None,
          nobuild=False,
          preserve=False,
          ):
    """
        --dest: package up the imorted tree to be installed relative to the dirpath named by dest.
                defaults to root, in which case you should feed aboslute path.
    """

    # allow .deb suffix. strip to make it the trunk.
    name_version=name_version.replace('.deb', '')

    if not workdir:
        workdir=mkdtemp(prefix='debify-'+name_version)

    try:
        name, version = name_version.split('_')
    except ValueError:
        die("package name must look like foo_0.1, not %s" % name_version)

    DEBIAN=os.path.join(workdir, 'DEBIAN')
    mkdir_p(DEBIAN)

    # gen control file
    controld=dict(control_fields)
    # xx do syntax check on name, version..
    controld.update(dict(package=name,
                         version=version,
                         description=description))

    # place the control file
    lines=[]
    for name, v in control_fields:
        val=controld[name]
        if val is None:
            die("need %s" % name)
        elif type(val) in (list, tuple):
            val=', '.join(val)
        elif isinstance(val, basestring):
            pass
        else:
            die("unexpected type for %s %s" % (name, type(val)))
        lines.append("%s: %s" % (name[:1].upper()+name[1:], val))
    file(os.path.join(DEBIAN, 'control'), 'w').write('\n'.join(lines+['']))
    # 
    # stage the build dir
    # populate with content
    # 
    def import_tree():
        cmd="/bin/cpio -id --no-absolute-filenames --quiet"
        debug('#', cmd)
        pipe=Popen(cmd.split(' '), stdin=cpio_stream, stderr=PIPE)

        Popen(['/bin/sed', 's/^/# /'], stdin=pipe.stderr).wait()

        status=pipe.wait()
        if status!=0:
            raise RuntimeError('fail', cmd, status)

    splice_point=os.path.join(*filter(None,[workdir, dest.lstrip('/') if dest else None]))
    mkdir_p(splice_point)
    debug('#', 'splice_point:', splice_point)
    with_dir(splice_point, import_tree)
    # 
    # configure the build dir
    # 
    if postinst:
        # user-supplied postinst script
        staged_postinst=os.path.join(DEBIAN,'postinst')
        shcopy(postinst, staged_postinst)
        os.chmod(staged_postinst, 0755)
    # 
    # build
    # 
    deb_file=None
    if not nobuild:
        deb_file=name_version + '.deb'
        cmd="/usr/bin/dpkg-deb --build %s %s" % (workdir, deb_file) #  1>&2
        debug('#', cmd)
        pipe=Popen(cmd.split(' '), stderr=PIPE, stdout=PIPE)

        Popen(['/bin/sed', 's/^/# /'], stdin=pipe.stderr).wait()
        Popen(['/bin/sed', 's/^/# /'], stdin=pipe.stdout).wait()

        pipe.stderr.close()
        status=pipe.wait()
    #
    # cleanup
    # 
    if not preserve:
        try:
            rm_rf(workdir)
            workdir=None
        except Exception, e:
            error("clean up of work dir {workdir} failed: {error} ".format(workdir=workdir,
                                                                                error=str(e)))
    return deb_file, workdir

def _pack_paths(path_stream, 
                name_version, 
                description, 
                dest=None, 
                postinst=None, 
                nobuild=False, 
                workdir=None):
    """
        usage:
            find /usr/lib/foo | $0 pack_paths foo_0.1 'awsome app foo'
    """
    # 
    # convert path stream to cpio archive
    # 
    cmd="/bin/cpio -o --quiet"
    pipe=Popen(filter(None, cmd.split(' ')), stdin=path_stream, stdout=PIPE)

    ret=_pack(
        name_version, 
        description, 
        workdir=workdir, 
        cpio_stream=pipe.stdout,
        dest=dest,
        postinst=postinst,
        nobuild=nobuild)

    status=pipe.wait()
    if status!=0:
        raise RuntimeError('fail', cmd, status)

    return ret

################ util
def say(inputfile, *phrases):
    inputfile.write(' '.join([unicode(p).encode('utf8') for p in phrases])+'\n')
def debug(*phrases):
    say(sys.stderr, *phrases)
def error(*phrases):
    say(sys.stderr, *phrases)
def report(*phrases):
    say(sys.stdout, *phrases)
def die(*phrases):
    error(*phrases)
    sys.exit(1)

def with_dir(adir, thunk):

    pwd=os.getcwd()
    os.chdir(adir)
    try:
        return thunk()
    finally:
        os.chdir(pwd)

def mkdir_p(newdir):
    """
    from http://code.activestate.com/recipes/82465/
    works the way a good mkdir should :)
        - already exists, silently complete
        - regular file in the way, raise an exception
        - parent directory(ies) does not exist, make them as well
    """
    if os.path.isdir(newdir):
        pass
    elif os.path.isfile(newdir):
        raise OSError("a file with the same name as the desired " \
                      "dir, '%s', already exists." % newdir)
    else:
        head, tail = os.path.split(newdir)
        if head and not os.path.isdir(head):
            mkdir_p(head)
        if tail:
            os.mkdir(newdir)

def rm_rf(p):
    """ rm -fr use at your own risk """
    if not os.path.exists(p):
        pass
    elif os.path.isdir(p):
        for ep in (os.path.join(p,e) for e in os.listdir(p)):
            rm_rf(ep)
        os.rmdir(p)
    else:                       # isfile or islink
        os.unlink(p)

################

def main():
    import baker

    @baker.command
    def pack_cpio(name_version, description, dest=None, postinst=None, nobuild=False, workdir=None):
        """ pack cpio archive into a .deb package.
usage: 
 $ find /usr/lib/foo/ | cpio -o | debify.py pack_cpio foo_1.0 '<desc>'
 $ (cd /usr/lib; find foo | cpio -o) | debify.py pack_cpio foo_1.0 '<desc>' --dest==/alt/lib
            
        """
        debug('#', 'workdir:', workdir)
        info=_pack(
              name_version, 
              description, 
              workdir=workdir, 
              cpio_stream=sys.stdin,
              dest=dest,
              postinst=postinst,
              nobuild=nobuild)

        deb_file, workdir=info
        report(deb_file)

    @baker.command
    def pack_paths(name_version, description, dest=None, postinst=None, nobuild=False, workdir=None):
        """ pack paths fed to stdin as a .deb package.
usage:
  find /usr/lib/foo | $0 pack_paths foo_1.0 '<desc>'
        """
        info=_pack_paths(
            sys.stdin, 
            name_version, 
            description, 
            dest=dest, 
            postinst=postinst, 
            nobuild=nobuild, 
            workdir=workdir)

        deb_file, workdir=info
        report(deb_file)

    @baker.command
    def pack_dir(name_version, description, dir, dest=None, postinst=None, nobuild=False, workdir=None):
        """ package files under a directory
usage:
  $0 pack_dir foo_0.1 'most awsome foo' /usr/lib/foo --dest=/alt/lib/
        """
        base_dir,target_dir=os.path.split(dir.rstrip('/'))
        pipe=Popen(['/bin/sh', '-c', 
                    '/usr/bin/find {target_dir} | /bin/cpio -o --quiet'.format(target_dir=target_dir)], 
                   stdout=PIPE, 
                   cwd=base_dir)
        info=_pack(
              name_version, 
              description, 
              workdir=workdir, 
              cpio_stream=pipe.stdout,
              dest=dest,
              postinst=postinst,
              nobuild=nobuild)

        if pipe.wait()!=0:
            die("command failed: ...");

        deb_file, workdir=info
        report(deb_file)

    @baker.command
    def relocate(src_pkg_name, new_pkg_name=None, dest=None, postinst=None, nobuild=False, workdir=None):
        """ create a .deb file from installed package with alternate destination.
            package name, version and description is taken from the source (installed) package.

            usage:
               $0 relocate <src_pkg_name> --dest=<dest_dir>
            example:
	       $0 relocate libfoo --dest=/alt/lib/
                  Suppose package 'libfoo' installs under  /usr/lib/foo
                  Newly created package will install under /alt/lib/foo
        """

        cmdtpl=['/usr/bin/dpkg-query', '-W', '-f', '${Package}_${Version}::::${Description}', src_pkg_name]
        p=Popen(cmdtpl, stdout=PIPE)
        name_version, description=p.stdout.read().split('::::')
        assert p.wait()==0, ' '.join(('FAIL:',)+cmdtpl)

        description+=' (relocated to {dest})'.format(dest=dest)
        if new_pkg_name:
            src_pkg_name, version=name_version.split('_',1)
            name_version='_'.join([new_pkg_name, version])
        else:
            name_version='relocated-'+name_version
        
        cmd='/usr/bin/dpkg -L {src_pkg_name}'.format(src_pkg_name=src_pkg_name)
        pipe=Popen(filter(None, cmd.split(' ')), stdout=PIPE)

        info=_pack_paths(pipe.stdout,
                         name_version, 
                         description, 
                         dest=dest,
                         postinst=postinst,
                         nobuild=nobuild,
                         workdir=workdir, 
                         )

        assert pipe.wait()==0, 'FAIL: '+cmd

        deb_file, workdir=info
        report(deb_file)

    baker.run()

if __name__=='__main__':
    
    main()
