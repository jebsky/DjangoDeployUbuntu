from fabric.contrib.files import append, exists, sed
from fabric.api import env, local, run, sudo
import random
import datetime



'''
To Deploy on a fresh ubuntu install run
fab spinup:host=root@<server_ip>
then
fab deploy:host=YOUR_USERNAME@<server_ip>

To update Production site uncomment variables under production (and comment out test site) below and run
cd /deploy_tools && fab deploy:host=PRODUCTION_IP

To update test site uncomment variables under test (and comment out production site) below and run
cd /deploy_tools && fab deploy:host=TEST_IP
'''


# Production Site #
HOST = 'PRODUCTION_IP' #official www.project.com
BRANCH = 'live'
env.password = 'YOUR_DEPLOYMENT_PASSWORD'


# Test Site #
# HOST = 'TEST_IP' #test.project.com
# BRANCH = 'test'
# env.password = 'YOUR_TEST_PASSWORD'


USERNAME = 'YOUR_USERNAME'
PROJECT_NAME = 'PROJECT_NAME'
PASSWORD = 'YOUR_DEPLOYMENT_PASSWORD'


LOCAL_REPO = 'DELOPMENT_DIRECTORY'
#ex: '/home/YOUR_USERNAME/dev/project.com/'

BACKUP_HOST = 'BACKUP_SERVER_IP'
BACKUP_REPO = '/home/%s/backups/project.com/repo' % (USERNAME)
BACKUP_URL = 'ssh://%s@%s%s' % (USERNAME, BACKUP_HOST, BACKUP_REPO)
REMOTE_REPO = '/home/%s/sites/%s.repo.git' % (USERNAME, HOST)
REPO_URL = 'ssh://%s@%s%s' % (USERNAME, HOST, REMOTE_REPO)
SITE_FOLDER = '/home/%s/sites/%s' % (USERNAME, HOST)



# must be root
def spinup():
    run('apt-get update --assume-yes')
    run('apt-get install nginx git mercurial python3-pip yui-compressor --assume-yes')
    run('pip3 install virtualenv')
    run('adduser %s --gecos "YOUR NAME,YOUR_OFFICE_NUM,YOUR_PHONE,YOUR_OTHER_PHONE" --disabled-password' % (USERNAME))
    run('echo %s:%s | chpasswd' % (USERNAME, PASSWORD))
    run('mkdir -p /home/%s/.ssh' % (USERNAME))
    run('adduser %s sudo' % (USERNAME))
    run('chown %s /home/%s/.ssh' % (USERNAME, USERNAME))
    local('ssh-copy-id -i ~/.ssh/id_rsa.pub %s' % (HOST))


def config():
    """
    This sets up nginx(the http server) and gunicorn(the wsgi module)
    """
    sudo('sed "s/SITENAME/%s/g" /home/%s/sites/%s/deploy_tools/nginx.template.conf | tee /etc/nginx/sites-available/%s' % (HOST, HOST, USERNAME, HOST))
    sudo('sed "s/USERNAME/%s/g" /home/%s/sites/%s/deploy_tools/nginx.template.conf | tee /etc/nginx/sites-available/%s' % (USERNAME, HOST, USERNAME, HOST))
    sudo('ln -s ../sites-available/%s /etc/nginx/sites-enabled/%s' % (HOST, HOST))
    sudo('sed "s/SITENAME/%s/g" /home/%s/sites/%s/deploy_tools/gunicorn-upstart.template.conf | tee /etc/init/gunicorn-%s.conf' % (HOST, HOST, USERNAME, HOST))
    sudo('sed "s/USERNAME/%s/g" /home/%s/sites/%s/deploy_tools/gunicorn-upstart.template.conf | tee /etc/init/gunicorn-%s.conf' % (USERNAME, HOST, USERNAME, HOST))
    sudo('sed "s/PROJECT_NAME/%s/g" /home/%s/sites/%s/deploy_tools/gunicorn-upstart.template.conf | tee /etc/init/gunicorn-%s.conf' % (PROJECT_NAME, USERNAME, HOST, HOST))
    sudo('rm /etc/nginx/sites-enabled/default')
    sudo('service nginx reload')
    sudo('initctl reload-configuration')
    sudo('start gunicorn-%s' % (HOST))
    run("ssh-keygen -t dsa -P '' -f ~/.ssh/id_rsa")
    run('ssh-copy-id -i ~/.ssh/id_rsa.pub %s' % (BACKUP_HOST))



