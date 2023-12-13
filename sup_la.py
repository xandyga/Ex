# -*- coding: utf-8 -*-
"""
	Работа с Treolan/Lanit
	~~~~~~~~~~~~~~~~~~~~~~
	by Cept (cept@simm.ru)
	~~~~~~~~~~~~~~~~~~~~~~
"""
import settings
from Ex import *
import xml.etree.cElementTree as ET

api = 'LA'
url = 'https://api.treolan.ru/ws/service.asmx?WSDL'
usr = 'simm_ki'
pas = 'f35l5xg5'


def api_connect():
	session = Session()
	session.auth = HTTPBasicAuth(usr,pas)
	wdsl = Client(
		url,
		transport=Transport(session=session)
	)
	return wdsl

def recursive(el,idn,i):
    global cou
    for child in el:
        i += 1
        id = idn+f'{i:02X}'
        cou += 1
        print(child.tag, child.attrib, id)
        sqlr = 'insert into sup_cat (api,id,idn,owner,name) values (\'LA\',\''+child.attrib["id"] +'\',\''+id+'\',\''+child.attrib["parentid"]+'\',\''+child.attrib["name"]+'\')'
        cur = settings.database['BCenter'].cursor()
        cur.execute(sqlr)
        recursive(child, id,0)



def run_command_c(cat='All'):
	global cou

	#print(u"Синхронизация каталога Triolan...")
	wdsl = api_connect()
	info = wdsl.service
	GC = info.GetCategories(usr,pas)
	#db_connect('BCenter')
	root = ET.fromstring(GC.Result)
	cou = 1
	#print(root.tag, root.attrib, 'LA')

	cur = settings.database['BCenter'].cursor()
	sql = 'delete from sup_cat where api=\'' + api + '\''
	cur.execute(sql)
	sql = 'insert into sup_cat (api,id,idn,owner,name) values (\'LA\',\'' + root.attrib[
		"id"] + '\',\'LA\',null,\'Lanit\')'
	cur.execute(sql)

	recursive(root, 'LA', 0)
	print('... Синхронизировано: ',cou,' ветвей каталога')
	settings.database['BCenter'].commit()
	time.sleep(2)
	return 0



def run_command_s(args):
	wdsl = api_connect()
	info = wdsl.service

	# Получаем курс Треолана
	cource = wdsl.service.GetExchangeRate(
		login=usr,
		password=pas
	)

	Rate = float(cource['Result'].replace(',','.'))
	if Rate == '0' : Rate = 1

	# Получаем каталог
	query = wdsl.service.GenCatalogV2(
		login=usr,
		password=pas,
		category=args.supcat,
		vendorid=0, 
		keywords=args.search,
		criterion=1,
		inArticul=0,
		inName=1, 
		inMark=0,
		showNc=1,
		freeNom=1
		)
	# doc: https://documenter.getpostman.com/view/18719071/UVR7KoEW
	if len(query) == 0:
		print(u"Данные не получены, увы выходим")
		return
	counter = 0
	counter_real = 0
	root = ET.fromstring(query.Result)

	#print(args)

	cur = settings.database['BCenter'].cursor()
	sql = 'update sup_st set status=-5 where ((cat=\'' + args.supcat + '\')and((\''+args.search+'\' = \'\'))or(\''+args.search+'\' = brand ))'  #статус -5 всем с учетом бренда!
	cur.execute(sql)

	for item in root.iter('position'):
		counter += 1

		data = {
			'ID'			: item.get('prid'),
			'PN'			: item.get('articul'),
			'BRAND'			: item.get('vendor'),
			'CAT'			: args.supcat,
			'NAME'			: item.get('name'),
			'BC_CAT'		: args.bccat,
			'SCLAD'			: item.get('freenom'),
			'TRANSIT'		: item.get('freeptrans'),
			'DATE_TRANSIT'	: item.get('ntdate'),
			'API' 			: api
			}

		if item.get('dprice') is None : continue

		if item.get('currency') == 'RUB' :
			data['RUR'] = float(item.get('dprice'))
			data['USD'] = round(data['RUR']/Rate,2)
		else :
			data['USD'] = float(item.get('dprice'))
			data['RUR'] = round(data['USD']*Rate,2)

		data['WARRANTY'] = {
			'1 месяц': 30, '6 месяцев': 183,
			'1 год': 365, '2 года': 730, '3 года': 1095
			}.get(item.get('gp'), 183)

		# обрабатываем только в наличии не складе или транзите ликвидные по цене
		if ((data['SCLAD'] == '0')and(data['TRANSIT'] == '0')) :
			continue

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
		cur.execute(sql, [args.bccat, counter, counter_real, args.supcat])
	else:
		sql = 'insert into sup_set(id,bc_cat,cou_all,cou_sclad,updates) values(?,?,?,?,\'NOW\')'
		cur.execute(sql, [cat, args.bccat, counter, counter_real])
	cur.close()

	# Запись изменений
	settings.database['BCenter'].commit()

	# Получилось!
	print(u"... Синхронизировано:  %d наименований из %d активных позиций поставщика" % (counter_real, counter))
	time.sleep(3)
	return 0

