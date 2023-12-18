import argparse
import sys
import configparser
import fdb
import importlib
import settings
import os
import time
from requests import Session
from requests.auth import HTTPBasicAuth  # or HTTPDigestAuth, or OAuth1, etc.
from zeep.client import Client
from zeep.transports import Transport

def main():
	#global args
	parser = argparse.ArgumentParser()
	parser.add_argument("-c", "--getcategory", action="count", help="only get category [-c ML]", default=0)
	parser.add_argument("-up", "--update", action="count", help="update all pair from sup_set [-up]", default=0)
	parser.add_argument("-s", "--getproduct", action="count", help="get product, default", default=0)

	if ((len(sys.argv[1:]) > 0) and (sys.argv[1] != '-up')):
		parser.add_argument("supplier", choices=['ML', 'ml', 'LA', 'la', 'NL', 'nl'], help="required")
		if ((len(sys.argv[1:])>0)and(sys.argv[1] != '-c')):
			parser.add_argument("supcat", help="the Supplier category, only [-s]")
			parser.add_argument("bccat", type=int, help="the BCenter category, only [-s]")
			parser.add_argument("-search", help="the keyword filter product, only [-s]", default='')
	parser.add_argument("-db", help="the DB name", default='Localhost:b2022')
	parser.add_argument("-login", help="the login DB", default='IG')
	parser.add_argument("-password", help="the password DB", default='bujhf')
	parser.add_argument("-role", help="the role DB", default='SOFT_USER')
	settings.args = parser.parse_args()

	settings.args.db = get_config('Default', 'DBName', settings.args.db)
	print(sys.argv)
	print(settings.args)
	#exit()
	#db_connect('INfo')
	db_connect('BCenter')
	if settings.args.update > 0:
		try:
			up()
			print('Полное обновление пар успешно завершено')
			return 0
		except Exception as error:
			print('Полное обновление пар завершено с ошибкой')
			time.sleep(5)
			return 200
	try:
		# Импортируем библиотеку поставщика
		if ((settings.args.getcategory > 0) or (settings.args.getproduct > 0)):
			supplier_lib = importlib.import_module('sup_%s' % settings.args.supplier.lower())
	except Exception as error:
		print('ошибка импорта модуля',error)
		time.sleep(5)
		return 200

	if settings.args.getcategory>0:
		print("Синхронизация {} каталога с BCenter".format(settings.args.supplier))
		supplier_lib.run_command_c('All')
		return 0
	if settings.args.getproduct>0:
		print("Синхронизация {} продуктов каталога {} c каталогом BCenter {}".format(settings.args.supplier, settings.args.supcat, settings.args.bccat))
		#print(settings.args)
		supplier_lib.run_command_s(settings.args)
		return 0


def up():
	print('Полное обновление пар ...')
	ml = importlib.import_module('sup_ml')
	la = importlib.import_module('sup_la')
	nl = importlib.import_module('sup_nl')
	cur = settings.database['BCenter'].cursor()
	sql = 'select sup_set.id, sup_set.bc_cat, sup_set.cr,(select sup_cat.id from sup_cat where sup_cat.idn=sup_set.id) idi from sup_set order by id'
	cur.execute(sql)
	rows = cur.fetchall()
	for row in rows:
		print(f'row = {row}')
		settings.args.supcat = row[3]
		settings.args.bccat = row[1]
		settings.args.cr = row[2]
		settings.args.search =''
		print((row[0][:2]).lower())
		match (row[0][:2]).lower():
			case "ml":
				ml.run_command_s(settings.args)
			case "la":
				la.run_command_s(settings.args)
			case "nl":
				nl.run_command_s(settings.args)

	print('Внесение обновлений в BCenter')
	cur = settings.database['BCenter'].cursor()
	sql = 'select sum(cou) co from sup2st_pairs'
	cur.execute(sql)
	countup = cur.fetchone()
	cur.close()
	if (countup != None): print(u"... Обновлено в BCenter:  %d строк прайса" % countup)
	else: print('Обновлений в BCenter строк прайса нет')
	settings.database['BCenter'].commit()




