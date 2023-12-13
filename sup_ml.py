# -*- coding: utf-8 -*-
"""
	Работа с Merlion
	на 07.07.16 поменялось

	~~~~~~~~~~~~~~~~~~~~~~
	by Cept (cept@simm.ru)
	~~~~~~~~~~~~~~~~~~~~~~
"""
import settings
from Ex import *


api = 'ML'
url = 'https://api.merlion.com/re/mlservice2?wsdl'
usr = 'TC0039408|IGOR'
pas = 'Fantom15'
deliveryMethod = 'С/В'



def api_connect():
	global proxy_settings

	session = Session()
	session.auth = HTTPBasicAuth(usr,pas)
	# Соединяемся
	wdsl = Client(url, transport = Transport(session=session))
	return wdsl


def run_command_c(cat='All'):
	global database
	#print(param)
	#print(u"Синхронизация каталога Merlion...")
	wdsl = api_connect()
	catalog = wdsl.service.getCatalog(cat)
	if len(catalog) == 0:
		print(u"Данные не получены, увы выходим")
		return

	# Работа с БД
	db_connect('BCenter')
	cur = settings.database['BCenter'].cursor()
	sql = 'delete from sup_cat where api=\'' + api + '\''
	cur.execute(sql)
	sql = 'insert into sup_cat (api,id,idn,owner,name) values (\'ML\',\'Order\',\'ML\',null,\'Merlion\')'
	cur.execute(sql)
	counter = 0


	# Пробегаем
	for item in catalog:
		counter += 1
		sql = 'insert into sup_cat (api,id,idn,owner,name) values (?,?,?,?,?)'
		cur.execute(sql, ['ML', item.ID, item.ID, item.ID_PARENT, item.Description])
		cur.close()

		# Сообщение
		print(item.ID, item.ID, item.ID_PARENT, item.Description)
		# Запись изменений
	settings.database['BCenter'].commit()

		# Получилось!
	print(u"... Синхронизировано: %d ветвей каталога" % counter)
	time.sleep(2)
	return 0



def run_command_s(args):

	# Соединяемся с API
	wdsl = api_connect()

	# Читаем метод и дату отгрузки
	shipment_date = wdsl.service.getShipmentDates('', deliveryMethod)
	if len(shipment_date) > 0: LastDateSh = shipment_date[-1].Date
	print(u"Метод отгрузки: %s, Дата отгрузки: %s" % (deliveryMethod, LastDateSh))
	# Текущий курс
	kurs = wdsl.service.getCurrencyRate(LastDateSh)
	kurs = [k for k in kurs if k.Code == 'USD']
	Rate = kurs[0].ExchangeRate


	# Получаем каталог и выборку цен складов
	info = wdsl.service.getItems(args.supcat, '', deliveryMethod, '', '')
	avail = wdsl.service.getItemsAvail(args.supcat, deliveryMethod, LastDateSh,0,'')

	#if len(info) == 0:
	#	print(u"Данные не получены, увы выходим")
	#	return

	#print(args)
	# Работа с БД
	cur = settings.database['BCenter'].cursor()
	sql = 'update sup_st set status=-5 where ((cat=\'' + args.supcat + '\')and((\''+args.search+'\' = \'\'))or(\''+args.search+'\' = brand ))'  #статус -5 всем с учетом бренда!
	cur.execute(sql)

	# Берем первый элемент
	#info = info[0]

	counter = 0
	counter_real =0
	# Пробегаем
	for item in info:
		 #Если указан бренд, то должен содержаться в элементе
		if args.search != '' and args.search != False:
			if item.Brand not in args.search:
				continue

		if item.Name == None: #на всякий який
			continue
		# Будем обрабатывать
		counter += 1

		data = {
			'ID'	: item.No,
			'PN'	: item.Vendor_part,
			'BRAND'	: item.Brand,
			'CAT'	: args.supcat,
			'NAME'	: item.Name,
			'API'	: api,
			'BC_CAT': args.bccat
		}

		# WARANTY=[30,183,...1095] или .Waranty*30
		data['WARRANTY'] = { 1: 30, 6: 183, 12: 365, 24: 730, 36: 1095 }.get(item.Warranty, item.Warranty * 30)
		p = [a for a in avail if a.No == data['ID']]

		if (p is None):
			print(u"Нет данных по складу.Вероятно не полное обновление у вендора по %s" % data['NAME'])
			continue

		data['USD'] = p[0].PriceClient
		data['RUR'] = data['USD'] * Rate
		data['SCLAD'] = str(p[0].AvailableClient)
		data['TRANSIT'] = str(p[0].AvailableExpected)
		data['DATE_TRANSIT'] = p[0].DateExpectedNext

		# обрабатываем только в наличии не складе или транзите ликвидные по цене
		if ((data['SCLAD'] == '0') and (data['TRANSIT'] == '0')):
			continue

		counter_real += 1
		post(data, cur)

	# Уже есть запись в SUP_SET?
	cur.execute('select id from sup_set where id=?', [args.supcat])
	sup_set_id = cur.fetchone()
	if (sup_set_id != None):
		sql = 'update sup_set set bc_cat=?, cou_all=?, cou_sclad=?, updates=\'NOW\' where id=?'
		cur.execute(sql, [args.bccat, counter, counter_real, args.supcat])
	else:
		sql = 'insert into sup_set(id,bc_cat,cou_all,cou_sclad,updates) values(?,?,?,?,\'NOW\')'
		cur.execute(sql, [args.supcat, args.bccat, counter, counter_real])
	cur.close()


	# Запись изменений
	settings.database['BCenter'].commit()

	# Получилось!
	print(u"... Синхронизировано:  %d наименований из %d активных позиций поставщика" % (counter_real,counter))
	time.sleep(2)
	return 0
