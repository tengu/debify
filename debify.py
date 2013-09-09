#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys,os
import re
import glob
import json
from subprocess import Popen, PIPE
from tempfile import mkdtemp

cmds=dict(
    ar='/usr/bin/ar',
    gunzip='/bin/gunzip',
    tar='/bin/tar',
)

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
            find /usr/lib/foo | $0 pack paths foo_0.1 'awsome app foo'
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

class Panya(object):
    """ manage command functions
    """

    def __init__(self):
        self.dispatcher=dict()

    def command(self, f):
        """ replacement for @baker.command
            register the function with the dispatcher.
            function name is split by the first _ into major and minor parts.
        """
        try:
            major, minor=f.__name__.split('_', 1)
        except ValueError:
            major, minor='do', f.__name__
        self.dispatcher.setdefault(major,{})[minor]=f

        # populate help map with docs: help --> 'show files' --> show_files.func_doc
        # xx how to sort? lexical or frequency of usage?
        for major, cmap in self.dispatcher.items():
            self.dispatcher.setdefault('help',{})[major]=(lambda ma: 
                                                          lambda mi=None: self.help(ma,mi))(major)

        return f

    def help(self, major, minor):
        me=os.path.basename(sys.argv[0])
        if minor==None:
            for minor, f in self.dispatcher[major].items():
                print me, major, minor+':', f.func_doc
        else:
            print me, major, minor+':', self.dispatcher[major][minor].func_doc

    def docs(self):
        for major, cmap in self.dispatcher.items():
            for minor, cfun in cmap.items():
                yield major, minor, cfun.func_doc

    def usage(self):
        """ me major minor: first line of func doc
        """
        # from inspect import getargspec
        synopsis=[]
        for major, cmap in self.dispatcher.items():
            if major=='help':
                continue
            for minor, cfun in cmap.items():
                synopsis.append("%-25s %s" % (' '.join([os.path.basename(sys.argv[0]), 
                                                     major, 
                                                     minor+':']), 
                                            (cfun.func_doc or '').split('\n')[0].strip()))
        return "".join(["\nUsage:",
                        "\n    ".join(['']+synopsis),
                        "\nSee '%s help foo bar' for more detail." % (sys.argv[0])])

panya=Panya()

@panya.command
def pack_cpio(name_version, description, dest=None, postinst=None, nobuild=False, workdir=None):
    """ pack cpio archive into a .deb package.
    usage: 
     $ find /usr/lib/foo/ | cpio -o | debify.py pack cpio foo_1.0 '<desc>'
     $ (cd /usr/lib; find foo | cpio -o) | debify.py pack cpio foo_1.0 '<desc>' --dest==/alt/lib

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

@panya.command
def pack_paths(name_version, description, dest=None, postinst=None, nobuild=False, workdir=None):
    """ pack paths fed to stdin as a .deb package.
    usage:
    find /usr/lib/foo | $0 pack paths foo_1.0 '<desc>'
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

