#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys,os
import re
import glob
import json
import shutil
from subprocess import Popen, PIPE
from tempfile import mkdtemp
import inspect
from optparse import OptionParser

import baker

cmds=dict(
    ar='/usr/bin/ar',
    gunzip='/bin/gunzip',
    tar='/bin/tar',
)

control_script_names = ['preinst', 'postinst', 'prerm', 'postrm']

"""
"""

control_fields=[
    ('package', None),          # set from file name argument.
    ('version', None),          # set from file name argument.
    ('section', "base"),
    ('priority', "optional"),
    ('architecture', "all"),
    ('depends', []),            # "libc6"
    ('maintainer', "taro <taro@example.com>"), # todo set from login
    ('description', None),      # set from file name argument.
    ]

def _pack(name_version, 
          description, 
          control_fields_override=None,
          workdir=None,
          cpio_stream=sys.stdin,
          dest=None,

          preinst=None,
          postinst=None,
          prerm=None,
          postrm=None,

          nobuild=False,
          preserve=False,
          ):
    """
        --dest: package up the imorted tree to be installed relative to the dirpath named by dest.
                defaults to root, in which case you should feed aboslute path.
    """

    if not control_fields_override:
        control_fields_override={}

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
    controld.update(control_fields_override)

    # place the control file
    lines=[]
    # xx is control file sensitive to order of fields?
    #    if not, just iter over dict items. or use ordered dict.
    for name, v in control_fields:
        val=controld[name]
        if not val:
            continue
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
    for script in [preinst, postinst, prerm, postrm]:
        stage_control_script(DEBIAN, script)
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
                control_fields=None,
                dest=None, 

                preinst=None,
                postinst=None, 
                prerm=None,
                postrm=None,

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
        control_fields_override=control_fields,
        workdir=workdir, 
        cpio_stream=pipe.stdout,
        dest=dest,

        preinst=preinst,
        postinst=postinst,
        prerm=prerm,
        postrm=postrm,

        nobuild=nobuild)

    status=pipe.wait()
    if status!=0:
        raise RuntimeError('fail', cmd, status)

    return ret


def stage_control_script(DEBIAN, script):
    """Stage preinst, postinst, prerm, postrm
    """
    if script is None:
        return
    assert os.path.basename(script) in control_script_names, ('unknown control script', script)
    staged = os.path.join(DEBIAN, script)
    shutil.copy(script, staged)
    os.chmod(staged, 0755)
    return staged

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

class Cmd(object):

    def __init__(self, f, kwd):
        self.f=f
        self.kwd=kwd

    def __call__(self):

        parser = OptionParser()
        parser.add_option("-f", "--fmt", action="store", dest="fmt", default=None, help="output format")        
        (optd, opta) = parser.parse_args()
        kwd=self.kwd.copy()
        kwd.update(optd.__dict__)
        # major,minor,*args
        positional=opta[2:]

        try:
            return self.f(*positional, **kwd)
        except TypeError, e:
            self.help()
            sys.exit(2)
                

    def help(self):
        print self.f.func_doc

@baker.command
def x_pack_cpio(name_version, description, dest=None, postinst=None, prerm=None, nobuild=False, workdir=None):
    """Pack cpio archive into a .deb package.

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
          prerm=prerm,
          nobuild=nobuild)

    deb_file, workdir=info
    report(deb_file)

def control_field_override(kwargs):
    """
    Extract control fields from kwargs dict.
    returns control field dict and what's left in kwargs.
    """
    control_fields, remainder={}, {}
    for k,v in kwargs.items():
        if k.startswith('cf_'):
            control_fields[k.replace('cf_','')] = v
        else:
            remainder[k]=v
    return control_fields, remainder

@baker.command(default=True)
def pack_paths(
        name_version,
        description,
        dest=None,

        preinst=None,
        postinst=None,
        prerm=None,
        postrm=None,

        nobuild=False,
        workdir=None, 
        **kwargs):
    """Package paths fed to stdin.
    usage:
    find /usr/local/lib/foo | debify.py pack_paths foo_1.0 '<desc>'
    find ./foo/ | debify.py pack_paths foo_1.0 '<desc>' /usr/local/lib/
    find ./foo/ | debify.py pack_paths foo_1.0 '<desc>' /usr/local/lib/ --cf_depends=bar
    """

    control_fields,remainder=control_field_override(kwargs)
    if remainder:
        die('unknown options', repr(remainder))

    info=_pack_paths(
        sys.stdin, 
        name_version, 
        description, 
        control_fields=control_fields,
        dest=dest, 

        preinst=preinst,
        postinst=postinst, 
        prerm=prerm,
        postrm=postrm,

        nobuild=nobuild, 
        workdir=workdir)

    deb_file, workdir=info
    report(deb_file)

@baker.command
def pack_dir(name_version, description, dir, dest=None, postinst=None, prerm=None, nobuild=False, workdir=None):
    """Package files under a directory.

    usage:
    $0 pack dir foo_0.1 'most awesome foo' /usr/lib/foo --dest=/alt/lib/
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
          prerm=prerm,
          nobuild=nobuild)

    if pipe.wait()!=0:
        die("command failed: ...");

    deb_file, workdir=info
    report(deb_file)

