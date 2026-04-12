import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from mysql.connector import Error
from datetime import datetime

# Carregar variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'chave-padrao-desenvolvimento')

# Configuração do banco de dados a partir do .env
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'oficina_db'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'port': int(os.getenv('DB_PORT', 3306))
}

def get_db_connection():
    """Retorna uma conexão com o MySQL."""
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Error as e:
        print(f"Erro ao conectar ao MySQL: {e}")
        return None

# ---------- ROTAS PRINCIPAIS ----------
@app.route('/')
def index():
    """Dashboard principal."""
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return render_template('index.html', clientes_count=0, os_abertas_count=0,
                               pecas_baixo_estoque=0, faturamento_mes=0,
                               ultimas_os=[], alertas_estoque=[])

    cursor = conn.cursor(dictionary=True)

    # Contagem de clientes ativos
    cursor.execute("SELECT COUNT(*) as total FROM clientes WHERE ativo = 1")
    clientes_count = cursor.fetchone()['total']

    # Contagem de OS abertas (status != CONCLUÍDA e != CANCELADA)
    cursor.execute("SELECT COUNT(*) as total FROM ordens_servico WHERE status NOT IN ('CONCLUÍDA', 'CANCELADA')")
    os_abertas_count = cursor.fetchone()['total']

    # Peças com estoque baixo (<=5)
    cursor.execute("SELECT COUNT(*) as total FROM pecas WHERE quantidade_estoque <= 5 AND ativo = 1")
    pecas_baixo_estoque = cursor.fetchone()['total']

    # Faturamento do mês atual (pagamentos registrados)
    mes_atual = datetime.now().strftime('%Y-%m')
    cursor.execute("""
        SELECT SUM(valor_pago) as total FROM pagamentos
        WHERE DATE_FORMAT(data_pagamento, '%%Y-%%m') = %s
    """, (mes_atual,))
    faturamento_mes = cursor.fetchone()['total'] or 0

    # Últimas 5 OS
    cursor.execute("""
        SELECT os.id, os.data_abertura, os.status, c.nome as cliente_nome
        FROM ordens_servico os
        JOIN clientes c ON os.cliente_id = c.id
        ORDER BY os.id DESC LIMIT 5
    """)
    ultimas_os = cursor.fetchall()

    # Alertas de estoque (peças com quantidade <=5)
    cursor.execute("SELECT nome, quantidade_estoque FROM pecas WHERE quantidade_estoque <= 5 AND ativo = 1")
    alertas_estoque = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html',
                           clientes_count=clientes_count,
                           os_abertas_count=os_abertas_count,
                           pecas_baixo_estoque=pecas_baixo_estoque,
                           faturamento_mes=faturamento_mes,
                           ultimas_os=ultimas_os,
                           alertas_estoque=alertas_estoque)

