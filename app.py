from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_mysqldb import MySQL
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import MySQLdb.cursors
import pytz
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = 'projeto'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'db_gerenciador'
mysql = MySQL(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Por favor, faça login para acessar esta página."

class User(UserMixin):
    def __init__(self, id, nome, email, senha):
        self.id = id
        self.nome = nome
        self.email = email
        self.senha = senha

def formatarData(dataString):
    if not dataString or dataString == 'None':
        return 'Data não informada'

    if re.match(r'\d{2}/\d{2}/\d{4}', dataString):
        return dataString

    try:
        try:
            data = datetime.strptime(dataString, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            data = datetime.strptime(dataString, '%Y-%m-%d')

        if isinstance(data, datetime):
            return data.strftime('%d/%m/%Y')

        utc_timezone = pytz.utc
        br_timezone = pytz.timezone('America/Sao_Paulo')
        
        if data.tzinfo is None:
            data_utc = utc_timezone.localize(data)
        else:
            data_utc = data.astimezone(utc_timezone)
            
        data_brasil = data_utc.astimezone(br_timezone)
        return data_brasil.strftime('%d/%m/%Y')

    except Exception as e:
        app.logger.error(f"Erro ao formatar data {dataString}: {str(e)}")
        return 'Data inválida'

@login_manager.user_loader
def load_user(user_id):
    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM usuarios WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    if user:
        return User(user['id'], user['nome'], user['email'], user['senha'])
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']

        if password != confirm_password:
            flash('As senhas não coincidem. Tente novamente.', 'error')
            return redirect(url_for('cadastro'))

        hashed_password = generate_password_hash(password)

        conn = mysql.connection
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)",
                (nome, email, hashed_password)
            )
            conn.commit()
            flash('Cadastro realizado com sucesso! Faça login para acessar.', 'success')
            return redirect(url_for('login'))
        except MySQLdb.IntegrityError:
            flash('Email já cadastrado. Use um email diferente.', 'error')
        finally:
            cursor.close()

    return render_template('cadastro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = mysql.connection
        cursor = conn.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()

        if user and check_password_hash(user['senha'], password):
            user_obj = User(user['id'], user['nome'], user['email'], user['senha'])
            login_user(user_obj)
            return redirect(url_for('usuario'))
        else:
            flash('E-mail ou senha incorretos. Tente novamente.', 'error')

    return render_template('login.html')

@app.route('/usuario')
@login_required
def usuario():
    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT SUM(valor) AS total_receitas FROM receitas WHERE usuario_id = %s", (current_user.id,))
    total_receitas = cursor.fetchone()['total_receitas'] or 0

    cursor.execute("SELECT SUM(valor) AS total_despesas FROM despesas WHERE usuario_id = %s", (current_user.id,))
    total_despesas = cursor.fetchone()['total_despesas'] or 0

    saldo_total = total_receitas - total_despesas

    cursor.execute("""
        SELECT total_limite 
        FROM totais_mensais 
        WHERE usuario_id = %s AND mes = MONTH(CURRENT_DATE()) AND ano = YEAR(CURRENT_DATE())
    """, (current_user.id,))
    limite_result = cursor.fetchone()
    total_limite = limite_result['total_limite'] if limite_result else 0

    cursor.close()
    return render_template('usuario.html', nome=current_user.nome, saldo_total=saldo_total, total_limite=total_limite, total_gasto=total_despesas)

@app.route('/historico')
@login_required
def historico():
    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT nome, imagem FROM categorias")
    categorias = cursor.fetchall()
    cursor.close()
    return render_template('historico.html', categorias=categorias)

@app.route('/relatorios')
@login_required
def relatorios():
    return render_template('relatorios.html')

@app.route('/transacoes', methods=['GET'])
@login_required
def transacoes():
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)
    categoria = request.args.get('categoria', default=None)
    tipo = request.args.get('tipo', default=None)
    data_filtro = request.args.get('data', default=None)
    prazo_filtro = request.args.get('prazo', default=None)

    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)

    query_despesas = """
        SELECT d.*, c.imagem AS categoria_imagem 
        FROM despesas d
        JOIN categorias c ON d.categoria = c.nome
        WHERE d.usuario_id = %s
    """
    params_despesas = [current_user.id]

    query_receitas = """
        SELECT r.*, c.imagem AS categoria_imagem 
        FROM receitas r
        JOIN categorias c ON r.categoria = c.nome
        WHERE r.usuario_id = %s
    """
    params_receitas = [current_user.id]

    if mes and ano:
        query_despesas += " AND MONTH(d.data) = %s AND YEAR(d.data) = %s"
        params_despesas.extend([mes, ano])
        query_receitas += " AND MONTH(r.data) = %s AND YEAR(r.data) = %s"
        params_receitas.extend([mes, ano])

    if categoria:
        query_despesas += " AND d.categoria = %s"
        params_despesas.append(categoria)
        query_receitas += " AND r.categoria = %s"
        params_receitas.append(categoria)

    if data_filtro:
        try:
            data_obj = datetime.strptime(data_filtro, '%Y-%m-%d').date()
            query_despesas += " AND DATE(d.data) = %s"
            params_despesas.append(data_obj)
            query_receitas += " AND DATE(r.data) = %s"
            params_receitas.append(data_obj)
        except ValueError:
            pass

    if prazo_filtro:
        try:
            prazo_obj = datetime.strptime(prazo_filtro, '%Y-%m-%d').date()
            query_despesas += " AND DATE(d.prazo) = %s"
            params_despesas.append(prazo_obj)
        except ValueError:
            pass

    despesas = []
    if not tipo or tipo == 'despesa':
        cursor.execute(query_despesas, params_despesas)
        despesas = cursor.fetchall()
        for d in despesas:
            d['tipo'] = 'despesa'
            d['data'] = d['data'].isoformat() if d['data'] else None
            d['prazo'] = d['prazo'].isoformat() if d['prazo'] else None

    receitas = []
    if not tipo or tipo == 'receita':
        cursor.execute(query_receitas, params_receitas)
        receitas = cursor.fetchall()
        for r in receitas:
            r['tipo'] = 'receita'
            r['data'] = r['data'].isoformat() if r['data'] else None

    cursor.close()
    return jsonify({'despesas': despesas, 'receitas': receitas})

