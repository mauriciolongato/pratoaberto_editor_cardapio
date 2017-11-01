import collections
import datetime
import itertools
import json
import os
import requests
from flask import Flask, flash, redirect, render_template, request, url_for, make_response
from werkzeug.utils import secure_filename
import cardapios_terceirizadas as terceirizadaslist
import cardapio_xml_para_dict as xmldict
import db_setup
import db_functions

app = Flask(__name__)

#ip_teste_vitor = 'http://192.168.0.195:8000'
#ip_homolog = 'https://pratoaberto.tk/api'
#api = 'https://pratoaberto.tk/api'
api = 'http://pratoaberto.sme.prefeitura.sp.gov.br:8100'


@app.route("/", methods=["GET", "POST"])
def backlog():
    if request.method == "GET":
        pendentes = get_pendencias()
        #semanas = sorted(set([x[8] for x in pendentes]), reverse=True)
        semanas = sorted(set([str(x[4]) + ' - ' + str(x[5]) for x in pendentes]), reverse=True)
        return render_template("pendencias_publicacao.html",
                               pendentes=pendentes,
                               semanas=semanas)

    else:
        pendentes = get_pendencias()
        #semanas = sorted(set([x[8] for x in pendentes]), reverse=True)
        semanas = sorted(set([str(x[4]) + ' - ' + str(x[5]) for x in pendentes]), reverse=True)
        return render_template("pendencias_publicacao.html",
                               pendentes=pendentes,
                               semanas=semanas)


@app.route("/pendencias_deletadas", methods=["GET", "POST"])
def deletados():
    if request.method == "GET":
        deletados = get_deletados()
        semanas = sorted(set([str(x[4]) + ' - ' + str(x[5]) for x in deletados]), reverse=True)
        return render_template("pendencias_deletadas.html",
                               pendentes=deletados,
                               semanas=semanas)


