# Импорт в BCenter Treolan, Merlion,Netlab

## Развертывание проекта:
* pip freeze > requirements.txt
* py -m pip install --upgrade pip
* pip install -r requirements.txt

## XXX:
* ig@everest:/opt/smsoft/Ex$ source /opt/smsoft/exenv/bin/activate
* python -m pip install --upgrade pip
* pip install -r requirements.txt
* путь до fbclient не указывать - находит в системе


## **py ex.py -h**

  
  options:
*   -h, --help          show this help message and exit
*   -c, --getcategory   only get category [-c ML]
*   -up, --update       update all pair from sup_set [-up]
*   -s, --getproduct    get product, default
*   -db DB              the DB name
*   -login LOGIN        the login DB
*   -password PASSWORD  the password DB
*   -role ROLE          the role DB

**Пример экспорта (-s) из Нетлаба из категории нелаба в категорию BCenter**

#### py ex.py NL -s 164456 1415

#### поставщик:
1. NL - Netlab
2. ML   Merlion
3. LA   Lanit

#### действие:

1. -s      Синхронизация 
2. -r      Импорт цен 
3. -p      Импорт картинок 
4. -a      Импорт аттрибутов
5. 

## Создание EXE
* pip install -U pyinstaller
* pyinstaller --onefile --hidden-import=sup_ml --hidden-import=sup_nl --hidden-import=sup_la Ex.py