@app.route('/adicionar_receita', methods=['POST'])
@login_required
def adicionar_receita():
    try:
        dados = request.get_json() if request.is_json else request.form
        descricao = dados.get('descricao')
        valor = dados.get('valor')
        data_transacao = dados.get('data')
        categoria = dados.get('categoria')

        if not all([descricao, valor, data_transacao, categoria]):
            return jsonify({'success': False, 'error': 'Todos os campos são obrigatórios'}), 400

        try:
            data_obj = datetime.strptime(data_transacao, '%Y-%m-%d').date()
        except ValueError as e:
            return jsonify({'success': False, 'error': f'Formato de data inválido: {str(e)}'}), 400

        conn = mysql.connection
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO receitas (usuario_id, descricao, valor, data, categoria) 
            VALUES (%s, %s, %s, %s, %s)
        """, (current_user.id, descricao, valor, data_obj, categoria))
        
        conn.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': 'Receita adicionada com sucesso!'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao adicionar receita: {str(e)}'
        }), 500

@app.route('/adicionar_despesa', methods=['POST'])
@login_required
def adicionar_despesa():
    try:
        dados = request.get_json() if request.is_json else request.form
        descricao = dados.get('descricao')
        valor = float(dados.get('valor'))
        data_transacao = dados.get('data')
        prazo = dados.get('prazo')
        categoria = dados.get('categoria')

        if not all([descricao, valor, data_transacao, prazo, categoria]):
            return jsonify({'success': False, 'error': 'Todos os campos são obrigatórios'}), 400

        if valor <= 0:
            return jsonify({'success': False, 'error': 'O valor deve ser positivo'}), 400

        try:
            data_obj = datetime.strptime(data_transacao, '%Y-%m-%d').date()
            prazo_obj = datetime.strptime(prazo, '%Y-%m-%d').date()
            
            if prazo_obj < data_obj:
                return jsonify({'success': False, 'error': 'O prazo deve ser posterior à data da despesa'}), 400
        except ValueError as e:
            return jsonify({'success': False, 'error': f'Formato of data inválido: {str(e)}'}), 400

        conn = mysql.connection
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO despesas (usuario_id, descricao, valor, data, prazo, categoria) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (current_user.id, descricao, valor, data_obj, prazo_obj, categoria))
        
        conn.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': 'Despesa adicionada com sucesso!'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao adicionar despesa: {str(e)}'
        }), 500

@app.route('/categorias', methods=['GET'])
@login_required
def categorias():
    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT nome, imagem FROM categorias")
    categorias = cursor.fetchall()
    cursor.close()
    return jsonify(categorias)

@app.route('/saldo')
@login_required
def obter_saldo():
    conn = mysql.connection
    cursor = conn.cursor()

    cursor.execute("SELECT SUM(valor) AS total_receitas FROM receitas WHERE usuario_id = %s", (current_user.id,))
    total_receitas = cursor.fetchone()['total_receitas'] or 0

    cursor.execute("SELECT SUM(valor) AS total_despesas FROM despesas WHERE usuario_id = %s", (current_user.id,))
    total_despesas = cursor.fetchone()['total_despesas'] or 0

    saldo_total = total_receitas - total_despesas

    cursor.close()
    return jsonify({'saldo': saldo_total})
@app.route('/metas', methods=['GET', 'POST'])
@login_required
def metas():
    if request.method == 'POST':
        return criar_cofre()
    
    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)
    
    cursor.execute("SELECT nome, imagem FROM categorias")
    categorias = cursor.fetchall()
    
    cursor.execute("SELECT * FROM cofre WHERE usuario_id = %s", (current_user.id,))
    cofres = cursor.fetchall()
    
    cursor.close()
    return render_template('metas.html', categorias=categorias, cofres=cofres)

@app.route('/salvar_meta', methods=['POST'])
def salvar_meta():
    usuario_id = request.form['usuario_id']
    categoria = request.form['categoria']
    valor = request.form['valor']
    mes = request.form['mes']
    ano = request.form['ano']

    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO metas (usuario_id, categoria, valor, mes, ano) VALUES (%s, %s, %s, %s, %s)",
                   (usuario_id, categoria, valor, mes, ano))
    mysql.connection.commit()
    cursor.close()

    return jsonify({'status': 'success', 'message': 'Meta salva com sucesso!'})

@app.route('/carregar_limite_total', methods=['GET'])
@login_required
def carregar_limite_total():
    try:
        mes = request.args.get('mes', type=int)
        ano = request.args.get('ano', type=int)
        
        if not mes or not ano:
            return jsonify({'status': 'error', 'message': 'Mês e ano são obrigatórios'}), 400

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT total_limite 
            FROM totais_mensais 
            WHERE usuario_id = %s AND mes = %s AND ano = %s
        """, (current_user.id, mes, ano))
        
        resultado = cursor.fetchone()
        cursor.close()
        
        if resultado:
            return jsonify({
                'status': 'success', 
                'limite_total': float(resultado['total_limite'])
            })
        else:
            cursor = mysql.connection.cursor()
            cursor.execute("""
                INSERT INTO totais_mensais 
                (usuario_id, mes, ano, total_gasto, total_limite)
                VALUES (%s, %s, %s, 0, 0)
            """, (current_user.id, mes, ano))
            mysql.connection.commit()
            cursor.close()
            
            return jsonify({
                'status': 'success',
                'limite_total': 0
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erro ao carregar limite total: {str(e)}'
        }), 500

