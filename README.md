# DjangoDeployUbuntu

### Full Stack
- Droplet on DigitalOcean.com running Ubuntu 14.04 LTS
- Nginx Webserver
- Gunicorn WSGI module

### Fabric for deploy script
- requires python 2.X on dev computer

Uses yuicompressor for minification
Shrink to configure yuicompressor 
https://bitbucket.org/jeronimoalbi/shrink

#### Config Files
- The fabric script Spinup script modifies and moves the config files
- Nginx config lives in /etc/nginx/sites-enabled
- Gunicorn script lives in /etc/init