# ---------- CLIENTES ----------
@app.route('/clientes')
def clientes():
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return render_template('clientes.html', clientes=[])

    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.*, 
               (SELECT COUNT(*) FROM veiculos WHERE cliente_id = c.id AND ativo = 1) as veiculos_count
        FROM clientes c WHERE ativo = 1
    """)
    clientes_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('clientes.html', clientes=clientes_list)

@app.route('/salvar_cliente', methods=['POST'])
def salvar_cliente():
    cliente_id = request.form.get('id')
    nome = request.form.get('nome')
    telefone = request.form.get('telefone')
    email = request.form.get('email')
    documento = request.form.get('documento')
    endereco = request.form.get('endereco')
    observacoes = request.form.get('observacoes')

    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return redirect(url_for('clientes'))

    cursor = conn.cursor()
    try:
        if cliente_id:  # Edição
            sql = """
                UPDATE clientes SET nome=%s, telefone=%s, email=%s, documento=%s,
                endereco=%s, observacoes=%s WHERE id=%s
            """
            cursor.execute(sql, (nome, telefone, email, documento, endereco, observacoes, cliente_id))
            flash('Cliente atualizado com sucesso!', 'success')
        else:  # Novo
            sql = """
                INSERT INTO clientes (nome, telefone, email, documento, endereco, observacoes, ativo, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, 1, NOW())
            """
            cursor.execute(sql, (nome, telefone, email, documento, endereco, observacoes))
            flash('Cliente cadastrado com sucesso!', 'success')
        conn.commit()
    except Error as e:
        flash(f'Erro ao salvar cliente: {e}', 'danger')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('clientes'))

@app.route('/excluir_cliente/<int:id>', methods=['POST'])
def excluir_cliente(id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Desativa o cliente (soft delete)
            cursor.execute("UPDATE clientes SET ativo = 0 WHERE id = %s", (id,))
            conn.commit()
            flash('Cliente removido com sucesso!', 'success')
        except Error as e:
            flash(f'Erro ao excluir cliente: {e}', 'danger')
        finally:
            cursor.close()
            conn.close()
    return redirect(url_for('clientes'))

# ---------- VEÍCULOS ----------
@app.route('/veiculos')
def veiculos():
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return render_template('veiculos.html', veiculos=[], clientes=[])

    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT v.*, c.nome as cliente_nome
        FROM veiculos v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.ativo = 1
    """)
    veiculos_list = cursor.fetchall()
    cursor.execute("SELECT id, nome FROM clientes WHERE ativo = 1")
    clientes_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('veiculos.html', veiculos=veiculos_list, clientes=clientes_list)

@app.route('/salvar_veiculo', methods=['POST'])
def salvar_veiculo():
    veiculo_id = request.form.get('id')
    cliente_id = request.form.get('cliente_id')
    placa = request.form.get('placa')
    modelo = request.form.get('modelo')
    marca = request.form.get('marca')
    ano = request.form.get('ano')
    observacoes = request.form.get('observacoes')

    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return redirect(url_for('veiculos'))

    cursor = conn.cursor()
    try:
        if veiculo_id:
            sql = """
                UPDATE veiculos SET cliente_id=%s, placa=%s, modelo=%s, marca=%s, ano=%s, observacoes=%s
                WHERE id=%s
            """
            cursor.execute(sql, (cliente_id, placa, modelo, marca, ano, observacoes, veiculo_id))
            flash('Veículo atualizado!', 'success')
        else:
            sql = """
                INSERT INTO veiculos (cliente_id, placa, modelo, marca, ano, observacoes, ativo)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
            """
            cursor.execute(sql, (cliente_id, placa, modelo, marca, ano, observacoes))
            flash('Veículo cadastrado!', 'success')
        conn.commit()
    except Error as e:
        flash(f'Erro: {e}', 'danger')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('veiculos'))

# ---------- MECÂNICOS ----------
@app.route('/mecanicos')
def mecanicos():
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return render_template('mecanicos.html', mecanicos=[])

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM mecanicos WHERE ativo = 1")
    mecanicos_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('mecanicos.html', mecanicos=mecanicos_list)

@app.route('/salvar_mecanico', methods=['POST'])
def salvar_mecanico():
    mecanico_id = request.form.get('id')
    nome = request.form.get('nome')
    especialidade = request.form.get('especialidade')
    telefone = request.form.get('telefone')
    observacoes = request.form.get('observacoes')

    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return redirect(url_for('mecanicos'))

    cursor = conn.cursor()
    try:
        if mecanico_id:
            sql = "UPDATE mecanicos SET nome=%s, especialidade=%s, telefone=%s, observacoes=%s WHERE id=%s"
            cursor.execute(sql, (nome, especialidade, telefone, observacoes, mecanico_id))
            flash('Mecânico atualizado!', 'success')
        else:
            sql = "INSERT INTO mecanicos (nome, especialidade, telefone, observacoes, ativo) VALUES (%s, %s, %s, %s, 1)"
            cursor.execute(sql, (nome, especialidade, telefone, observacoes))
            flash('Mecânico cadastrado!', 'success')
        conn.commit()
    except Error as e:
        flash(f'Erro: {e}', 'danger')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('mecanicos'))

