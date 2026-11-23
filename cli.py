"""Comandos de administração.

    python cli.py sync                     # do último dia sincronizado até hoje
    python cli.py sync --de 2026-01-01 --ate 2026-01-31
    python cli.py criar-chave "Fulano" fulano@exemplo.com
    python cli.py desativar-chave ck_AbCdEfG
"""

import argparse
import logging
import sys
from datetime import date

from app.auth import criar_chave
from app.db import SessionLocal, init_db
from app.ingest import sincronizar_incremental, sincronizar_periodo
from app.models import ApiKey
from app.pncp import PncpClient


def cmd_sync(args) -> None:
    client = PncpClient()
    try:
        with SessionLocal() as session:
            if args.de:
                ate = args.ate or date.today()
                total = sincronizar_periodo(session, client, args.de, ate)
            else:
                total = sincronizar_incremental(session, client, dias_iniciais=args.dias)
    finally:
        client.close()
    print(f"{total} contratos gravados.")


def cmd_criar_chave(args) -> None:
    with SessionLocal() as session:
        _, chave = criar_chave(session, args.nome, args.email)
    print(chave)


def cmd_desativar_chave(args) -> None:
    with SessionLocal() as session:
        chaves = session.query(ApiKey).filter_by(prefix=args.prefixo[:10]).all()
        if not chaves:
            sys.exit("Nenhuma chave com esse prefixo.")
        for chave in chaves:
            chave.ativa = False
        session.commit()
    print(f"{len(chaves)} chave(s) desativada(s).")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("sync", help="Baixa contratos do PNCP")
    p.add_argument("--de", type=date.fromisoformat, help="Data inicial (AAAA-MM-DD)")
    p.add_argument("--ate", type=date.fromisoformat, help="Data final (AAAA-MM-DD)")
    p.add_argument("--dias", type=int, default=7, help="Dias para trás na primeira execução")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("criar-chave", help="Cria uma chave de API")
    p.add_argument("nome")
    p.add_argument("email")
    p.set_defaults(func=cmd_criar_chave)

    p = sub.add_parser("desativar-chave", help="Desativa uma chave pelo prefixo")
    p.add_argument("prefixo", help="Os primeiros 10 caracteres da chave")
    p.set_defaults(func=cmd_desativar_chave)

    args = parser.parse_args()
    init_db()
    args.func(args)


if __name__ == "__main__":
    main()
