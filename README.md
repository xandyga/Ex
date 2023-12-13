Развертывание простого проекта:
В исходниках:
pip freeze > requirements.txt
в целевом компе в новой dir:
py -m pip install --upgrade pip
pip install -r requirements.txt

# simm-ex
Импорт Treolan, Merlion,Netlab
-----------------------------
**Системные требования:**
   * Python 3
**Для помощи:**
  py ex.py -h
  usage: ex.py [-h] [-c] [-up] [-s] [-db DB] [-login LOGIN] [-password PASSWORD] [-role ROLE]
  options:
  -h, --help          show this help message and exit
  -c, --getcategory   only get category [-c ML]
  -up, --update       update all pair from sup_set [-up]
  -s, --getproduct    get product, default
  -db DB              the DB name
  -login LOGIN        the login DB
  -password PASSWORD  the password DB
  -role ROLE          the role DB
**Пример экспорта (-s) из Нетлаба из категории нелаба в категорию BCenter**
py ex.py NL -s 164456 1415
поставщик:
NL - Netlab
ML   Merlion
LA   Lanit
действие:
-s      Синхронизация 
-r      Импорт цен 
-p      Импорт картинок 
-a      Импорт аттрибутов