# ---------- ESTOQUE (PEÇAS) ----------
@app.route('/estoque')
def estoque():
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return render_template('estoque.html', pecas=[], alerta_baixo_estoque=False)

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM pecas WHERE ativo = 1 ORDER BY nome")
    pecas_list = cursor.fetchall()
    # Verifica se há algum alerta de estoque baixo (<=5)
    alerta = any(p['quantidade_estoque'] <= 5 for p in pecas_list)
    cursor.close()
    conn.close()
    return render_template('estoque.html', pecas=pecas_list, alerta_baixo_estoque=alerta)

@app.route('/salvar_peca', methods=['POST'])
def salvar_peca():
    peca_id = request.form.get('id')
    codigo = request.form.get('codigo')
    nome = request.form.get('nome')
    quantidade_estoque = request.form.get('quantidade_estoque', 0)
    custo = request.form.get('custo', 0)
    preco_venda = request.form.get('preco_venda', 0)
    observacoes = request.form.get('observacoes')

    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return redirect(url_for('estoque'))

    cursor = conn.cursor()
    try:
        if peca_id:
            sql = """
                UPDATE pecas SET codigo=%s, nome=%s, quantidade_estoque=%s, custo=%s,
                preco_venda=%s, observacoes=%s WHERE id=%s
            """
            cursor.execute(sql, (codigo, nome, quantidade_estoque, custo, preco_venda, observacoes, peca_id))
            flash('Peça atualizada!', 'success')
        else:
            sql = """
                INSERT INTO pecas (codigo, nome, quantidade_estoque, custo, preco_venda, observacoes, ativo, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, 1, NOW())
            """
            cursor.execute(sql, (codigo, nome, quantidade_estoque, custo, preco_venda, observacoes))
            flash('Peça cadastrada!', 'success')
        conn.commit()
    except Error as e:
        flash(f'Erro: {e}', 'danger')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('estoque'))