@app.route("/pendencias_publicadas", methods=["GET", "POST"])
def publicados():
    if request.method == "GET":
        publicados = get_publicados()
        semanas = sorted(set([str(x[4]) + ' - ' + str(x[5]) for x in publicados]), reverse=True)
        return render_template("pendencias_publicadas.html",
                               pendentes=publicados,
                               semanas=semanas)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)

    file = request.files['file']

    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        try:
            cardapio_dict = xmldict.create(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cardapios_preview = []
            json_list = []
            responses = {}
            for tipo_atendimento, v1 in cardapio_dict.items():
                for tipo_unidade, v2 in v1.items():
                    for agrupamento, v3 in v2.items():
                        for idade, v4 in v3.items():
                            for data, v5 in v4.items():
                                query = {
                                    'tipo_atendimento': tipo_atendimento,
                                    'tipo_unidade': tipo_unidade,
                                    'agrupamento': agrupamento,
                                    'idade': idade,
                                }
                                _key = frozenset(query.items())
                                if _key not in responses:
                                    args = (api,
                                            data,
                                            '&'.join(['%s=%s' % item for item in query.items()]),
                                            '&'.join(
                                                ['status=%s' % item for item in ['PUBLICADO', 'SALVO', 'PENDENTE']]))
                                    responses[_key] = requests.get('{}/editor/cardapios/{}?{}&{}'.format(*args)).json()

                                cardapio = query
                                cardapio['data'] = data
                                if responses[_key]:
                                    cardapio.update({
                                        'cardapio': {'DUPLICADO': ['DUPLICADO']},
                                        'status': 'DUPLICADO'
                                    })
                                else:
                                    cardapio.update({
                                        'cardapio_original': {k: list(map(str.strip, v.split(','))) for (k, v) in
                                                              v5.items()},
                                        'cardapio': {k: list(map(str.strip, v.split(','))) for (k, v) in v5.items()},
                                        'status': 'PENDENTE'
                                    })
                                    json_list.append(cardapio)

                                cardapios_preview.append(cardapio)

            json_dump = json.dumps(json_list)
        except:
            cardapios_preview, json_dump = [], {}
        return render_template("preview_json.html", filename=filename, cardapios_preview=cardapios_preview,
                               json_dump=json_dump)


@app.route('/cria_terceirizada', methods=['GET'])
def cria_terceirizada():
    if request.method == "GET":
        quebras = db_functions.select_quebras_terceirizadas()
        editais = set([x[1] for x in quebras])
        tipo_unidade = set([x[0] for x in quebras])
        idade = set([x[2] for x in quebras])
        refeicao = set([x[3] for x in quebras])

        return render_template("cria_terceirizadas.html",
                               editais=editais,
                               tipo_unidade=tipo_unidade,
                               idades=idade,
                               refeicoes=refeicao)


@app.route('/atualiza_cardapio', methods=['POST'])
def atualiza_cardapio():
    headers = {'Content-type': 'application/json'}
    data = request.form.get('json_dump', request.data)
    r = requests.post(api + '/editor/cardapios', data=data, headers=headers)

    if request.form:
        return (redirect(url_for('backlog')))
    else:
        return ('', 200)


comments = []
@app.route("/calendario", methods=["GET"])
def calendario():
    args = request.args
    depara = db_functions.select_all()
    depara = [x[3:5] for x in depara if x[1] == 'TEMPEROS' and x[2] == 'INGREDIENTES']

    # Monta json - Semana da requisicao
    jdata = get_cardapio(args)

    # Obtem data semana anterior
    args_semana_anterior = args.copy()
    args_semana_anterior['status'] = 'SALVO'
    args_semana_anterior.add('status', 'PUBLICADO')

    delta_dias = datetime.timedelta(days=7)
    data_final_semana_anterior = datetime.datetime.strptime(str(args['data_final']), '%Y%m%d') - delta_dias
    data_inicial_semana_anterior = datetime.datetime.strptime(str(args['data_inicial']), '%Y%m%d') - delta_dias
    args_semana_anterior['data_final'] = datetime.datetime.strftime(data_final_semana_anterior, '%Y%m%d')
    args_semana_anterior['data_inicial'] = datetime.datetime.strftime(data_inicial_semana_anterior, '%Y%m%d')
    # Monta json - Semana anterior a da requisicao
    jdata_anterior = get_cardapio(args_semana_anterior)

    jdata_aux = []
    for cardapio_atual in jdata:
        dia = datetime.datetime.strptime(str(cardapio_atual['data']), '%Y%m%d').weekday()
        cardapio_atual['dia_semana'] = dia_semana(dia)
        jdata_aux.append(cardapio_atual)

    jdata_anterior_aux = []
    for cardapio_anterior in jdata_anterior:
        dia = datetime.datetime.strptime(str(cardapio_anterior['data']), '%Y%m%d').weekday()
        cardapio_anterior['dia_semana'] = dia_semana(dia)
        jdata_anterior_aux.append(cardapio_anterior)

    jdata = jdata_aux
    jdata_anterior = jdata_anterior_aux

    # Liga o cardapio atual com o da semana anterior
    dias_da_semana = set([x['dia_semana'] for x in list(jdata + jdata_anterior)])

    cardapios = []
    for dia in dias_da_semana:
        cardapio_atual = filtro_dicionarios(jdata, 'dia_semana', dia)
        cardapio_anterior = filtro_dicionarios(jdata_anterior, 'dia_semana', dia)

        if cardapio_atual and cardapio_anterior:
            cardapio_atual['cardapio_semana_anterior'] = cardapio_anterior['cardapio']
            cardapios.append(cardapio_atual)

        else:
            if cardapio_atual:
                cardapio_atual['cardapio_semana_anterior'] = []
                cardapios.append(cardapio_atual)

            elif cardapio_anterior:
                cardapio_atual['cardapio_semana_anterior'] = []
                cardapios.append(cardapio_atual)
    if args['tipo_atendimento'] == 'TERCEIRIZADA':
        historicos_cardapios = get_cardapios_terceirizadas(args['tipo_atendimento'],
                                                           args['tipo_unidade'],
                                                           args['agrupamento'],
                                                           args['idade'])

        return render_template("editor_terceirizadas.html",
                               url=api + '/cardapios',
                               cardapios=cardapios,
                               tipo_atendimento=args['tipo_atendimento'],
                               tipo_unidade=args['tipo_unidade'],
                               idade=args['idade'],
                               agrupamento=args['agrupamento'],
                               historicos_cardapios=historicos_cardapios)

    else:
        return render_template("editor_direto_misto_conveniada.html",
                               url=api + '/cardapios',
                               cardapios=jdata,
                               tipo_atendimento=args['tipo_atendimento'],
                               tipo_unidade=args['tipo_unidade'],
                               idade=args['idade'],
                               agrupamento=args['agrupamento'],
                               depara=depara)


@app.route("/visualizador_cardapio", methods=["GET"])
def visualizador():
    args = request.args
    # Monta json
    jdata = get_cardapio(args)
    jdata = [d for d in jdata if d['tipo_atendimento'] in args['tipo_atendimento']]
    jdata = [d for d in jdata if d['idade'] in args['idade']]
    jdata = [d for d in jdata if d['tipo_unidade'] in args['tipo_unidade']]
    jdata = [d for d in jdata if str(d['agrupamento']) in args['agrupamento']]

    cardapios = []
    for cardapio in jdata:
        dia = datetime.datetime.strptime(str(cardapio['data']), '%Y%m%d').weekday()
        cardapio['dia_semana'] = dia_semana(dia)
        cardapios.append(cardapio)

    return render_template("visualizador_cardapio.html",
                           url=api + '/cardapios',
                           cardapios=jdata,
                           tipo_atendimento=args['tipo_atendimento'],
                           tipo_unidade=args['tipo_unidade'],
                           idade=args['idade'],
                           agrupamento=args['agrupamento'])


@app.route("/calendario_editor_grupo", methods=["POST"])
def calendario_grupo_cardapio():
    data = request.form.get('json_dump', request.data)

    charset = ['"', '[', ']']
    for char in charset:
        data = data.replace(char, '')
    data = data.split(',')

    # Datas compativeis (Todas as quebras precisam ter as mesmas datas no conjunto)
    lista_data_inicial = []
    lista_data_final = []
    lista_args = []
    for url in data:
        args = dict([tuple(x.split('=')) for x in url.split('?')[1].split('&')])
        lista_data_inicial.append(args['data_inicial'])
        lista_data_final.append(args['data_final'])
        lista_args.append(args)

    if (len(set(lista_data_inicial)) > 1) or (len(set(lista_data_final)) > 1):
        flash('A cópia de cardápios só é permitida para quabras com mesmo periodo')
        return redirect(url_for('backlog'))

    depara = db_functions.select_all()
    depara = [x[3:5] for x in depara if x[1] == 'TEMPEROS' and x[2] == 'INGREDIENTES']
    cardapios = []
    for url in data:
        args = dict([tuple(x.split('=')) for x in url.split('?')[1].split('&')])
        jdata = get_cardapio(args)

        # Obtem data semana anterior
        args_semana_anterior = args.copy()
        args_semana_anterior['status'] = 'SALVO&status=PUBLICADO'

        delta_dias = datetime.timedelta(days=7)
        data_final_semana_anterior = datetime.datetime.strptime(str(args['data_final']), '%Y%m%d') - delta_dias
        data_inicial_semana_anterior = datetime.datetime.strptime(str(args['data_inicial']), '%Y%m%d') - delta_dias
        args_semana_anterior['data_final'] = datetime.datetime.strftime(data_final_semana_anterior, '%Y%m%d')
        args_semana_anterior['data_inicial'] = datetime.datetime.strftime(data_inicial_semana_anterior, '%Y%m%d')
        jdata_anterior = get_cardapio(args_semana_anterior)

        jdata_aux = []
        for cardapio_atual in jdata:
            dia = datetime.datetime.strptime(str(cardapio_atual['data']), '%Y%m%d').weekday()
            cardapio_atual['dia_semana'] = dia_semana(dia)
            jdata_aux.append(cardapio_atual)

        jdata_anterior_aux = []
        for cardapio_anterior in jdata_anterior:
            dia = datetime.datetime.strptime(str(cardapio_anterior['data']), '%Y%m%d').weekday()
            cardapio_anterior['dia_semana'] = dia_semana(dia)
            jdata_anterior_aux.append(cardapio_anterior)

        jdata = jdata_aux
        jdata_anterior = jdata_anterior_aux

        # Liga o cardapio atual com o da semana anterior
        dias_da_semana = set([x['dia_semana'] for x in list(jdata + jdata_anterior)])

        for dia in dias_da_semana:
            cardapio_atual = filtro_dicionarios(jdata, 'dia_semana', dia)
            cardapio_anterior = filtro_dicionarios(jdata_anterior, 'dia_semana', dia)

            if cardapio_atual and cardapio_anterior:
                cardapio_atual['cardapio_semana_anterior'] = cardapio_anterior['cardapio']
                cardapios.append(cardapio_atual)

            else:
                if cardapio_atual:
                    cardapio_atual['cardapio_semana_anterior'] = []
                    cardapios.append(cardapio_atual)

                elif cardapio_anterior:
                    cardapio_atual['cardapio_semana_anterior'] = []
                    cardapios.append(cardapio_atual)

    if lista_args[0]['tipo_atendimento'] == 'TERCEIRIZADA':
        historicos_cardapios = get_cardapios_terceirizadas(lista_args[0]['tipo_atendimento'],
                                                           lista_args[0]['tipo_unidade'],
                                                           lista_args[0]['agrupamento'],
                                                           lista_args[0]['idade'])

        return render_template("editor_grupo_terceirizadas.html",
                               url=api + '/cardapios',
                               cardapios=cardapios,
                               args=lista_args,
                               historicos_cardapios=historicos_cardapios)

    else:
        return render_template("editor_grupo_direto_misto_conveniada.html",
                               url=api + '/cardapios',
                               cardapios=cardapios,
                               args=lista_args,
                               depara=depara)


@app.route("/configuracoes_gerais", methods=['GET', 'POST'])
def config():
    if request.method == "GET":
        config_editor = db_functions.select_all()
        return render_template("configurações.html", config=config_editor)


@app.route('/atualiza_configuracoes', methods=['POST'])
def atualiza_configuracoes():
    headers = {'Content-type': 'application/json'}
    data = request.form.get('json_dump', request.data)

    db_functions.truncate_replacements()
    for row in json.loads(data):
        db_functions.add_replacements(row[0], row[1], row[2], row[3])

    if request.form:
        return (redirect(url_for('config')))
    else:
        return ('', 200)


@app.route("/configuracoes_cardapio", methods=['GET', 'POST'])
def config_cardapio():
    if request.method == "GET":
        config_editor = db_functions.select_all_receitas_terceirizadas()
        return render_template("configurações_receitas.html", config=config_editor)


@app.route('/atualiza_receitas', methods=['POST'])
def atualiza_config_cardapio():
    data = request.form.get('json_dump', request.data)

    db_functions.truncate_receitas_terceirizadas()
    db_functions.add_bulk_cardapio(json.loads(data))

    if request.form:
        return (redirect(url_for('config_cardapio')))
    else:
        return ('', 200)


@app.route('/escolas', methods=['GET'])
def escolas():
    if request.method == "GET":
        escolas = get_escolas()
        return render_template("configurações_escolas.html", escolas=escolas)


@app.route('/atualiza_escolas', methods=['POST'])
def atualiza_escolas():
    data = request.form.get('json_dump', request.data)
    data = json.loads(data)

    erro_falta_data = False
    erro_data = False

    for escola_mod in data:

        escola_atual = get_escola(escola_mod['_id'])
        escola_atual['_id'] = int(escola_mod['_id'])
        if 'edital' not in escola_atual:
            escola_atual['edital'] = ''

        if 'data_inicio_vigencia' not in escola_atual:
            escola_atual['data_inicio_vigencia'] = ''

        if escola_atual['nome'] != escola_mod['nome']:
            escola_atual['nome'] = escola_mod['nome']

        if escola_atual['endereco'] != escola_mod['endereco']:
            escola_atual['endereco'] = escola_mod['endereco']

        if escola_atual['bairro'] != escola_mod['bairro']:
            escola_atual['bairro'] = escola_mod['bairro']

        try:
            escola_mod['lat'] = float(escola_mod['lat'])
            escola_mod['lon'] = float(escola_mod['lon'])
        except:
            pass

        if escola_atual['lat'] != escola_mod['lat']:
            escola_atual['lat'] = escola_mod['lat']

        if escola_atual['lon'] != escola_mod['lon']:
            escola_atual['lon'] = escola_mod['lon']

        try:
            escola_mod['agrupamento'] = int(escola_mod['agrupamento'])
        except:
            pass

        flag_unidade = (escola_atual['tipo_unidade'] != escola_mod['tipo_unidade'])
        flag_atendimento = (escola_atual['tipo_atendimento'] != escola_mod['tipo_atendimento'])
        flag_agrupamento = (escola_atual['agrupamento'] != escola_mod['agrupamento'])
        flag_edital = (escola_atual['edital'] != escola_mod['edital'])

        if flag_unidade or flag_atendimento or flag_agrupamento or flag_edital:
            flag_historico = True
        else:
            flag_historico = False

        if flag_historico == True:
            if escola_mod['data_inicio_vigencia'] == '':
                erro_falta_data = True

            else:
                erro_falta_data = False
                try:
                    erro_data = False
                    data = datetime.datetime.strptime(escola_mod['data_inicio_vigencia'], '%Y%m%d')
                except:
                    erro_data = True

            if 'historico' in escola_atual:
                escola_atual['historico'].append({'data_inicio_vigencia': escola_mod['data_inicio_vigencia'],
                                                  'tipo_unidade': escola_atual['tipo_unidade'],
                                                  'tipo_atendimento': escola_atual['tipo_atendimento'],
                                                  'agupamento': escola_atual['agrupamento'],
                                                  'edital': escola_atual['edital']
                                                  })
                escola_atual['tipo_unidade'] = escola_mod['tipo_unidade']
                escola_atual['tipo_atendimento'] = escola_mod['tipo_atendimento']
                escola_atual['agrupamento'] = escola_mod['agrupamento']
                escola_atual['edital'] = escola_mod['edital']
                escola_atual['data_inicio_vigencia'] = escola_mod['data_inicio_vigencia']

            else:
                escola_atual['historico'] = []
                escola_atual['historico'].append({'data_inicio_vigencia': escola_mod['data_inicio_vigencia'],
                                                  'tipo_unidade': escola_atual['tipo_unidade'],
                                                  'tipo_atendimento': escola_atual['tipo_atendimento'],
                                                  'agupamento': escola_atual['agrupamento'],
                                                  'edital': escola_atual['edital']
                                                  })
                escola_atual['tipo_unidade'] = escola_mod['tipo_unidade']
                escola_atual['tipo_atendimento'] = escola_mod['tipo_atendimento']
                escola_atual['agrupamento'] = escola_mod['agrupamento']
                escola_atual['edital'] = escola_mod['edital']
                escola_atual['data_inicio_vigencia'] = escola_mod['data_inicio_vigencia']


        if (erro_data == False) and (erro_falta_data == False):
            headers = {'Content-type': 'application/json'}
            r = requests.post(api + '/editor/escola/{}'.format(str(escola_atual['_id'])),
                              data=json.dumps(escola_atual),
                              headers=headers)
        else:
            pass

    if request.form:
        if erro_falta_data:
            flash('Para essas modificações, é necessario definir a data de inicio da vigência das modificações! No campo "data" coloque a informação no formato aaaammdd')
            return (redirect(url_for('escolas')))
        elif erro_data:
            flash('Formato da data inválido. No campo "data" coloque a informação no formato aaaammdd')
            return (redirect(url_for('escolas')))
        else:
            return (redirect(url_for('escolas')))
    else:
        return ('', 200)


@app.route("/download_publicacao", methods=["GET", "POST"])
def publicacao():
    if request.method == "GET":
        return render_template("download_publicações.html", data_inicio_fim='disabled')

    else:
        data_inicial = request.form.get('data-inicial', request.data)
        data_final = request.form.get('data-final', request.data)
        data_inicial = datetime.datetime.strptime(data_inicial, '%d/%m/%Y').strftime('%Y%m%d')
        data_final = datetime.datetime.strptime(data_final, '%d/%m/%Y').strftime('%Y%m%d')
        filtro = request.form.get('filtro', request.data)

        if filtro == 'STATUS':
            return render_template("download_publicações.html",
                                   data_inicio_fim=str(data_inicial + '-' + data_final),
                                   filtro_selected=filtro)

        else:
            cardapio_aux = []
            for cardapio in get_grupo_publicacoes(filtro):
                if (data_inicial <= cardapio[4]) or (data_inicial <= cardapio[5]):
                    if (cardapio[4] <= data_final) or (cardapio[5] <= data_final):
                        url = api + '/cardapios?' + '&' + cardapio[7]
                        r = requests.get(url)
                        refeicoes = r.json()

                        for refeicoes_dia in refeicoes:
                            _keys = ['tipo_atendimento', 'tipo_unidade', 'agrupamento', 'idade', 'data', 'status']
                            refeicao_dia_aux = [refeicoes_dia[_key] for _key in _keys]
                            for refeicao in refeicoes_dia['cardapio'].keys():
                                cardapio_aux.append(
                                    refeicao_dia_aux + [refeicao] + [', '.join(refeicoes_dia['cardapio'][refeicao])])

            return render_template("download_publicações.html", publicados=cardapio_aux,
                                   data_inicio_fim=str(data_inicial + '-' + data_final),
                                   filtro_selected=filtro)


@app.route('/download_csv', methods=['POST'])
def download_csv():
    data_inicio_fim_str = request.form.get('datas', request.data)
    data_inicial = data_inicio_fim_str.split('-')[0]
    data_final = data_inicio_fim_str.split('-')[1]
    filtro = request.form.get('filtro_selected', request.data)

    if filtro == 'STATUS':
        return render_template("download_publicações.html",
                               data_inicio_fim=str(data_inicial + '-' + data_final))
    else:
        cardapio_aux = []
        for cardapio in get_grupo_publicacoes(filtro):
            if (data_inicial <= cardapio[4]) or (data_inicial <= cardapio[5]):
                if (cardapio[4] <= data_final) or (cardapio[5] <= data_final):
                    url = api + '/cardapios?' + '&' + cardapio[7]
                    r = requests.get(url)
                    refeicoes = r.json()

                    for refeicoes_dia in refeicoes:
                        _keys = ['tipo_atendimento', 'tipo_unidade', 'agrupamento', 'idade', 'data', 'status']
                        refeicao_dia_aux = [refeicoes_dia[_key] for _key in _keys]
                        for refeicao in refeicoes_dia['cardapio'].keys():
                            cardapio_aux.append(
                                refeicao_dia_aux + [refeicao] + [', '.join(refeicoes_dia['cardapio'][refeicao])])

        header = [['ATENDIMENTO', 'UNIDADE', 'AGRUPAMENTO', 'IDADE', 'DATA', 'STATUS', 'REFEICÃO', 'CARDÁPIO']]
        cardapio_aux = header + cardapio_aux
        csvlist = '\n'.join(['"' + str('";"'.join(row)) + '"' for row in cardapio_aux])
        output = make_response(csvlist)
        output.headers["Content-Disposition"] = "attachment; filename=agrupamento_publicações" + str(data_inicio_fim_str) + ".csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8'"

        if request.form:
            return output
        else:
            return ('', 200)


# FUNÇÕES AUXILIARES
def data_semana_format(text):
    date = datetime.datetime.strptime(text, "%Y%m%d").isocalendar()
    return str(date[0]) + "-" + str(date[1])


def get_cardapio(args):
    url = api + '/editor/cardapios?' + '&'.join(['%s=%s' % item for item in args.items()])
    r = requests.get(url)
    refeicoes = r.json()

    return refeicoes


def get_pendencias():
    url = api + '/editor/cardapios?status=PENDENTE&status=SALVO'
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

    pendentes = []
    _ids = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])
        _key = frozenset([agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana])
        _ids[_key].append(refeicao['_id']['$oid'])
        data_inicial = min(semanas[_key_semana])
        data_final = max(semanas[_key_semana])

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        pendentes.append(
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana])

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        pendente.append(','.join(_ids[_key]))

    return pendentes