def deploy():
    if exists(REMOTE_REPO):
        '''
        If a repo is set up on the server already(normal case)
        '''
        _backup_database()
        _push_local_repo()
        _pull_changes()
        _minify()
        _update_settings()
        _update_virtualenv()
        _update_static_files()
        _update_database()
        update_live()
    else:
        '''
        if a repo is not set up. Should only be on first deploy
        '''
        _git_config()
        _create_git_repo()
        _add_remote_repo()
        _push_local_repo()
        _clone_repo_source()
        _update_settings()
        _update_virtualenv()
        _update_static_files()
        _minify()
        config()
        get_database()
        _update_database()
        update_live()

def _git_config():
    run('git config --global user.email "YOUR_EMAIL"')
    run('git config --global user.name "YOUR_NAME"')


def _create_git_repo():
    run('git init %s --bare --shared' % REMOTE_REPO)


def _add_remote_repo():
    local("cd %s && git remote add %s %s" % (LOCAL_REPO, BRANCH, REPO_URL))


def _push_local_repo():
    local('cd %s && git push %s master' % (LOCAL_REPO, BRANCH))
    local('cd %s && git push backup master' % (LOCAL_REPO))


def _pull_changes():
    sudo('cd %s && git stash' % (SITE_FOLDER))
    sudo('cd %s && git pull %s' % (SITE_FOLDER, REMOTE_REPO))


def _clone_repo_source():
    run('git clone %s %s' % (REMOTE_REPO, SITE_FOLDER))


def _minify():
    """
    uses the shrink app to minifiy .css and .js according to mini.ini
    https://bitbucket.org/jeronimoalbi/shrink
    """
    mini_path = SITE_FOLDER + '/deploy_tools/mini.ini'
    sudo('cd %s/templates/nav && rm headlinks.html' % (SITE_FOLDER))
    sudo('cd %s/deploy_tools && cp headlinks.html %s/templates/nav' % (SITE_FOLDER, SITE_FOLDER,))
    sed(mini_path, "<HOST>", HOST)
    sudo('cd %s/deploy_tools && shrink -f mini.ini all -d -v -y global' % (SITE_FOLDER))


def _update_settings():
    settings_path = SITE_FOLDER + '/forte/settings.py'
    if BRANCH == 'live':
        sed(settings_path, "DEBUG = True", "DEBUG = False")
        sed(settings_path, 'from forte.settings_testsite', '# ')
        sudo('cd %s/deploy_tools && cp test-only-links.html %s/templates/nav' % (SITE_FOLDER, SITE_FOLDER,))
    sed(settings_path, 'DOMAIN = "localhost"', 'DOMAIN = "%s"' % (HOST,))
    sed(settings_path, "STATICFILES_DIRS", "STATIC_ROOT")
    # GETs rid of the comma
    sed(settings_path, ",##!##", "#!#")
    # switches from test to deployment email schema
    sed(settings_path, "#X ", "")
    sed(settings_path, "EMAIL_BACKEND=", "#X EMAIL_BACKEND = ")


def _update_virtualenv():
    virtualenv_folder = SITE_FOLDER + '/virtualenv'
    if not exists(virtualenv_folder + '/bin/pip'):
        run('virtualenv --python=python3 %s' % (virtualenv_folder,))
        run('hg clone https://jeffrey_balinsky@bitbucket.org/jeffrey_balinsky/shrink')
        sudo('pip3 install -e /home/%s/shrink' %s (USERNAME))
    run('%s/bin/pip install -r %s/requirements.txt' % (
        virtualenv_folder, SITE_FOLDER
    ))
    run('%s/bin/pip install --upgrade pip' % (virtualenv_folder))
    run('%s/bin/pip install gunicorn' % (virtualenv_folder))


def _update_static_files():
    sudo('cd %s && virtualenv/bin/python3 manage.py collectstatic --noinput' % ( SITE_FOLDER, ))


def get_database():
    run('scp %s:`ssh %s ls -1td /home/%s/backups/project.com/db/live/\* | head -1` %s/db.sqlite3' %
        (BACKUP_HOST, BACKUP_HOST, USERNAME SITE_FOLDER))

def _update_database():
    sudo('cd %s && virtualenv/bin/python3 manage.py migrate --noinput' % ( SITE_FOLDER, ))


def update_live():
    sudo('initctl reload-configuration')
    sudo('restart gunicorn-%s' % (HOST))


def _backup_database():
    run('scp %s/db.sqlite3 %s@BACKUP_SERVER_IP:/home/%s/backups/project.com/db/%s/db.%s.sqlite3' %
        (SITE_FOLDER, USERNAME, USERNAME, BRANCH, datetime.datetime.now().isoformat()))