# ---------- ORDENS DE SERVIÇO (LISTAGEM E FORMULÁRIO) ----------
@app.route('/ordens_servico')
def ordens_servico():
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return render_template('ordens_servico.html', ordens=[])

    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT os.id, os.data_abertura, os.status, os.valor_total,
               c.nome as cliente_nome, v.placa as veiculo_placa, m.nome as mecanico_nome
        FROM ordens_servico os
        JOIN clientes c ON os.cliente_id = c.id
        JOIN veiculos v ON os.veiculo_id = v.id
        LEFT JOIN mecanicos m ON os.mecanico_id = m.id
        ORDER BY os.id DESC
    """)
    ordens_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('ordens_servico.html', ordens=ordens_list)

@app.route('/nova_os')
def nova_os():
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return redirect(url_for('ordens_servico'))

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nome FROM clientes WHERE ativo = 1")
    clientes = cursor.fetchall()
    cursor.execute("SELECT id, placa, modelo FROM veiculos WHERE ativo = 1")
    veiculos = cursor.fetchall()
    cursor.execute("SELECT id, nome FROM mecanicos WHERE ativo = 1")
    mecanicos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('os_form.html', os=None, clientes=clientes, veiculos=veiculos, mecanicos=mecanicos)

@app.route('/editar_os/<int:id>')
def editar_os(id):
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return redirect(url_for('ordens_servico'))

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM ordens_servico WHERE id = %s", (id,))
    os_data = cursor.fetchone()
    if not os_data:
        flash('OS não encontrada', 'warning')
        return redirect(url_for('ordens_servico'))

    cursor.execute("SELECT id, nome FROM clientes WHERE ativo = 1")
    clientes = cursor.fetchall()
    cursor.execute("SELECT id, placa, modelo FROM veiculos WHERE ativo = 1")
    veiculos = cursor.fetchall()
    cursor.execute("SELECT id, nome FROM mecanicos WHERE ativo = 1")
    mecanicos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('os_form.html', os=os_data, clientes=clientes, veiculos=veiculos, mecanicos=mecanicos)

@app.route('/salvar_os', methods=['POST'])
def salvar_os():
    os_id = request.form.get('id')
    cliente_id = request.form.get('cliente_id')
    veiculo_id = request.form.get('veiculo_id')
    mecanico_id = request.form.get('mecanico_id') or None
    status = request.form.get('status')
    problema_relatado = request.form.get('problema_relatado')
    diagnostico = request.form.get('diagnostico')
    observacoes = request.form.get('observacoes')
    # Usuário de abertura - por enquanto fixo, depois implementar autenticação
    usuario_id = 1  # TODO: pegar do login

    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return redirect(url_for('ordens_servico'))

    cursor = conn.cursor()
    try:
        if os_id:  # Atualização
            sql = """
                UPDATE ordens_servico SET cliente_id=%s, veiculo_id=%s, mecanico_id=%s,
                status=%s, problema_relatado=%s, diagnostico=%s, observacoes=%s
                WHERE id=%s
            """
            cursor.execute(sql, (cliente_id, veiculo_id, mecanico_id, status, problema_relatado, diagnostico, observacoes, os_id))
            flash('OS atualizada!', 'success')
        else:  # Nova OS
            sql = """
                INSERT INTO ordens_servico (cliente_id, veiculo_id, usuario_abertura_id, mecanico_id,
                data_abertura, status, problema_relatado, diagnostico, observacoes, valor_total)
                VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s, 0)
            """
            cursor.execute(sql, (cliente_id, veiculo_id, usuario_id, mecanico_id, status, problema_relatado, diagnostico, observacoes))
            os_id = cursor.lastrowid
            flash('OS criada com sucesso!', 'success')
        conn.commit()
    except Error as e:
        flash(f'Erro ao salvar OS: {e}', 'danger')
        conn.rollback()
        return redirect(url_for('ordens_servico'))
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('ver_os', id=os_id))

@app.route('/os/<int:id>')
def ver_os(id):
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return redirect(url_for('ordens_servico'))

    cursor = conn.cursor(dictionary=True)
    # Dados da OS
    cursor.execute("""
        SELECT os.*, c.nome as cliente_nome, v.placa as veiculo_placa, v.modelo as veiculo_modelo,
               m.nome as mecanico_nome
        FROM ordens_servico os
        JOIN clientes c ON os.cliente_id = c.id
        JOIN veiculos v ON os.veiculo_id = v.id
        LEFT JOIN mecanicos m ON os.mecanico_id = m.id
        WHERE os.id = %s
    """, (id,))
    os_data = cursor.fetchone()
    if not os_data:
        flash('OS não encontrada', 'warning')
        return redirect(url_for('ordens_servico'))

    # Itens da OS
    cursor.execute("""
        SELECT * FROM os_itens WHERE os_id = %s
    """, (id,))
    itens = cursor.fetchall()

    # Lista de peças para o modal (para adicionar itens)
    cursor.execute("SELECT id, nome, quantidade_estoque FROM pecas WHERE ativo = 1")
    pecas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('os_detalhe.html', os=os_data, itens=itens, pecas=pecas)

@app.route('/adicionar_item_os/<int:os_id>', methods=['POST'])
def adicionar_item_os(os_id):
    tipo = request.form.get('tipo')
    descricao = request.form.get('descricao')
    quantidade = int(request.form.get('quantidade', 1))
    valor_unitario = float(request.form.get('valor_unitario', 0))
    peca_id = request.form.get('peca_id') if tipo == 'PEÇA' else None

    valor_total = quantidade * valor_unitario

    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return redirect(url_for('ver_os', id=os_id))

    cursor = conn.cursor()
    try:
        # Inserir item
        sql_item = """
            INSERT INTO os_itens (os_id, peca_id, descricao, tipo, quantidade, valor_unitario, valor_total)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql_item, (os_id, peca_id, descricao, tipo, quantidade, valor_unitario, valor_total))

        # Se for peça, decrementar estoque
        if tipo == 'PEÇA' and peca_id:
            cursor.execute("UPDATE pecas SET quantidade_estoque = quantidade_estoque - %s WHERE id = %s",
                           (quantidade, peca_id))
            # Verificar estoque baixo
            cursor.execute("SELECT quantidade_estoque FROM pecas WHERE id = %s", (peca_id,))
            estoque_atual = cursor.fetchone()[0]
            if estoque_atual <= 5:
                flash(f'Atenção: estoque da peça agora é {estoque_atual} unidades.', 'warning')

        # Atualizar valor_total da OS
        cursor.execute("SELECT SUM(valor_total) as total FROM os_itens WHERE os_id = %s", (os_id,))
        novo_total = cursor.fetchone()[0] or 0
        cursor.execute("UPDATE ordens_servico SET valor_total = %s WHERE id = %s", (novo_total, os_id))

        conn.commit()
        flash('Item adicionado com sucesso!', 'success')
    except Error as e:
        flash(f'Erro ao adicionar item: {e}', 'danger')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('ver_os', id=os_id))

