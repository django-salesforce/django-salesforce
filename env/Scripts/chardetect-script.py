#!C:\Users\c266139\Documents\web_services\integration_engine\django-salesforce\env\Scripts\python.exe
# EASY-INSTALL-ENTRY-SCRIPT: 'chardet==4.0.0','console_scripts','chardetect'
__requires__ = 'chardet==4.0.0'
import re
import sys
from pkg_resources import load_entry_point

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(
        load_entry_point('chardet==4.0.0', 'console_scripts', 'chardetect')()
    )
