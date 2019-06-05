import os
import getpass
import build

from os.path import join, normpath
from .common import (venv, task, exists, delete_foreign_tasks)
from ConfigParser import SafeConfigParser
from contextlib import nested


core_dependencies = [
    'yarn',
    'jq',
    'libevent',
    'zeromq',
    'libtool',
    'libmemcached',
    'gawk',
    'libxmlsec1',
    'pkg-config',
    'autoconf',
    'automake'
]


@task()
def install_core_dependencies(c):
    print 'Installing dependencies, compilers and required libraries'
    c.run('brew install %s' % ' '.join(list(core_dependencies)))
    if not c.run('brew link libevent', quiet=True):
        c.sudo('brew link libevent')


@task()
def uninstall_lamp_mac(c):
    """
    Uninstalls lamp from development environment
    """
    c.run("brew uninstall php56-imagick php56 homebrew/apache/httpd24 mysql")


@task()
def upgrade_yarn_mac(c):
    c.run("brew update && brew upgrade yarn")


@task()
def create_venv_python_3(c):
    if not exists(c, '/usr/local/bin/python3'):
        if not exists(c, '/usr/local/bin/brew'):
            c.run('ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"')
        c.run("brew update")
        c.run("brew upgrade")
        c.run("brew install python@2")
        c.run("brew install python")  # This installs python3
        c.run("brew install libmagic")  # needed for python-magic
        c.run('pip2 install virtualenv psycopg2 requests jinja2')
        c.run('python3 -m pip install virtualenv')
    venv3 = os.path.join(os.getcwd(), "venvpy3")
    if exists(c, os.path.join(venv3, "bin/activate")):
        print("Found an already existing virtual env with python 3")
        return
    print("Creating a fresh virtual env with python 3")
    c.run('chmod -R o-rwx ' + venv3)
    c.run('python3 -m virtualenv --python python3 %s' % venv3)


def venv_py3_mac(c):
    project_prefix = c.config.get('_project_home', c.config._project_prefix[:-1])
    return nested(c.cd(project_prefix), c.prefix('source venv/bin/activate'))


@task()
def update_pip_requirements_mac(c, force_reinstall=False):
    """
    Update external dependencies on remote host.
    """
    from .build import separate_pip_install
    with venv(c):
        c.run('pip install -U setuptools "pip<10" ')

    if force_reinstall:
        with venv(c):
            c.run("pip install --ignore-installed -r %s/requirements.txt" % (c.config.projectpath))
    else:
        specials = [
            # setuptools and lxml need to be installed before compiling dm.xmlsec.binding
            ("lxml", None, None),
            # Thanks to https://github.com/pypa/pip/issues/4453 disable wheel separately.
            ("dm.xmlsec.binding", "%s --install-option='-q'", "%s --install-option='-q'"),
            ("pycurl", None, 'env PYCURL_SSL_LIBRARY=openssl MACOSX_DEPLOYMENT_TARGET="10.13" LDFLAGS="-L/usr/local/opt/openssl/lib" CPPFLAGS="-I/usr/local/opt/openssl/include" %s'),
        ]
        for package, wrapper, mac_wrapper in specials:
            wrapper = mac_wrapper
            separate_pip_install(c, package, wrapper)
        cmd = "pip install -r %s/requirements.txt" % (c.config.projectpath)
        with venv(c):
            c.run("yes w | %s" % cmd, warn=True)


@task()
def install_database(c):
    """
    Install a postgresql DB server
    """
    print('Installing Postgresql')
    c.run('brew install postgresql')
    c.run('brew tap homebrew/services')
    c.run('brew services start postgres')


@task()
def install_java(c):
    """Install openjdk-11-jdk. Require sudo."""
    print('Installing Java')
    c.run('brew cask install java')


