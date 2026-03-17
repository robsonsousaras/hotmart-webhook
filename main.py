from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, auth, firestore
import random
import string
import os
import json
from datetime import datetime, timedelta
import urllib.request

app = Flask(__name__)

cred_json = os.environ.get("FIREBASE_CREDENTIALS")
cred_dict = json.loads(cred_json)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")

def gerar_senha(tamanho=10):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for _ in range(tamanho))

def identificar_plano(nome_produto):
    nome = nome_produto.lower()
    if 'vitalicio' in nome or 'vitalício' in nome or 'lifetime' in nome:
        return 'vitalicio'
    elif 'anual' in nome or 'annual' in nome or '12 mes' in nome:
        return 'anual'
    else:
        return 'mensal'

def calcular_expiracao(plano, base=None):
    if base is None:
        base = datetime.utcnow()
    if plano == 'vitalicio':
        return datetime.utcnow() + timedelta(days=36500)
    elif plano == 'anual':
        return base + timedelta(days=365)
    else:
        return base + timedelta(days=30)

def enviar_email(destinatario, nome, email, senha, plano):
    try:
        plano_texto = "Vitalício" if plano == "vitalicio" else "Anual" if plano == "anual" else "Mensal"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; background: #0d0d0d; color: #e8e8e8; padding: 32px; border-radius: 8px;">
            <h2 style="color: #ff6b1a;">🖨 ShopeeZPLPrinter</h2>
            <p>Olá, <strong>{nome}</strong>! Seu acesso foi liberado.</p>
            <div style="background: #1a1a1a; padding: 16px; border-radius: 6px; margin: 24px 0;">
                <p style="margin: 4px 0;"><strong>Plano:</strong> {plano_texto}</p>
                <p style="margin: 4px 0;"><strong>E-mail:</strong> {email}</p>
                <p style="margin: 4px 0;"><strong>Senha:</strong> <span style="color: #ff6b1a; font-size: 18px;">{senha}</span></p>
            </div>
            <p>Baixe o programa, abra e faça login com essas credenciais.</p>
            <p style="color: #666; font-size: 12px;">Guarde sua senha em um local seguro.</p>
        </div>
        """
        payload = json.dumps({
            "sender": {"name": "ShopeeZPLPrinter", "email": "shopeezplprinter@gmail.com"},
            "to": [{"email": destinatario, "name": nome}],
            "subject": "Seu acesso ao ShopeeZPLPrinter",
            "htmlContent": html
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={
                "api-key": BREVO_API_KEY,
                "Content-Type": "application/json"
            },
            method="POST"
        )
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False

def enviar_email_renovacao(destinatario, nome, plano, nova_expiracao):
    try:
        plano_texto = "Vitalício" if plano == "vitalicio" else "Anual" if plano == "anual" else "Mensal"
        expiracao_texto = nova_expiracao.strftime('%d/%m/%Y')
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; background: #0d0d0d; color: #e8e8e8; padding: 32px; border-radius: 8px;">
            <h2 style="color: #ff6b1a;">🖨 ShopeeZPLPrinter</h2>
            <p>Olá, <strong>{nome}</strong>! Sua licença foi renovada.</p>
            <div style="background: #1a1a1a; padding: 16px; border-radius: 6px; margin: 24px 0;">
                <p style="margin: 4px 0;"><strong>Plano:</strong> {plano_texto}</p>
                <p style="margin: 4px 0;"><strong>Nova expiração:</strong> {expiracao_texto}</p>
            </div>
            <p>Continue usando normalmente com suas credenciais atuais.</p>
        </div>
        """
        payload = json.dumps({
            "sender": {"name": "ShopeeZPLPrinter", "email": "shopeezplprinter@gmail.com"},
            "to": [{"email": destinatario, "name": nome}],
            "subject": "Sua licença foi renovada - ShopeeZPLPrinter",
            "htmlContent": html
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={
                "api-key": BREVO_API_KEY,
                "Content-Type": "application/json"
            },
            method="POST"
        )
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        print(f"Erro ao enviar email renovacao: {e}")
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json

    try:
        evento = data['event']
        comprador = data['data']['buyer']
        email = comprador['email']
        nome = comprador['name']
        produto = data['data']['product']['name']

        if evento == 'PURCHASE_APPROVED':
            plano = identificar_plano(produto)

            try:
                # Usuário já existe
                usuario = auth.get_user_by_email(email)
                doc = db.collection('licenses').document(usuario.uid).get()
                dados = doc.to_dict() if doc.exists else {}

                # Calcula nova expiração somando dias restantes
               expiracao_atual = dados.get('expiracao', datetime.utcnow())
if hasattr(expiracao_atual, 'tzinfo') and expiracao_atual.tzinfo is not None:
    expiracao_atual = expiracao_atual.replace(tzinfo=None)
ativo_atual = dados.get('ativo', True)
if ativo_atual:
    base = max(expiracao_atual, datetime.utcnow())
else:
    base = datetime.utcnow()
nova_expiracao = calcular_expiracao(plano, base)

                # Atualiza sem trocar senha e sem resetar deviceId
                db.collection('licenses').document(usuario.uid).update({
                    'plano': plano,
                    'ativo': True,
                    'expiracao': nova_expiracao,
                    'produto': produto
                })

                enviar_email_renovacao(email, nome, plano, nova_expiracao)

            except:
                # Usuário novo
                senha = gerar_senha()
                nova_expiracao = calcular_expiracao(plano)
                usuario = auth.create_user(email=email, password=senha)
                db.collection('licenses').document(usuario.uid).set({
                    'email': email,
                    'nome': nome,
                    'produto': produto,
                    'plano': plano,
                    'ativo': True,
                    'deviceId': '',
                    'expiracao': nova_expiracao
                })
                enviar_email(email, nome, email, senha, plano)

            return jsonify({'status': 'sucesso', 'plano': plano, 'email': email}), 200

        if evento in ['PURCHASE_CANCELLED', 'PURCHASE_REFUNDED']:
            try:
                usuario = auth.get_user_by_email(email)
                db.collection('licenses').document(usuario.uid).update({'ativo': False})
            except:
                pass
            return jsonify({'status': 'licenca desativada'}), 200

        return jsonify({'status': 'ignorado'}), 200

    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/')
def index():
    return 'API ShopeeZPLPrinter rodando!', 200

if __name__ == '__main__':
    app.run()