def db_connect(dbname):
	# Уже соединились
	#print(settings.args)
	if dbname in settings.database: return [settings.args.db, settings.args.login]

	settings.database[dbname] = fdb.connect(
		dsn				= settings.args.db,
		user			= settings.args.login,
		password		= settings.args.password,
		charset			= 'WIN1251',
		sql_dialect		= 3,
		role			= settings.args.role,
		fb_library_name = os.getcwd()+'\\fbclient.dll')


	return [settings.args.db, settings.args.login]




def get_config(section, param, default = ''):
	config = configparser.ConfigParser()
	try:
		config.read('bcenter.ini')
		return config.get(section, param)
	except:
		return default

def post(data,cur):
	# Постим. Статусы строк импорта:
	#-5 - устанавливаем всем перед состоявшемся импортом импортом когда len(info) > 0
	#-4 - существующая строка и активная без изменений и с наличием на складе или в транзите
	#-3 - существующая строка и активная с изменением и с наличием на складе или в транзите
	#-2 - новая строка с наличием на складе или в транзите
	#-1 - изменилось название - затерется если изменится цена или количество на -3
	#-------- ниже работает процедура Firebird по фиксации в наш прайс:
	# 0 - обработано в наш прайс содержит целое количество в транзите
	# 1 и выше - обработано в наш прайс содержит целое количество на складе

	# Уже есть запись в таблице?
	cur.execute('select name,pn,usd,sclad,transit from sup_st where api=? and id=?', [data['API'], data['ID']])
	import_st_name = cur.fetchone()
	already_exists = import_st_name != None
	cur.close()

	# Да
	if already_exists:
		change_usd = float(import_st_name[2]) != float(data['USD'])
		change_sclad = str(import_st_name[3]) != str(data['SCLAD'])
		change_transit = str(import_st_name[4]) != str(data['TRANSIT'])
		change_all = change_usd or change_sclad or change_transit
		# Может имя поменялось?
		if ((import_st_name[0] != data['NAME']) or (import_st_name[1] != data['PN'])):
			print(u"AHTUNG-1:изменилось название или партномер: %s" % data['NAME'])
			sql = 'update sup_st set name=?, pn=?, status=-1, updates=\'NOW\' where id=?'  # status = -1
			cur.execute(sql, [data['NAME'], data['PN'], data['ID']])
			cur.close()

		# Обновляем поля если изменились status -3 инача -4 (без изменений)
		if (change_all):
			sql = 'update sup_st set cat=?, bc_cat=?, usd=?, rur=?, brand=?,warranty=?, sclad=?, transit=?, date_transit=?, pn=?, updates=?,status=?  where id=?'
			cur.execute(sql, [data['CAT'], data['BC_CAT'], data['USD'], data['RUR'], data['BRAND'], data['WARRANTY'], data['SCLAD'],
							  data['TRANSIT'], data['DATE_TRANSIT'], data['PN'], 'NOW', -3, data['ID']])
			print(u"SINK(upd-3): %s, $%.2f(%.2f), s %s(%s), t %s(%s)" % (
			data['NAME'], data['USD'], import_st_name[2], data['SCLAD'], import_st_name[3], data['TRANSIT'],
			import_st_name[4]))
		else:
			sql = 'update sup_st set cat=?, bc_cat=?, brand=?,warranty=?, date_transit=?, updates=?, status=?  where id=?'
			cur.execute(sql, [data['CAT'], data['BC_CAT'], data['BRAND'], data['WARRANTY'], data['DATE_TRANSIT'], 'NOW', -4, data['ID']])
	# output(u"SINK(upd-4 <изменений цены и кол нет>): %s" % item.Name)
	else:
		sql = 'insert into sup_st (id,pn,name,cat,bc_cat,usd,rur,brand,warranty,sclad,transit,date_transit,api,status) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
		cur.execute(sql, [data['ID'], data['PN'], data['NAME'], data['CAT'], data['BC_CAT'], data['USD'], data['RUR'],
						  data['BRAND'],
						  data['WARRANTY'], data['SCLAD'], data['TRANSIT'], data['DATE_TRANSIT'], data['API'], -2])
		print(u"SINK(ins-2): %s" % data['NAME'])

	cur.close()



if __name__ == '__main__':
	sys.exit(main())