@panya.command
def pack_dir(name_version, description, dir, dest=None, postinst=None, nobuild=False, workdir=None):
    """ package files under a directory
    usage:
    $0 pack dir foo_0.1 'most awsome foo' /usr/lib/foo --dest=/alt/lib/
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

@panya.command
def deb_relocate(src_pkg_name, new_pkg_name=None, dest=None, postinst=None, nobuild=False, workdir=None):
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

@panya.command
def show_files(deb_file):
    """ list the contents of a deb file.
        unlike 'dpkg --contents', only the file names are shown.
        deb_file: deb file whose files are to be shown.
    """

    # ar pf - data.tar.gz | gunzip | tar tf -
    # ar does not read from stdin
    cmd=['{ar} pf {deb_file} data.tar.gz | {gunzip} | {tar} tf -'.format(deb_file=deb_file, **cmds)]
    p=Popen(cmd, shell=True)
    if p.wait()!=0:
        die("command failed: "+str(cmd))

### verification

def installed_pkgs(pkg_glob):
    """generate installed (pkg,ver) matching pkg_glob"""

    fmt="""${Status}\t${Package}=${Version}\n"""
    out,err=Popen(['/usr/bin/dpkg-query', '-f', fmt, '-W', pkg_glob], stdout=PIPE, stdin=PIPE).communicate()
    for line in out.split('\n'):
        if not line:
            continue
        status,pkg=line.split('\t')
        if status=='install ok installed':
            name,version=pkg.split('=')
            yield (name,version)
        elif status=='unknown ok not-installed':
            pass
        else:
            print >>sys.stderr, line

    for line in (err or '').split('\n'):
        if line:
            print >>sys.stderr, line

@panya.command
def show_installed_pkgs(pkg_glob):
    """show package and version of installed packages matching a pattern. a nicer version of dpkg -l.
    
    example:
        installed_pkgs yoyo\*
        yoyodyne-server
        yoyodyne-client
        yoyodyne-dev
    """
    for name_version in installed_pkgs(pkg_glob):
        print '='.join(name_version)

def deb_files(pkg_glob):

    return glob.glob(os.path.join('/var/cache/apt/archives', pkg_glob + '*.deb'))

@panya.command
def show_deb_files(pkg_glob):
    """list cached .deb files under /var/cache/apt/archives/"""

    for df in deb_files(pkg_glob):
        print df

def deb_files(pkg_glob, fetch=False):
    """find cached deb files for the pkg_glob"""

    assert os.path.exists('/usr/bin/debsums'), ('need', '/usr/bin/debsums', 'try apt-get install debsums')
    # 
    # enumerate installed pkgs
    # 
    pkgs=installed_pkgs(pkg_glob)
    # 
    # find debfile for these pkgs
    # 
    debs=[]
    for name_ver in pkgs:
        name_eq_ver='='.join(name_ver)
        deb_glob=os.path.join('/var/cache/apt/archives/', '{0}*.deb'.format('_'.join(name_ver)))
        matches=glob.glob(deb_glob)
        if not matches:
            # 
            # if missing fetch: apt-get install --reinstall --download-only foo=ver
            # 
            if fetch:
                print >>sys.stderr, 'fetching:', name_eq_ver
                p=Popen(['/usr/bin/sudo', '/usr/bin/apt-get',  'install', '--reinstall', '--download-only', name_eq_ver])
                p.wait()        # xx check status
            else:
                print >>sys.stderr, 'skipping:', name_eq_ver
                continue

        matches=glob.glob(deb_glob)
        if not matches:
            print >>sys.stderr, 'failed to fetch', name_eq_ver
            continue
        assert len(matches)==1, ('multiple or zero matches', matches, deb_glob)
        debs.append( (name_ver, matches[0]) )

    return debs

@panya.command
def show_modified(pkg_glob, fetch=False, prefix=None):
    """report files whose checksum differs from the pkg
    * fetch:  downloads the deb file if necessary
    * prefix: first col in tsv if supplied
    """
    # 
    # do checksum analysis using the right deb file.
    # 
    for name_ver, debfile in deb_files(pkg_glob, fetch=fetch):

        out,err=Popen(['/usr/bin/debsums', '-c', '--generate=all', debfile], stdout=PIPE, stderr=PIPE).communicate()

        for line in out.split('\n'):
            if line:
                print '\t'.join(filter(None, [prefix]+['='.join(name_ver), line]))

        for line in err.split('\n'):
            if line:
                print >>sys.stderr, line

@panya.command
def show_diff(deb_file, workdir=None, fmt=None):
    """diff ..."""

    if workdir:
        mkdir_p(workdir)
    else:
        workdir=mkdtemp(prefix='debify-')

    workdir=dump_content(deb_file, workdir)
    for xdir,sdir,files in os.walk(workdir):
        for f in files:
            packaged=os.path.join(xdir, f)
            assert packaged.startswith(workdir), (packaged, xdir)
            installed=packaged[len(workdir):]
            out,err=Popen(['/usr/bin/diff', packaged, installed], stdout=PIPE).communicate()
            if out:
                if fmt=='json':
                    print json.dumps(dict(file=installed, diff=out))
                else:
                    print installed
                    print out


def dump_content(deb_file, workdir):

    cmd='{ar} pf {deb_file} data.tar.gz | tar x -z -C {workdir} -f -'.format(deb_file=deb_file, 
                                                                             workdir=workdir,
                                                                             **cmds)
    p=Popen(cmd, shell=True)
    if p.wait()!=0:
        die("command failed: "+str(cmd))

    return workdir
        

@panya.command
def help_usage():
    """ usage
    """
    print panya.usage()

def cmd_args(me, major=None, minor=None, *rest):
    if not minor:
        major,minor='help','usage'
    return major, minor, rest

def main():

    major, minor, args=cmd_args(*sys.argv)
    # resove the command
    try:
        cmd_f=panya.dispatcher[major][minor]
    except:
        die("no such command '%s' '%s'" % (major, minor), panya.usage())
    # invoke it
    cmd_f(*args)

if __name__=='__main__':
    
    main()
