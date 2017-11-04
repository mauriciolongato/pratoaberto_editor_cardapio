import requests
import datetime
import collections
import db_functions
import itertools


# api = 'https://pratoaberto.tk/api'
# api = 'http://pratoaberto.sme.prefeitura.sp.gov.br:8100'
api = 'https://pratoaberto.sme.prefeitura.sp.gov.br/api'

def dia_semana(dia):
    diasemana = ('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom')
    return diasemana[dia]


def replace_cardapio(cardapio):
    config_editor = db_functions.select_all()

    for de_para in config_editor:
        cardapio = [de_para[4] if x == de_para[3] else x for x in cardapio]

    cardapio = [x for x in cardapio if x != '']
    return cardapio


def data_semana_format(text):
    date = datetime.datetime.strptime(text, "%Y%m%d").isocalendar()
    return str(date[0])+"-"+str(date[1])


def get_cardapios_iguais():
    url = api + '/cardapios?status=PENDENTE&status=SALVO'
    r = requests.get(url)
    refeicoes = r.json()

    # Formatar as chaves
    semanas = {}
    for refeicao in refeicoes:
        _key_semana = data_semana_format(refeicao['data'])
        if _key_semana in semanas.keys():
            semanas[_key_semana].append(refeicao['data'])
        else:
            semanas[_key_semana] = [refeicao['data']]

    ingredientes = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])

        for alimentos in refeicao['cardapio_original'].keys():
            _key = frozenset(replace_cardapio(refeicao['cardapio_original'][alimentos]))
            ingredientes[_key].append([agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana])

    return ingredientes


def open_csv():
    path = './tmp'
    file = 'Cardapios Novos.csv'

    cardapio = []
    with open(path+'/'+file, 'r', encoding='utf-8') as f:

        # REFEIÇÕES
        text = f.read().replace(' (Sopa e Fruta)', '')
        text = text.replace('(Papa Principal e Papa de Fruta)', '')
        text = text.replace('(Sopa e Fruta)', '')
        text = text.replace('(Papa de Fruta)', '')
        text = text.replace('(Papa Principal e Papa de Fruta/Suco)', '')
        text = text.replace('(Fórmula e Papa de Fruta)', '')
        text = text.replace('(Fruta)', '')
        text = text.replace('R1 - REFEICAO 1 da Tarde', 'R1 - REFEICAO 1')
        text = text.replace('A - ALMOCO (R1 - REFEICAO 1 e Fruta/Suco)', 'R1 - REFEICAO 1')
        text = text.replace('(R1 - REFEICAO 1 e Fruta/Suco)', '')

        # IDADES
        text = text.replace('7 meses', 'D - 7 MESES')
        text = text.replace('0 a 5 meses', 'D - 0 A 5 MESES')
        text = text.replace('6 meses', 'D - 6 MESES')
        text = text.replace('2 - 6 anos', 'I - 2 A 6 ANOS')
        text = text.replace('8 a 11 meses', 'E - 8 A 11 MESES')
        text = text.replace('1 ano - 1 ano e 11 meses', 'X - 1A -1A E 11MES')
        text = text.replace('TODAS', 'Z - UNIDADES SEM FAIXA')
        text = text.replace('\n', '')
        cardapio = text.split('|')

    cardapio_aux = []
    for nrow in range(0, len(cardapio), 5):
        if len(cardapio[nrow:nrow+5]) == 5:
            x = cardapio[nrow:nrow + 5]
            ingredientes = ', '.join([y.strip() for y in x[3].split(',') if y.strip() != ''])
            dsemana = datetime.datetime.strptime(x[4].strip(), '%d-%m-%Y').weekday()
            row = [x[0], x[1].strip(), x[2].strip(), ingredientes, dia_semana(dsemana)]
            cardapio_aux.append(row)

    cardapio_aux.sort()
    cardapio = list(cardapio_aux for cardapio_aux, _ in itertools.groupby(cardapio_aux))
    db_functions.truncate_receitas_terceirizadas()

    objects = []
    for row in cardapio:
        if row[3] != '':
            objects.append(['TERCEIRIZADA', row[0], 'EDITAL 78/2016', row[4], row[1], row[2], row[3]])
            # db_functions.add_cardapio('TERCEIRIZADA', row[0], 'EDITA1', row[4], row[1], row[2], row[3])

    db_functions.add_bulk_cardapio(objects)


def get_escola(cod_eol):
    url = api + '/escola/{}'.format(cod_eol)
    r = requests.get(url)
    escola = r.json()

    return escola


def get_escolas():
    url = api + '/escolas?completo'
    r = requests.get(url)
    escolas = r.json()

    return escolas


def post_cardapio():
    api = 'https://pratoaberto.sme.prefeitura.sp.gov.br/api'
    headers = {'Content-type': 'application/json'}
    jdata = '[{"_id":{"$oid":"59fa66a454e6253592047a8b"}, "idade": "Z - UNIDADES SEM FAIXA", "data": "20171101", "status":"PENDENTE"}]'
    r = requests.post(api + '/editor/cardapios', data=jdata, headers=headers)


if __name__ == '__main__':
    # db_functions.truncate_receitas_terceirizadas()
    # open_csv()
    import json

    post_cardapio()
    escolas = get_escolas()
    # cod_eol = [91065, 19235, 90891]
    # escolas_f = [x for x in escolas if x['_id'] in cod_eol]
    escolas_eol = set([x['_id'] for x in escolas])
    print(len(escolas_eol))
    print(escolas_eol)
    for cod_eol in ['19235']:
        print(json.dumps(get_escola(str(cod_eol))['historico']))
        print('\n')