@app.route('/salvar_limite_total', methods=['POST'])
@login_required
def salvar_limite_total():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Dados inválidos'}), 400

        mes = data.get('mes')
        ano = data.get('ano')
        limite_total = data.get('limite_total')

        if not all([mes, ano, limite_total is not None]):
            return jsonify({'status': 'error', 'message': 'Dados incompletos'}), 400

        cursor = mysql.connection.cursor()
        
        try:
            cursor.execute("""
                SELECT id FROM totais_mensais 
                WHERE usuario_id = %s AND mes = %s AND ano = %s
            """, (current_user.id, mes, ano))
            existe = cursor.fetchone()

            if existe:
                cursor.execute("""
                    UPDATE totais_mensais 
                    SET total_limite = %s 
                    WHERE id = %s
                """, (limite_total, existe[0]))
            else:
                cursor.execute("""
                    INSERT INTO totais_mensais 
                    (usuario_id, mes, ano, total_gasto, total_limite)
                    VALUES (%s, %s, %s, 0, %s)
                """, (current_user.id, mes, ano, limite_total))
            
            mysql.connection.commit()
            return jsonify({'status': 'success'})
            
        except Exception as e:
            mysql.connection.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Erro no banco de dados: {str(e)}'
            }), 500
        finally:
            cursor.close()

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erro geral: {str(e)}'
        }), 500
        
@app.route('/configuracoes')
@login_required
def configuracoes():
    return render_template('configuracoes.html', usuario=current_user)