def get_deletados():
    url = api + '/editor/cardapios?status=DELETADO'
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

    pendentes = []
    _ids = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])
        _key = frozenset([agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana])
        _ids[_key].append(refeicao['_id']['$oid'])
        data_inicial = min(semanas[_key_semana])
        data_final = max(semanas[_key_semana])

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        pendentes.append(
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana])

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        pendente.append(','.join(_ids[_key]))

    return pendentes


def get_publicados():
    url = api + '/editor/cardapios?status=PUBLICADO'
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

    pendentes = []
    _ids = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])
        _key = frozenset([agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana])
        _ids[_key].append(refeicao['_id']['$oid'])
        data_inicial = min(semanas[_key_semana])
        data_final = max(semanas[_key_semana])

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        pendentes.append(
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana])

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        pendente.append(','.join(_ids[_key]))

    return pendentes


def get_escolas():
    url = api + '/escolas?completo'
    r = requests.get(url)
    escolas = r.json()

    return escolas


def get_escola(cod_eol):
    url = api + '/escola/{}'.format(cod_eol)
    r = requests.get(url)
    escola = r.json()

    return escola


def get_grupo_publicacoes(status):
    url = api + '/editor/cardapios?status=' + status
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

    pendentes = []
    _ids = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])
        _key = frozenset([agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana])
        _ids[_key].append(refeicao['_id']['$oid'])
        data_inicial = min(semanas[_key_semana])
        data_final = max(semanas[_key_semana])

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        pendentes.append(
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana])

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        pendente.append(','.join(_ids[_key]))

    return pendentes