# ---------- PAGAMENTOS ----------
@app.route('/pagamentos')
def pagamentos():
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return render_template('pagamentos.html', pagamentos=[], ordens_nao_pagas=[])

    cursor = conn.cursor(dictionary=True)
    # Listar todos os pagamentos com nome do cliente
    cursor.execute("""
        SELECT p.*, c.nome as cliente_nome
        FROM pagamentos p
        JOIN ordens_servico os ON p.os_id = os.id
        JOIN clientes c ON os.cliente_id = c.id
        ORDER BY p.data_pagamento DESC
    """)
    pagamentos_list = cursor.fetchall()

    # OS que ainda não foram pagas (nenhum pagamento registrado)
    cursor.execute("""
        SELECT os.id, os.valor_total, c.nome as cliente_nome
        FROM ordens_servico os
        JOIN clientes c ON os.cliente_id = c.id
        WHERE os.status NOT IN ('CANCELADA')
        AND os.id NOT IN (SELECT DISTINCT os_id FROM pagamentos)
        ORDER BY os.id
    """)
    ordens_nao_pagas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('pagamentos.html', pagamentos=pagamentos_list, ordens_nao_pagas=ordens_nao_pagas)

@app.route('/salvar_pagamento', methods=['POST'])
def salvar_pagamento():
    os_id = request.form.get('os_id')
    data_pagamento = request.form.get('data_pagamento')
    forma_pagamento = request.form.get('forma_pagamento')
    valor_pago = float(request.form.get('valor_pago', 0))
    observacoes = request.form.get('observacoes')

    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return redirect(url_for('pagamentos'))

    cursor = conn.cursor()
    try:
        sql = """
            INSERT INTO pagamentos (os_id, data_pagamento, forma_pagamento, valor_pago, observacoes)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (os_id, data_pagamento, forma_pagamento, valor_pago, observacoes))
        # Opcional: marcar OS como paga (adicionar flag na tabela OS? Mantemos simples)
        conn.commit()
        flash('Pagamento registrado com sucesso!', 'success')
    except Error as e:
        flash(f'Erro ao registrar pagamento: {e}', 'danger')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('pagamentos'))

# ---------- RELATÓRIOS ----------
@app.route('/relatorios')
def relatorios():
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return render_template('relatorios.html', os_abertas=[], os_concluidas_mes=[],
                               estoque_baixo=[], faturamento_periodo=0)

    cursor = conn.cursor(dictionary=True)

    # OS abertas (não concluídas e não canceladas)
    cursor.execute("""
        SELECT os.id, os.data_abertura, c.nome as cliente_nome
        FROM ordens_servico os
        JOIN clientes c ON os.cliente_id = c.id
        WHERE os.status NOT IN ('CONCLUÍDA', 'CANCELADA')
        ORDER BY os.data_abertura DESC
    """)
    os_abertas = cursor.fetchall()

    # OS concluídas no mês corrente
    mes_atual = datetime.now().strftime('%Y-%m')
    cursor.execute("""
        SELECT os.id, os.data_conclusao, c.nome as cliente_nome
        FROM ordens_servico os
        JOIN clientes c ON os.cliente_id = c.id
        WHERE os.status = 'CONCLUÍDA'
        AND DATE_FORMAT(os.data_conclusao, '%%Y-%%m') = %s
    """, (mes_atual,))
    os_concluidas_mes = cursor.fetchall()

    # Estoque baixo (quantidade <=5)
    cursor.execute("SELECT nome, quantidade_estoque FROM pecas WHERE quantidade_estoque <= 5 AND ativo = 1")
    estoque_baixo = cursor.fetchall()

    # Faturamento por período (padrão: mês atual)
    data_ini = request.args.get('data_ini')
    data_fim = request.args.get('data_fim')
    if data_ini and data_fim:
        cursor.execute("""
            SELECT SUM(valor_pago) as total FROM pagamentos
            WHERE data_pagamento BETWEEN %s AND %s
        """, (data_ini, data_fim))
    else:
        cursor.execute("""
            SELECT SUM(valor_pago) as total FROM pagamentos
            WHERE DATE_FORMAT(data_pagamento, '%%Y-%%m') = %s
        """, (mes_atual,))
    faturamento = cursor.fetchone()['total'] or 0

    cursor.close()
    conn.close()
    return render_template('relatorios.html',
                           os_abertas=os_abertas,
                           os_concluidas_mes=os_concluidas_mes,
                           estoque_baixo=estoque_baixo,
                           faturamento_periodo=faturamento)

# ---------- USUÁRIOS (SIMPLES) ----------
@app.route('/usuarios')
def usuarios():
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return render_template('usuarios.html', usuarios=[])

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nome, email, ativo, telefone FROM usuarios ORDER BY nome")
    usuarios_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('usuarios.html', usuarios=usuarios_list)

@app.route('/salvar_usuario', methods=['POST'])
def salvar_usuario():
    usuario_id = request.form.get('id')
    nome = request.form.get('nome')
    email = request.form.get('email')
    senha = request.form.get('senha')
    telefone = request.form.get('telefone')
    ativo = 1 if request.form.get('ativo') == '1' else 0

    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão', 'danger')
        return redirect(url_for('usuarios'))

    cursor = conn.cursor()
    try:
        if usuario_id:  # Edição
            if senha:
                sql = "UPDATE usuarios SET nome=%s, email=%s, senha_hash=%s, telefone=%s, ativo=%s WHERE id=%s"
                # Hash simples (em produção usar bcrypt)
                cursor.execute(sql, (nome, email, senha, telefone, ativo, usuario_id))
            else:
                sql = "UPDATE usuarios SET nome=%s, email=%s, telefone=%s, ativo=%s WHERE id=%s"
                cursor.execute(sql, (nome, email, telefone, ativo, usuario_id))
            flash('Usuário atualizado!', 'success')
        else:
            if not senha:
                flash('Senha obrigatória para novo usuário', 'danger')
                return redirect(url_for('usuarios'))
            sql = "INSERT INTO usuarios (nome, email, senha_hash, telefone, ativo, criado_em) VALUES (%s, %s, %s, %s, %s, NOW())"
            cursor.execute(sql, (nome, email, senha, telefone, ativo))
            flash('Usuário cadastrado!', 'success')
        conn.commit()
    except Error as e:
        flash(f'Erro: {e}', 'danger')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('usuarios'))

# ---------- INICIALIZAÇÃO ----------
if __name__ == '__main__':
    app.run(debug=True)