@app.route('/notificacoes')
@login_required
def notificacoes():
    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)
    
    cursor.execute("""
        SELECT descricao, prazo 
        FROM despesas 
        WHERE usuario_id = %s AND status = 'pendente' AND prazo <= CURDATE() + INTERVAL 5 DAY
    """, (current_user.id,))
    proximas_despesas = cursor.fetchall()
    
    cursor.execute("""
        SELECT id, nome, limite, valor_juntado 
        FROM cofre 
        WHERE usuario_id = %s AND valor_juntado >= limite
    """, (current_user.id,))
    metas_atingidas = cursor.fetchall()
    
    for despesa in proximas_despesas:
        if despesa['prazo']:
            despesa['prazo'] = despesa['prazo'].isoformat()
    
    for meta in metas_atingidas:
        meta['tipo'] = 'meta_atingida'
    
    cursor.close()
    
    return jsonify({
        'despesas': proximas_despesas,
        'metas_atingidas': metas_atingidas
    })

@app.route('/limpar_notificacoes', methods=['POST'])
@login_required
def limpar_notificacoes():
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE despesas 
        SET status = 'lida' 
        WHERE usuario_id = %s AND prazo <= CURDATE() + INTERVAL 5 DAY
    """, (current_user.id,))
    conn.commit()
    cursor.close()
    return jsonify(success=True)

@app.route('/alterar_nome', methods=['POST'])
@login_required
def alterar_nome():
    data = request.get_json()
    novo_nome = data.get('nome')
    usuario_id = current_user.id

    if not novo_nome:
        return jsonify({'success': False, 'error': 'Nome não fornecido.'}), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT nome FROM usuarios WHERE id = %s", (usuario_id,))
    nome_atual = cur.fetchone()

    if nome_atual is None:
        return jsonify({'success': False, 'error': 'Usuário não encontrado.'}), 404

    nome_atual = nome_atual[0]

    if novo_nome == nome_atual:
        return jsonify({'success': False, 'error': 'O novo nome deve ser diferente do nome atual.'}), 400
    else:
        try:
            cur.execute("UPDATE usuarios SET nome = %s WHERE id = %s", (novo_nome, usuario_id))
            mysql.connection.commit()
            return jsonify({'success': True, 'message': 'Nome alterado com sucesso!'})
        except Exception as e:
            return jsonify({'success': False, 'error': f'Erro ao alterar o nome: {str(e)}'}), 500

@app.route('/alterar_senha', methods=['POST'])
@login_required
def alterar_senha():
    senha_atual = request.json.get('senha_atual')
    nova_senha = request.json.get('senha')

    if not senha_atual:
        return jsonify({'success': False, 'error': 'Por favor, insira sua senha atual.'}), 400

    if not nova_senha:
        return jsonify({'success': False, 'error': 'Por favor, insira uma nova senha.'}), 400

    if not check_password_hash(current_user.senha, senha_atual):
        return jsonify({'success': False, 'error': 'Senha atual está incorreta.'}), 400

    hashed_password = generate_password_hash(nova_senha)
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET senha = %s WHERE id = %s", (hashed_password, current_user.id))
    conn.commit()
    cursor.close()

    return jsonify({'success': True, 'message': 'Senha alterada com sucesso!'}), 200

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso.', 'success')
    return redirect(url_for('index'))

@app.route('/transacao/<int:id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def transacao(id):
    if request.method == 'GET':
        tipo = request.args.get('tipo')
        if tipo not in ['receita', 'despesa']:
            return jsonify({'error': 'Tipo de transação inválido'}), 400

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        if tipo == 'receita':
            cursor.execute("""
                SELECT r.*, c.imagem AS categoria_imagem
                FROM receitas r
                JOIN categorias c ON r.categoria = c.nome
                WHERE r.id = %s AND r.usuario_id = %s
            """, (id, current_user.id))
        else:
            cursor.execute("""
                SELECT d.*, c.imagem AS categoria_imagem
                FROM despesas d
                JOIN categorias c ON d.categoria = c.nome
                WHERE d.id = %s AND d.usuario_id = %s
            """, (id, current_user.id))

        transacao = cursor.fetchone()
        cursor.close()
        
        if not transacao:
            return jsonify({'error': 'Transação não encontrada'}), 404

        if 'data' in transacao and transacao['data']:
            transacao['data'] = transacao['data'].isoformat()
        if 'prazo' in transacao and transacao['prazo']:
            transacao['prazo'] = transacao['prazo'].isoformat()
            
        return jsonify(transacao)

    elif request.method == 'PUT':
        tipo = request.args.get('tipo')
        if tipo not in ['receita', 'despesa']:
            return jsonify({'success': False, 'error': 'Tipo de transação inválido'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400

        campos_requeridos = ['descricao', 'valor', 'data', 'categoria']
        if not all(campo in data for campo in campos_requeridos):
            return jsonify({'success': False, 'error': 'Todos os campos são obrigatórios'}), 400

        try:
            data_obj = datetime.strptime(data['data'], '%Y-%m-%d').date()
            
            prazo_obj = None
            if tipo == 'despesa':
                if 'prazo' not in data:
                    return jsonify({'success': False, 'error': 'Prazo é obrigatório para despesas'}), 400
                
                prazo_obj = datetime.strptime(data['prazo'], '%Y-%m-%d').date()
                
                if prazo_obj < data_obj:
                    return jsonify({'success': False, 'error': 'O prazo deve ser posterior à data da transação'}), 400

            cursor = mysql.connection.cursor()
            
            try:
                cursor.execute(f"""
                    SELECT id FROM {tipo}s 
                    WHERE id = %s AND usuario_id = %s
                """, (id, current_user.id))
                
                if not cursor.fetchone():
                    return jsonify({'success': False, 'error': 'Transação não encontrada ou não autorizada'}), 404

                if tipo == 'despesa':
                    cursor.execute("""
                        UPDATE despesas 
                        SET descricao = %s, 
                            valor = %s, 
                            data = %s, 
                            prazo = %s, 
                            categoria = %s
                        WHERE id = %s
                    """, (
                        data['descricao'],
                        float(data['valor']),
                        data_obj,
                        prazo_obj,
                        data['categoria'],
                        id
                    ))
                else:
                    cursor.execute("""
                        UPDATE receitas 
                        SET descricao = %s, 
                            valor = %s, 
                            data = %s, 
                            categoria = %s
                        WHERE id = %s
                    """, (
                        data['descricao'],
                        float(data['valor']),
                        data_obj,
                        data['categoria'],
                        id
                    ))

                mysql.connection.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Transação atualizada com sucesso!',
                    'id': id
                })
            
            except Exception as e:
                mysql.connection.rollback()
                app.logger.error(f"Erro ao atualizar transação: {str(e)}")
                return jsonify({'success': False, 'error': 'Erro interno ao atualizar transação'}), 500
            finally:
                cursor.close()

        except ValueError as e:
            return jsonify({'success': False, 'error': f'Formato de data inválido: {str(e)}'}), 400

    elif request.method == 'DELETE':
        tipo = request.args.get('tipo')
        if tipo not in ['receita', 'despesa']:
            return jsonify({'success': False, 'error': 'Tipo de transação inválido'}), 400

        cursor = mysql.connection.cursor()
        
        try:
            cursor.execute(f"""
                SELECT id FROM {tipo}s 
                WHERE id = %s AND usuario_id = %s
            """, (id, current_user.id))
            
            if not cursor.fetchone():
                return jsonify({'success': False, 'error': 'Transação não encontrada ou não autorizada'}), 404

            cursor.execute(f"DELETE FROM {tipo}s WHERE id = %s", (id,))
            mysql.connection.commit()
            
            return jsonify({'success': True, 'message': 'Transação excluída com sucesso!'})
        
        except Exception as e:
            mysql.connection.rollback()
            return jsonify({'success': False, 'error': f'Erro ao excluir a transação: {str(e)}'}), 500
        finally:
            cursor.close()

@app.route('/criar_cofre', methods=['POST'])
@login_required
def criar_cofre():
    nome = request.form['nome_meta']
    valor_desejado = request.form['valor_desejado']
    valor_juntado = request.form['valor_juntado']

    conn = mysql.connection
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM cofre 
            WHERE usuario_id = %s AND nome = %s
        """, (current_user.id, nome))
        
        if cursor.fetchone():
            flash('Já existe um cofre com esse nome. Escolha outro nome.', 'error')
            return redirect(url_for('metas'))

        cursor.execute("""
            INSERT INTO cofre (usuario_id, nome, limite, valor_juntado)
            VALUES (%s, %s, %s, %s)
        """, (current_user.id, nome, valor_desejado, valor_juntado))
        conn.commit()
        flash('Cofre criado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao criar cofre: {str(e)}', 'error')
    finally:
        cursor.close()

    return redirect(url_for('metas'))

