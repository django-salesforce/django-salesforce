#!c:\users\c266139\documents\web_services\integration_engine\django-salesforce\env\scripts\python.exe
# EASY-INSTALL-ENTRY-SCRIPT: 'lilly-aws-auth==2.3.3','console_scripts','lilly-aws-auth'
__requires__ = 'lilly-aws-auth==2.3.3'
import re
import sys
from pkg_resources import load_entry_point

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(
        load_entry_point('lilly-aws-auth==2.3.3', 'console_scripts', 'lilly-aws-auth')()
    )
