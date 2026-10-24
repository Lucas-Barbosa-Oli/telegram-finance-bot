"""Small asynchronous Supabase Data API client with pooled HTTP connections."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5
import httpx
from utils.domain import Transaction

COLUMNS = 'id,user_id,amount,type,category,description,status,occurred_on,created_at,deleted_at'
PAGE_SIZE = 500


class DatabaseError(RuntimeError):
    pass


class FinanceStore:
    def __init__(self, client, url, key):
        self.client = client
        self.base = url.rstrip('/') + '/rest/v1'
        self.headers = {'apikey': key, 'Content-Type': 'application/json'}
        # New sb_secret keys are API keys, not JWT bearer tokens.
        if not key.startswith('sb_secret_'):
            self.headers['Authorization'] = f'Bearer {key}'

    async def request(self, method, table, params=None, payload=None, prefer='return=representation'):
        try:
            response = await self.client.request(
                method, self.base + '/' + table, params=params, json=payload,
                headers={**self.headers, 'Prefer': prefer}, timeout=10,
            )
            response.raise_for_status()
            return json.loads(response.text, parse_float=Decimal) if response.content else []
        except (httpx.HTTPError, ValueError) as exc:
            # Do not expose keys, request URLs, database details, or finance data.
            raise DatabaseError('Não foi possível confirmar a operação. Consulte /extrato antes de reenviar para evitar duplicatas.') from exc

    @staticmethod
    def scope(user_id):
        if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
            raise ValueError('Usuário inválido.')
        return [('user_id', f'eq.{user_id}'), ('deleted_at', 'is.null')]

    async def health(self):
        await self.request('GET', 'transactions', [('select', 'id,occurred_on,source_message_id,deleted_at'), ('limit', '0')])
        await self.request('GET', 'finance_drafts', [('select', 'id,payload,expires_at'), ('limit', '0')])

    async def create(self, user_id, chat_id, message_id, transaction):
        data = Transaction.from_dict(transaction.as_dict()).as_dict()
        self.scope(user_id)
        data.update(user_id=user_id, source_chat_id=chat_id, source_message_id=message_id)
        rows = await self.request('POST', 'transactions',
            [('on_conflict', 'user_id,source_chat_id,source_message_id')], data,
            'resolution=ignore-duplicates,return=representation')
        if rows:
            return rows[0], True
        rows = await self.request('GET', 'transactions', [
            ('user_id', f'eq.{user_id}'), ('source_chat_id', f'eq.{chat_id}'),
            ('source_message_id', f'eq.{message_id}'), ('select', COLUMNS), ('limit', '1')])
        if not rows:
            raise DatabaseError('Não foi possível verificar o lançamento. Tente novamente.')
        return rows[0], False

    async def list(self, user_id, period=None, status=None, kind=None, category=None, limit=None, before=None):
        filters = self.scope(user_id)
        if period:
            filters += [('occurred_on', f'gte.{period.start}'), ('occurred_on', f'lt.{period.end}')]
        if status:
            filters += [('status', f'eq.{status}')]
        if kind:
            filters += [('type', f'eq.{kind}')]
        if category:
            filters += [('category', f'eq.{category}')]
        rows, cursor = [], before
        while True:
            size = min(PAGE_SIZE, limit - len(rows)) if limit else PAGE_SIZE
            params = filters + [('select', COLUMNS), ('order', 'id.desc'), ('limit', str(size))]
            if cursor:
                params += [('id', f'lt.{int(cursor)}')]
            batch = await self.request('GET', 'transactions', params)
            rows.extend(batch)
            # Continue until empty, even if Supabase's configured max-rows is below page size.
            if not batch or (limit and len(rows) >= limit):
                return rows
            cursor = batch[-1]['id']
            if len(rows) >= 50000:
                raise ValueError('Há muitos lançamentos. Escolha um período menor.')

    async def get(self, user_id, transaction_id):
        rows = await self.request('GET', 'transactions', self.scope(user_id) + [
            ('id', f'eq.{int(transaction_id)}'), ('select', COLUMNS), ('limit', '1')])
        if not rows:
            raise ValueError('Lançamento não encontrado para este usuário.')
        return rows[0]

    async def update(self, user_id, transaction_id, changes):
        row = await self.get(user_id, transaction_id)
        validated = Transaction.from_dict({**row, **changes}).as_dict()
        payload = {key: validated[key] for key in changes}
        rows = await self.request('PATCH', 'transactions', self.scope(user_id) + [('id', f'eq.{int(transaction_id)}')], payload)
        if not rows:
            raise ValueError('Lançamento não encontrado.')
        return rows[0]

    async def delete(self, user_id, transaction_id):
        # Soft deletion keeps the unique message key, so Telegram retries cannot resurrect it.
        await self.request('PATCH', 'transactions', self.scope(user_id) + [('id', f'eq.{int(transaction_id)}')],
                           {'deleted_at': datetime.now(timezone.utc).isoformat()})

    async def save_draft(self, user_id, chat_id, message_id, transaction):
        draft_id = str(uuid5(NAMESPACE_URL, f'finance:{user_id}:{chat_id}:{message_id}'))
        await self.request('DELETE', 'finance_drafts', [
            ('user_id', f'eq.{user_id}'), ('expires_at', f'lt.{datetime.now(timezone.utc).isoformat()}')])
        await self.request('POST', 'finance_drafts', [('on_conflict', 'id')], {
            'id': draft_id, 'user_id': user_id, 'source_chat_id': chat_id,
            'source_message_id': message_id, 'payload': transaction.as_dict(),
            'expires_at': (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        }, 'resolution=ignore-duplicates,return=representation')
        return draft_id

    async def get_draft(self, user_id, draft_id):
        rows = await self.request('GET', 'finance_drafts', [
            ('id', f'eq.{draft_id}'), ('user_id', f'eq.{user_id}'),
            ('expires_at', f'gt.{datetime.now(timezone.utc).isoformat()}'), ('limit', '1')])
        if not rows:
            raise ValueError('Esta prévia expirou ou já foi usada. Envie a mensagem novamente.')
        return rows[0]

    async def delete_draft(self, user_id, draft_id):
        await self.request('DELETE', 'finance_drafts', [('id', f'eq.{draft_id}'), ('user_id', f'eq.{user_id}')])