@app.route('/meus_cofres')
@login_required
def meus_cofres():
    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM cofre WHERE usuario_id = %s", (current_user.id,))
    cofres = cursor.fetchall()
    cursor.close()
    return render_template('meus_cofres.html', cofres=cofres)

@app.route('/excluir_cofre/<int:cofre_id>', methods=['DELETE'])
@login_required
def excluir_cofre(cofre_id):
    conn = mysql.connection
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM cofre WHERE id = %s AND usuario_id = %s", (cofre_id, current_user.id))
        conn.commit()
        return jsonify(success=True), 200
    except Exception as e:
        print(f"Erro ao excluir cofre: {e}")
        return jsonify(success=False), 500
    finally:
        cursor.close()

@app.route('/editar_cofre', methods=['POST'])
@login_required
def editar_cofre():
    cofre_id = request.form['cofre_id']
    novo_nome = request.form['nome_meta']
    novo_limite = request.form['valor_desejado']
    
    conn = mysql.connection
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE cofre 
            SET nome = %s, limite = %s 
            WHERE id = %s AND usuario_id = %s
        """, (novo_nome, novo_limite, cofre_id, current_user.id))
        conn.commit()
        flash('Cofrinho atualizado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar cofre: {str(e)}', 'error')
    finally:
        cursor.close()

    return redirect(url_for('metas'))

@app.route('/adicionar_valor', methods=['POST'])
@login_required
def adicionar_valor():
    cofre_id = request.form['cofre_id']
    valor_adicionar = request.form['valor_adicionar']

    conn = mysql.connection
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE cofre 
            SET valor_juntado = valor_juntado + %s 
            WHERE id = %s AND usuario_id = %s
        """, (valor_adicionar, cofre_id, current_user.id))
        conn.commit()
        flash('Valor adicionado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar valor: {str(e)}', 'error')
    finally:
        cursor.close()

    return redirect(url_for('metas'))