@baker.command
def x_deb_relocate(src_pkg_name, new_pkg_name=None, dest=None, postinst=None, prerm=None, nobuild=False, workdir=None):
    """Create a deb file from installed package with alternate destination.

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
                     prerm=prerm,
                     nobuild=nobuild,
                     workdir=workdir, 
                     )

    assert pipe.wait()==0, 'FAIL: '+cmd

    deb_file, workdir=info
    report(deb_file)

@baker.command
def show_files(deb_file):
    """List the contents of a deb file.

       unlike 'dpkg --contents', only the paths are shown.
    """
    # 
    # todo:
    #   do `ar t foo.deb` to select the suffix for  the data.tar.*
    #   suffix used to be gz. more recent versions use xz.
    #   change tar command to use --xz or --gunzip accordingly.
    # 
    assert os.path.exists(cmds['ar']), ('need ar', 'try: sudo apt-get install binutils')

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

@baker.command
def show_installed_pkgs(pkg_glob):
    """Show package and version of installed packages matching a pattern. a nicer version of dpkg -l.
    
    example:
        installed_pkgs yoyo\*
        yoyodyne-server
        yoyodyne-client
        yoyodyne-dev
    """
    # apt list --installed

    for name_version in installed_pkgs(pkg_glob):
        print '='.join(name_version)

def deb_files(pkg_glob):

    return glob.glob(os.path.join('/var/cache/apt/archives', pkg_glob + '*.deb'))

@baker.command
def x_show_deb_files(pkg_glob):
    """List deb files cached under /var/cache/apt/archives/"""

    for df in deb_files(pkg_glob):
        ((name,version),deb_file)=df
        # '='.join([name,version])
        print deb_file

def deb_files(pkg_glob, fetch=False):
    """Find cached deb files for the pkg_glob."""

    if not os.path.exists('/usr/bin/debsums'):
        die('need', '/usr/bin/debsums', 'try apt-get install debsums')
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

@baker.command
def show_modified(pkg_glob, fetch=False, prefix=None):
    """Report files whose checksum differs from the cached deb file.

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

@baker.command
def show_diff(pkg_glob, fetch=False, workdir=None, fmt=None):
    """Show the differences between installed files and content of cached deb file.

    Example:
        debify.py show_diff yoyodyne
        /etc/yoyodyne.conf
        < listen=127.0.0.1
        ---
        > listen=0.0.0.0
    shows that the config file has been modified.
    """
    # todo: take pkg_glob

    for name_ver, debfile in deb_files(pkg_glob, fetch=fetch):
        x_show_diff_deb_file(debfile, workdir=workdir, fmt=fmt)

@baker.command
def x_show_diff_deb_file(deb_file, workdir=None, fmt=None):
    """Show the differences between installed files and content of cached deb file.

    see show_diff_deb_file.
    """

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

class DiffFormatter(object):
    pass

class DiffFormatterSummary(DiffFormatter):
    def content(self, a, b):
        return 'D:', file1.replace(work_dirs[0],'')

class DiffFormatterShell(DiffFormatter):
    def content(self, a, b):
        return 'diff', ' '.join(files)

class DiffFormatterFull(DiffFormatter):
    pass