def run_command_p(cat='W10307'):
	# TODO
	return False

	global database

	# Сообщение
	output(u"Синхронизация картинок по каталогу Треолана")
	if cat != '': output(u", по категории %s" % cat)
	outputln()

	# Соединяемся с БД Info
	try:
		# Запоминаем данные соединения
		(info_dsn, info_user) = db_connect('Info')
		(bc_dsn, bc_user) = db_connect('BCenter')
		# Выводим дату и с кем соединились
		now = datetime.datetime.strftime(datetime.datetime.now(), '%H:%M:%S')
		outputln("%s Connect1: %s %s" % (now, info_dsn, info_user))
		outputln("%s Connect2: %s %s" % (now, bc_dsn, bc_user))
	except Exception as ex:
		# Произошла ошибка, выходим
		output("Error: Not Connected") # to Pictures and BCenter',
		outputln("(%s)" % ex)
		return False

	# Если успешно, то сообщение
	output(u"Connected to Pictures fo Category %s" % cat)

	# Выполняем запрос
	cur = {
		'bcenter': database['BCenter'].cursor(),
		'info': database['Info'].cursor()
		}
	
	if cat != '':
		cur['bcenter'].execute("select * from import_st where cat starting with ?", [cat])
	else:	cur['bcenter'].execute("select first 100 * from import_st") # danger, very big => first 1000

	outputln(u"Records ")

	items = cur['bcenter'].fetchallmap()
	cur['bcenter'].close()

	# Соединяемся к API
	wdsl = api_connect()
	outputln(u"Соединяемся к Treolan...")

	# Для загрузки файлов, при условии прокси
	if proxy_settings:
		proxy_handler 	= urllib.request.ProxyHandler(proxy_settings)
		opener			= urllib.request.build_opener(proxy_handler)
		urllib.request.install_opener(opener)


	# if 'debug': return [wdsl, items]

	alltraffic = 0

	# Бегаем по выбранному списку из import_st
	for item in items:                
		allpics = wdsl.service.getItemsImages('',item.get('id'))

		if len(allpics)==0: continue

		# С какого номера идет отсчет?
		fn = allpics[0].FileName
		k = fn.find('_')
		# У первого файла минимальный k
		if (k>0) and (len(fn)>k+2):
			# ...._v12  => k = 12
			if fn[k+1] == 'v': mink = int(fn[k+2:k+4])
			# ...._d12  => k = 42
			elif fn[k+1] == 'd': mink = int(fn[k+2:k+4]) + 30
			# ...._p12  => k = 72
			elif fn[k+1] == 'p': mink = int(fn[k+2:k+4]) + 60
			# иначе	=> k = -1
			else: mink = 0

		for pic in allpics:

			# Только big
			if (pic.SizeType!='b'): continue

			# Имя файла
			fn = pic.FileName

			# Хитро-хитро
			k = fn.find('_')

			# Должно быть по формату
			if (k>0) and (len(fn)>k+2):
				# ...._v12  => k = 12
				if fn[k+1] == 'v': k = int(fn[k+2:k+4])
				# ...._d12  => k = 42
				elif fn[k+1] == 'd': k = int(fn[k+2:k+4]) + 30
				# ...._p12  => k = 72
				elif fn[k+1] == 'p': k = int(fn[k+2:k+4]) + 60
				# иначе	=> k = -1
				else: k = 0
			else:
				continue

			# Минимум приводим к нулю
			k -= mink

			# Какой то неправильный номер
			if k < 0: continue

			# Много картинок не надо
			if k > 2: continue #k = 0

			# делаем
			output('.') #зачем точку?

			# ищем в базе ИНФО, проверяем на размер, скачиваем если нужно
			# есть ли в базе картинка  в 2х базах
			cur['info'].execute("select * from TBL_INFO_PICS where ((code=?)and(idx=?))",
				["T73U%d" % item.get('st_id'), k])

			cur['bcenter'].execute("select * from prop_val_str where ((st_id=?)and(prop_id4=?))",
				[item.get('st_id'), 1000000+k])	# константа для картинки

			tbl_info_pic = cur['info'].fetchall()
			prop_val_str = cur['bcenter'].fetchall()
			if len(tbl_info_pic) == 0 and len(prop_val_str) == 0: # ни там ни там нет
				#пишем в базу картину если там их нет
				if True:
					#	'[%s]' % item.Size, item.ViewType
					outputln()
					outputln(u"%s bigPic %s %s %s [%s] %s" % 
						(item.get('cat'), k, pic.No,
						pic.FileName, pic.Size, pic.ViewType))

					alltraffic += pic.Size

					#качаем картинку
					picture_f = urllib.request.urlopen("http://img.Treolan.ru/items/%s" % fn)
					picture = picture_f.read()

					#! INFO: insert into tbl_info_pics values (T73U+item.get('st_id'), k, picture, null, null)
					cur['info'].execute(
						'insert into tbl_info_pics values (?, ?, ?, null, null)',
						["T73U%d" % item.get('st_id'), k, picture])
					#! BCENTER: insert into prop_val_str (st_id,prop_id4,val) values (item.get('st_id'), 1000000+k, T73U+item.get('st_id'))
					cur['bcenter'].execute(
						'insert into prop_val_str (st_id,prop_id4,val) values (?, ?, ?)',
						[item.get('st_id'), 1000000+k, "T73U%d" % item.get('st_id')])	# константа для картинки
					#!
					# Запись изменений
					db_commit('Info')
					db_commit('BCenter')
				#except:
				#	outputln(u"<Error Load from Treolan or Save Pic to base>")

			cur['info'].close()
			cur['bcenter'].close()

	# Получилось!
	outputln(u"Успешное завершение")
	outputln(u"Всего скачено изображений: %d байт" % alltraffic)

	return 0