@app.route('/obter_valor_cofre/<int:cofre_id>', methods=['GET'])
@login_required
def obter_valor_cofre(cofre_id):
    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)
    
    cursor.execute("""
        SELECT valor_juntado 
        FROM cofre 
        WHERE id = %s AND usuario_id = %s
    """, (cofre_id, current_user.id))
    
    cofre = cursor.fetchone()
    cursor.close()
    
    if cofre:
        return jsonify({
            'status': 'success',
            'valor_juntado': float(cofre['valor_juntado'])
        })
    return jsonify({'status': 'error', 'message': 'Cofre não encontrado'}), 404

@app.route('/retirar_valor', methods=['POST'])
@login_required
def retirar_valor():
    try:
        cofre_id = request.form['cofre_id']
        valor_retirar = float(request.form['valor_retira'])
        
        conn = mysql.connection
        cursor = conn.cursor()
        
        cursor.execute("SELECT valor_juntado FROM cofre WHERE id = %s AND usuario_id = %s", 
                      (cofre_id, current_user.id))
        cofre = cursor.fetchone()
        
        if not cofre:
            return jsonify({'status': 'error', 'message': 'Cofre não encontrado'}), 404
            
        if valor_retirar > cofre[0]:
            return jsonify({'status': 'error', 'message': 'Saldo insuficiente'}), 400

        cursor.execute("""
            UPDATE cofre 
            SET valor_juntado = valor_juntado - %s 
            WHERE id = %s AND usuario_id = %s
        """, (valor_retirar, cofre_id, current_user.id))
        
        conn.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Valor retirado com sucesso'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Erro ao retirar valor: {str(e)}'
        }), 500
    finally:
        cursor.close()

@app.route('/dados_limite')
@login_required
def dados_limite():
    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)
    
    cursor.execute("""
        SELECT total_limite 
        FROM totais_mensais 
        WHERE usuario_id = %s AND mes = MONTH(CURRENT_DATE()) AND ano = YEAR(CURRENT_DATE())
    """, (current_user.id,))
    limite_result = cursor.fetchone()
    total_limite = limite_result['total_limite'] if limite_result else 0

    cursor.execute("SELECT SUM(valor) AS total_gasto FROM despesas WHERE usuario_id = %s", (current_user.id,))
    total_gasto = cursor.fetchone()['total_gasto'] or 0

    cursor.close()
    return jsonify({'limite': total_limite, 'gasto': total_gasto})


if __name__ == '__main__':
    app.run(debug=True)