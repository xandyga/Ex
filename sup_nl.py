# -*- coding: utf-8 -*-
"""
	Работа с Netlab
	~~~~~~~~~~~~~~~~~~~~~~
	by Cept (cept@simm.ru)
	~~~~~~~~~~~~~~~~~~~~~~
"""
import settings
from Ex import *
import urllib.parse
import json
import xml.etree.cElementTree as ET

api = 'NL'
usr = 'simmru'
pas = 'fciSiL3'
storedToken = None

def get_token():
	global storedToken
	if storedToken: return storedToken
	wdsl = Client('http://services.netlab.ru/AuthenticationService?wsdl')
	response = wdsl.service.authenticate(usr, pas)
	storedToken = response.data.token
	print('Токен:', storedToken)
	return storedToken


def catalog_name():
	return urllib.parse.quote('В наличии')

def GetParentIdn(parentId):
	if (parentId == '0'):
		return 'NL'
	for item in sorted_list:
		if (item['id'] == parentId):
			return str(item['idn'])


def run_command_c(cat='All'):
	global sorted_list
	#print(u"Синхронизация каталога netlab...")

	# Получение токена
	token = get_token()

	# Получение данных
	data = ''
	url = 'http://services.netlab.ru/rest/catalogsZip/' + catalog_name() + '.json?oauth_token=' + token
	urlConnection = urllib.request.urlopen(url)
	data = urlConnection.read()
	urlConnection.close()
	if len(data) == 0:
		print(u"Данные не получены, увы выходим")
		return

	jsonData = json.loads(data[6:])['catalogResponse']['data']['category']
	sorted_list = sorted(jsonData, key=lambda k: (int(k['parentId']), int(k["id"])))
	db_connect('BCenter')
	cur = settings.database['BCenter'].cursor()

	sql = 'delete from SUP_CAT where api=\'' + api + '\''
	cur.execute(sql)
	counter = 0
	sql = 'insert into sup_cat (api,id,idn,owner,name) values (\'NL\',\'0\',\'NL\',null,\'Netlab\')'
	cur.execute(sql)
	sql = 'insert into SUP_CAT (api,id,idn,owner,name) values (?,?,?,?,?)'
	for item in jsonData:
		name = item['name'][0:80]
		counter += 1
	i = 0
	old = sorted_list[1]['parentId']
	for item in sorted_list:
		if (item['parentId'] == old): i += 1
		else: i = 1
		item['idn'] = f'{i:02X}'
		item['idn'] = GetParentIdn(item['parentId']) + item['idn']
		old = item['parentId']
		cur.execute(sql, [api, item['id'], item['idn'], item['parentId'], item['name'][0:80]])
		counter += 1
		print(item)
	cur.close()
	settings.database['BCenter'].commit()
	print(u"... Синхронизировано: %d ветвей каталога" % counter)
	time.sleep(2)
	return 0



def run_command_s(args):
	# Получение токена
	#token = get_token()

	# Получение данных
	da = ''
	url = 'http://services.netlab.ru/rest/catalogsZip/' + catalog_name() + '/' + args.supcat + '.json?oauth_token=' + get_token()
	urlConnection = urllib.request.urlopen(url)
	da = urlConnection.read()
	urlConnection.close()
	info = json.loads(da[6:])['categoryResponse']['data']['goods']

	if len(da) == 0:
		print(u"Данные не получены, увы выходим")
		return 1

	url = 'http://services.netlab.ru/rest/catalogsZip/info.json?oauth_token='+ get_token()
	urlConnection = urllib.request.urlopen(url)
	rawData = urlConnection.read()
	urlConnection.close()

	# Parse response
	jsonData = json.loads(rawData[6:])
	try:
		# Get rate and output it
		rate = jsonData['entityListResponse']['data']['items'][0]['properties']['usdRateNonCash']
		print('Курс Нетлаба', rate)
	except:
		# Catch error, if any
		rate = None
		print('Fail -  Плохой курс: выходим')
		return 2

	db_connect('BCenter')
	counter = 0
	counter_real = 0
	#print(args)

	cur = settings.database['BCenter'].cursor()
	sql = 'update sup_st set status=-5 where ((cat=\'' + args.supcat + '\')and((\''+args.search+'\' = \'\'))or(\''+args.search+'\' = brand ))'  #статус -5 всем с учетом бренда!
	cur.execute(sql)

	for item in info:
		counter += 1
		item = item['properties']
		#print(item)

		data = {
				'ID': item['id'],
				'PN': item['PN'],
				'BRAND': item['производитель'],
				'CAT': args.supcat,
				'NAME': item['название'],
				'BC_CAT': args.bccat,
				'TRANSIT': int(item.get('количество в транзите')),
				'DATE_TRANSIT': item.get('дата транзита'),
				'API': api
		}

		Lo = item['количество на Лобненской']
		Ku = item['количество на Курской']
		Ka = item['количество на Калужской']
		data['SCLAD'] = int(Lo+Ku+Ka)
		data['WARRANTY'] = {'1 год': 365, '2 года': 730, '3 года': 1095}.get(item['гарантия'], None)
		data['USD'] = item['цена по категории F']
		data['RUR'] = data['USD']*rate
		print(data)

		counter_real += 1
		post(data,cur)

	# в CAT меняем на IDN из каталога в BCentre
	cur.execute('select idn from sup_cat where id=?', [args.supcat])
	sup_cat_idn = cur.fetchonemap()
	if (sup_cat_idn != None): cat = sup_cat_idn.get('IDN')

	# Уже есть запись в SUP_SET?
	cur.execute('select id from sup_set where id=?', [cat])
	sup_set_id = cur.fetchone()
	if (sup_set_id != None):
		sql = 'update sup_set set bc_cat=?, cou_all=?, cou_sclad=?, updates=\'NOW\' where id=?'
		cur.execute(sql, [args.bccat, counter, counter_real, cat])
	else:
		sql = 'insert into sup_set(id,bc_cat,cou_all,cou_sclad,updates) values(?,?,?,?,\'NOW\')'
		cur.execute(sql, [cat, args.bccat, counter, counter_real])
	cur.close()

	# Запись изменений
	settings.database['BCenter'].commit()

	# Получилось!
	print(u"... Синхронизировано:  %d наименований из %d активных позиций поставщика" % (counter_real, counter))
	time.sleep(2)
	return 0