@task()
def install_elasticsearch(c):
    """Install elasticsearch"""
    ELASTICSEARCH_VERSION = c.config.elasticsearch_version

    base_extract_path = normpath(
        join(c.config.projectpath, 'var'))
    extract_path = join(base_extract_path, 'elasticsearch')
    if exists(c, extract_path):
        print("elasticsearch already installed")
        c.run('rm -rf %s' % extract_path)

    base_filename = 'elasticsearch-{version}'.format(version=ELASTICSEARCH_VERSION)
    tar_filename = base_filename + '.tar.gz'
    sha1_filename = tar_filename + '.sha1'
    with c.cd(base_extract_path):
        if not exists(c, tar_filename):
            c.run('curl -o {fname} https://artifacts.elastic.co/downloads/elasticsearch/{fname}'.format(fname=tar_filename))
        sha1_expected = c.run('curl https://artifacts.elastic.co/downloads/elasticsearch/' + sha1_filename).stdout
        sha1_effective = c.run('openssl sha1 ' + tar_filename).stdout
        if ' ' in sha1_effective:
            sha1_effective = sha1_effective.split(' ')[-1]
        assert sha1_effective == sha1_expected, "sha1sum of elasticsearch tarball doesn't match, exiting"
        c.run('tar zxf ' + tar_filename)
        c.run('rm ' + tar_filename)
        c.run('mv %s elasticsearch' % base_filename)

        # ensure that the folder being scp'ed to belongs to the user/group
        user = c.config._user if '_user' in c.config else getpass.getuser()
        c.run('chown -R {user}:{group} {path}'.format(
            user=user, group=c.config._group,
            path=extract_path))

        # Make elasticsearch and plugin in /bin executable
        c.run('chmod ug+x {es} {esp} {in_sh} {sysd} {log}'.format(
            es=join(extract_path, 'bin/elasticsearch'),
            esp=join(extract_path, 'bin/elasticsearch-plugin'),
            in_sh=join(extract_path, 'bin/elasticsearch.in.sh'),
            sysd=join(extract_path, 'bin/elasticsearch-systemd-pre-exec'),
            log=join(extract_path, 'bin/elasticsearch-translog'),
        ))
        c.run(c.config.projectpath + '/var/elasticsearch/bin/elasticsearch-plugin install https://artifacts.elastic.co/downloads/elasticsearch-plugins/analysis-smartcn/analysis-smartcn-{version}.zip'.format(version=ELASTICSEARCH_VERSION))
        c.run(c.config.projectpath + '/var/elasticsearch/bin/elasticsearch-plugin install https://artifacts.elastic.co/downloads/elasticsearch-plugins/analysis-kuromoji/analysis-kuromoji-{version}.zip'.format(version=ELASTICSEARCH_VERSION))

        print "Successfully installed elasticsearch"


@task()
def install_services(c):
    """
    Install redis server
    """
    print('Installing redis server')
    c.run('brew install redis', warn=True)
    c.run('brew install memcached', warn=True)
    c.run('brew tap homebrew/services')
    c.run('brew services start redis')
    c.run('brew services start memcached')
    

@task()
def install_borg(c):
    print("Installing borg")
    c.run('brew cask install borgbackup')
    ncftp_path = '/usr/local/bin/ncftp'
    if not exists(c, ncftp_path):
        print('Installing ncftp client')
        c.run('brew install ncftp')


@task(install_core_dependencies, upgrade_yarn_mac)
def install_assembl_server_deps(c):
    print('Assembl Server dependencies installed')


@task()
def install_single_server(c):
    """
        Will install all assembl components on a single server.
        Follow with bootstrap_from_checkout
    """
    print('Installing Assembl Server')
    install_java(c)
    install_elasticsearch(c)
    install_database(c)
    install_assembl_server_deps(c)
    install_services(c)
    install_borg(c)
    print('Assembl Server installed')


@task()
def bootstrap_from_checkout(c, backup=False):
    """
    Creates the virtualenv and install the app from git checkout
    """
    print('Bootstraping')
    # updatemaincode(c, backup=backup)
    build_virtualenv(c)
    create_venv_python_3(c)
    app_update_dependencies(c, backup=backup)
    app_setup(c, backup=backup)
    """check_and_create_database_user(c)
    app_compile_nodbupdate(c)
    set_file_permissions(c)
    if not backup:
        app_db_install(c)
    else:
        database_restore(c)
    app_reload(c)
    webservers_reload(c)
    if not is_integration_env() and env.wsginame != 'dev.wsgi':
        create_backup_script(c)
        create_alert_disk_space_script(c)"""
    print('Bootstraping finished')


def updatemaincode(c, backup=False):
    """
    Update code and/or switch branch
    """
    if not backup:
        print('Updating Git repository')
        with c.cd(join(c.config.projectpath)):
            c.run('git fetch')
            c.run('git checkout %s' % c.config._internal.gitbranch)
            c.run('git pull %s %s' % (c.config._internal.gitrepo, c.config._internal.gitbranch))

        path = join(c.config.projectpath, '..', 'url_metadata')
        if exists(c, path):
            print('Updating url_metadata Git repository')
            with c.cd(path):
                c.run('git pull')
            with venv_py3_mac(c):
                c.run('python3 -m pip install -e ../url_metadata')


