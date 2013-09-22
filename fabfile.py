import os

current_dir = os.path.abspath(os.path.dirname(__file__))
repo_dir = os.path.join(current_dir, 'repos')
virtualenv_dir = os.path.join(current_dir, '.env')

def bootstrap_venv():
    print "No virtualenv found in .env, installing."
    virtualenv_version = '1.10.1'
    virtualenv_filename = 'virtualenv-%s' % virtualenv_version
    virtualenv_tgz = virtualenv_filename + '.tar.gz'
    virtualenv_download = 'https://pypi.python.org/packages/source/v/virtualenv/{0}'.format(virtualenv_tgz)
    if not os.path.isfile(os.path.join(current_dir, virtualenv_tgz)):
        run('curl %s -o %s' % (virtualenv_download, virtualenv_tgz))
    run('tar xzvf %s' % virtualenv_tgz)
    run('python %s/virtualenv.py --no-site-packages .env' % virtualenv_filename)
    run('rm -rf %s' % virtualenv_filename)


def install_fabric():
    pip_binary = os.path.join(virtualenv_dir, 'bin', 'pip')
    if not os.path.isfile(pip_binary):
        bootstrap_venv()
    run('%s install fabric' % pip_binary)


def install_fabtools():
    pip_binary = os.path.join(virtualenv_dir, 'bin', 'pip')
    if not os.path.isfile(pip_binary):
        bootstrap_venv()
    run('%s install fabtools' % pip_binary)

if os.path.exists(virtualenv_dir):
    # also check os.environ to see if his path is virtualenv_dir and dont run
    # this
    execfile(os.path.join(virtualenv_dir, 'bin', 'activate_this.py'))

try:
    from fabric.api import task, env
    from fabric import *
    env.hosts = ['127.0.0.1']

except ImportError:
    print "No fabric, installing."
    def run(cmd, echo=True):
        import subprocess
        output = subprocess.check_output(cmd, shell=True)
        if echo:
            print(output)
    install_fabric()

try:
    import fabtools
    from fabtools import require
except:
    print "No fabtools, installing."
    def run(cmd, echo=True):
        import subprocess
        output = subprocess.check_output(cmd, shell=True)
        if echo:
            print(output)
    install_fabtools()


#if not os.path.exists(virtualenv_dir):
#    bootstrap_venv()
# we now have fabtools, kool

#@task

#env.settings = None

def load_config():
    print 'load_config'

    try:
        import kaptan
    except ImportError:
        with fabtools.python.virtualenv(virtualenv_dir):
            print require.python.package('kaptan')

    config = kaptan.Kaptan(handler='yaml')
    config.import_config('pillar/study_repos.sls')
    print config.export()
    return config

def printrepos():
    config = load_config()

    for language, repotype in config.get('study_repos').iteritems():
        print "created %s repos for %s" % (repotype, language)
        for project_name, project_repo in config.get('study_repos')[language]:
            print "%s %s %s" % (project_name, project_repo, language)

        #print language,repotype


def saltlater():

    import salt.client
    client = salt.client.LocalClient()
    ret = client.cmd('*', 'cmd.run', ['whoami'])

    print ret

#hey()