@baker.command
def diff_deb_files(deb1, deb2, keep=False, fmt='plain'):
    """Diff two deb files better than debdiff.
    usages:
        diff yoyo_01.deb yoyo_02.deb
        diff --fmt=shell --keep yoyo_01.deb yoyo_02.deb  | grep ^diff | bash
    """
    # ar pf yoyodyne_0.1.deb data.tar.gz

    debs=[deb1, deb2]
    names=[ os.path.basename(d).replace('.deb', '') for d in debs ]
    if len(set(names))==1:
        # if the file names are the same, modify by the order.
        names=[ "{name}-{index}".format(name=n, index=i) for i,n in enumerate(names) ]

    work_dirs=[]
    for i,(deb,name) in enumerate(zip(debs, names)):
        work_dir=name+'.d'
        if os.path.exists(work_dir):
            print >>sys.stderr, 'please remove old work dir ', work_dir
            sys.exit(1)
        os.mkdir(work_dir)
        cmd="ar pf {deb_file} data.tar.gz | tar xzf - -C {work_dir}"\
            .format(deb_file=deb,  work_dir=work_dir)

        out,err=Popen([cmd], shell=True, stdout=PIPE).communicate()

        # echo the index, deb-file, work-dir as legend
        print >>sys.stderr, '='.join(map(str,[i, work_dir]))

        work_dirs.append(work_dir)

    out,err=Popen(['/usr/bin/diff', 
                   '-qr',
                   '--exclude=*.pyc',
                   '--exclude=*egg-info*']
                  +work_dirs, stdout=PIPE).communicate()

    for line in out.split('\n'):
        # parse the diff(1) output and reformat
        m=re.match(r'((Files) (.*) and (.*) differ|((Only in) (.*): (.*)))', line)
        if m:
            groups=list(m.groups())
            whole=groups.pop(0)

            if whole.startswith('Files '):
                what=groups.pop(0)  # File, Only in

                # Files {} and {} differ
                files=groups[:2]
                file1=files[0]
                # formatter.content_diff
                if fmt=='shell':
                    # shell expression output is requested.
                    print 'echo diff', ' '.join(files)
                    print 'diff', ' '.join(files)
                else:           # summary
                    print 'D:', file1.replace(work_dirs[0],'')

            elif whole.startswith('Only in '):
                what, dirpath, basename=groups[4:]
                # split dirpath at workdir 
                for i,wd in enumerate(work_dirs):
                    if dirpath.startswith(wd):
                        break
                _,packed_dir_path=dirpath.split(wd)
                file_path=os.path.join(packed_dir_path.lstrip('/'), basename)
                # todo: translate back to the deb name (not work dir name)
                # formatter.fs_diff
                if fmt=='shell':
                    # is there a command that can be used to drill down this difference?
                    print 'echo only-in:', wd, file_path
                else: 
                    print '{index}:'.format(index=i), wd, file_path
            else:
                print line

    # clean up actions
    if not keep:
        # do this in finally clause..
        for d in work_dirs:
            shutil.rmtree(d)

@baker.command
def x_diff_deb_files(deb1, deb2):
    """diff contents of two deb files"""
    
    workdir1=dump_content(deb1, None)
    workdir2=dump_content(deb2, None)

    out,err=Popen(['/usr/bin/diff', '-q', '-r', workdir1, workdir2], stdout=PIPE, stderr=PIPE).communicate()
    for line in out.split('\n'):
        m=re.match(r'^Files (.*) and (.*) differ', line)
        if m:
            print 'diff:', m.group(1).replace(workdir1,'')
            #print 'diff', m.group(1), m.group(2)
        else:
            print line
#    print >>sys.stderr, err('\n')

    # clean up workdirs..
    print 'rm -fr ', workdir1, workdir2

def dump_content(deb_file, workdir):

    if workdir:
        mkdir_p(workdir)
    else:
        workdir=mkdtemp(prefix='debify-')

    cmd='{ar} pf {deb_file} data.tar.gz | tar x -z -C {workdir} -f -'.format(deb_file=deb_file, 
                                                                             workdir=workdir,
                                                                             **cmds)
    p=Popen(cmd, shell=True)
    if p.wait()!=0:
        die("command failed: "+str(cmd))

    return workdir

@baker.command
def examples():
    """Show usage examples.
    """
    doc="""debify usage examples:

* Pack files into debian package by path:
        find /usr/local/yoyodyne | debify.py yoyodyne_0.1 'custom install of yoyodyne'

* Install first and then pack
  With a few commands, install from source can be packaged so you can track and deintall the package later:
        # the usual tgz install flow
        wget ..../yoyodyne-0.1.tgz
        tar xzf yoyodyne-0.1.tgz
        cd yoyodyne-0.1
        ./conifigure
        # Take a pre-instll snapshot of /usr/local. 
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

"""
    print doc
    

def main():
    baker.run()

if __name__=='__main__':

    main()
