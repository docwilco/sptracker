
echo Setting environment
export PYTHONPATH=$PWD:$PWD/stracker/externals

echo Cleaning up old version
cd stracker
rm -f stracker_linux_x86.tgz
rm -rf dist
rm -rf build

echo Setting up python environment

# Setting up the env and installing/upgrading takes forever,
# so only do it once a day, or if it hasn't been done yet
if find env/linux/lastcheck -mtime 0 > /dev/null
then
    . env/linux/bin/activate
else
    virtualenv env/linux
    . env/linux/bin/activate
    echo Installing/upgrading packages
    pip install --upgrade bottle
    pip install --upgrade cherrypy
    pip install --upgrade psycopg2
    pip install --upgrade python-dateutil
    pip install --upgrade wsgi-request-logger
    pip install --upgrade simplejson
    pip install --upgrade pyinstaller
    # This is so incredibly slow, and no way to auto-upgrade
    if ! pip show apsw
    then
        pip install https://github.com/rogerbinns/apsw/releases/download/3.35.4-r1/apsw-3.35.4-r1.zip \
            --global-option=fetch --global-option=--version --global-option=3.35.4 --global-option=--all \
            --global-option=build --global-option=--enable-all-extensions
    fi
    touch env/linux/lastcheck
fi

pyinstaller --clean -y -s --exclude-module http_templates --hidden-import cherrypy.wsgiserver.wsgiserver3 --hidden-import psycopg2 stracker.py

mv dist/stracker dist/stracker_linux_x86
tar cvzf stracker_linux_x86.tgz -C dist stracker_linux_x86
rm -rf dist
rm -rf build

exit 0