def get_pendencias_terceirizadas():
    FILE = './tmp/Cardapio_Terceirizadas.txt'
    return terceirizadaslist.create(FILE)


def get_cardapios_iguais():
    url = api + '/editor/cardapios?status=PENDENTE&status=SALVO'
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

    pendentes = []
    ingredientes = {}
    _ids = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])

        for alimentos in refeicao['cardapio_original'].keys():
            [agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana]
            _key = frozenset(alimentos)
            _ids[_key].append(refeicao['_id']['$oid'])
            data_inicial = min(semanas[_key_semana])
            data_final = max(semanas[_key_semana])

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        pendentes.append(
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana])

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        pendente.append(','.join(_ids[_key]))

    return pendentes


def allowed_file(filename):
    ALLOWED_EXTENSIONS = set(['txt', 'XML', 'xml'])
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def dia_semana(dia):
    diasemana = ('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom')
    return diasemana[dia]


def replace_cardapio(cardapio):
    config_editor = db_functions.select_all()

    for de_para in config_editor:
        cardapio = [de_para[4] if x == de_para[3] else x for x in cardapio]

    cardapio = [x for x in cardapio if x != '']
    return cardapio


def filtro_dicionarios(dictlist, key, valuelist):
    lista_filtrada = [dictio for dictio in dictlist if dictio[key] in valuelist]
    if lista_filtrada:
        return lista_filtrada[0]
    else:
        return []


def get_cardapios_terceirizadas(tipo_gestao, tipo_escola, edital, idade):
    return db_functions.select_receitas_terceirizadas(tipo_gestao, tipo_escola, edital, idade)


if __name__ == "__main__":
    db_setup.set()
    app.secret_key = os.urandom(12)
    app.config['UPLOAD_FOLDER'] = './tmp'
    app.run(debug=True, host='0.0.0.0', port=5000)