@task()
def build_virtualenv(c, with_setuptools=False):
    """
    Build the virtualenv
    """
    print('Creating a fresh virtualenv')
    venv = c.config.get('virtualenv', None)
    if not venv:
        if exists(c, 'venv'):
            print('The virtualenv seems to already exist, so we don\'t try to create it again')
            print('(otherwise the virtualenv command would produce an error)')
            return
        else:
            # _project_prefix is defined by Invoke at run-time
            project_prefix = c.config.get('_project_home', c.config._project_prefix[:-1])
            venv = os.path.join(project_prefix, 'venv')

    setup_tools = ''
    if not with_setuptools:
        setup_tools = '--no-setuptools'
    c.run('python2 -mvirtualenv %s %s' % (setup_tools, "venv"))

    # Virtualenv does not reuse distutils.cfg from the homebrew python,
    # and that sometimes precludes building python modules.
    bcfile = "/usr/local/Frameworks/Python.framework/Versions/2.7/lib/python2.7/distutils/distutils.cfg"
    vefile = venv + "/lib/python2.7/distutils/distutils.cfg"
    sec = "build_ext"
    if exists(c, bcfile):
        brew_config = SafeConfigParser()
        brew_config.read(bcfile)
        venv_config = SafeConfigParser()
        if exists(c, vefile):
            venv_config.read(vefile)
        if (brew_config.has_section(sec) and
                not venv_config.has_section(sec)):
            venv_config.add_section(sec)
            for option in brew_config.options(sec):
                val = brew_config.get(sec, option)
                venv_config.set(sec, option, val)
            with open(vefile, 'w') as f:
                venv_config.write(f)


@task()
def app_update_dependencies(c, force_reinstall=False, backup=False):
    """
    Updates all python and javascript dependencies.  Everything that requires a
    network connection to update
    """
    if not backup:
        ensure_requirements(c)
    update_pip_requirements_mac(c, force_reinstall=force_reinstall)
    build.update_node(c, force_reinstall=force_reinstall)
    build.update_bower(c)
    build.update_bower_requirements(c, force_reinstall=force_reinstall)
    build.update_npm_requirements(c, force_reinstall=force_reinstall)


def ensure_requirements(c):
    "Copy the appropriate frozen requirements file into requirements.txt"
    target = c.config.frozen_requirements
    if target:
        with c.cd(c.config.projectpath):
            c.run("cp %s requirements.txt" % target)
    else:
        # TODO: Compare a hash in the generated requirements
        # with the hash of the input files, to avoid regeneration
        generate_new_requirements(c)


def generate_new_requirements(c):
    "Generate frozen requirements.txt file (with name taken from environment)."
    ensure_pip_compile()
    target = c.config.frozen_requirements or 'requirements.txt'
    venv(" ".join(("pip-compile --output-file", target, c.config.requirement_inputs)))


def ensure_pip_compile(c):
    if not exists(c, c.config.venvpath + "/bin/pip-compile"):
        separate_pip_install('pip-tools')


def separate_pip_install(c, package, wrapper=None):
    cmd = '%(venvpath)s/bin/pip install'
    if wrapper:
        cmd = wrapper % (cmd,)
    cmd = "egrep '^%(package)s' %(projectpath)s/requirements-prod.frozen.txt | sed -e 's/#.*//' | xargs %(cmd)s" % dict(cmd=cmd, package=package, **c.config)
    c.run(cmd)


def get_upload_dir(c, path=None):
    path = path or c.config.get('upload_root', 'var/uploads')
    if path != '/':
        path = join(c.config.projectpath, path)
    return path


def setup_var_directory(c):
    c.run('mkdir -p %s' % normpath(join(c.config.projectpath, 'var', 'log')))
    c.run('mkdir -p %s' % normpath(join(c.config.projectpath, 'var', 'run')))
    c.run('mkdir -p %s' % normpath(join(c.config.projectpath, 'var', 'db')))
    c.run('mkdir -p %s' % normpath(join(c.config.projectpath, 'var', 'share')))
    c.run('mkdir -p %s' % get_upload_dir(c))


@task()
def app_setup(c, backup=False):
    """Setup the environment so the application can run"""
    if not c.config.package_install:
        with venv(c):
            c.run('pip install -e ./')
    setup_var_directory(c)
    if not exists(c, c.config._internal.ini_file):
        create_local_ini(c)
    if not backup:
        with venv(c):
            c.run('assembl-ini-files populate %s' % (c.config._internal.ini_file))
    with c.cd(c.config.projectpath):
        has_pre_commit = c.run('cat requirements.txt|grep pre-commit', warn=True)
        if has_pre_commit and not exists(c, join(
                c.config.projectpath, '.git/hooks/pre-commit')):
            with venv(c):
                c.run("pre-commit install")


@task()
def create_local_ini(c):
    """Replace the local.ini file with one composed from the current .rc file"""
    local_ini_path = os.path.join(c.config.projectpath, c.config._internal.ini_file)
    if exists(local_ini_path):
        c.run('cp %s %s.bak' % (local_ini_path, local_ini_path))
    with venv(c):
        c.run("python2 -m assembl.scripts.ini_files compose -o %s %s" % (
            c.config._internal.ini_file, c.config.rcfile))


delete_foreign_tasks(locals())
