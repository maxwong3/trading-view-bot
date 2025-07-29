import asyncio
import logging
import os
import sys
from fastapi import HTTPException, status
from db import pool

queue = asyncio.Queue()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("discord.log", encoding="utf-8", mode="w"),
    ]
)

logger = logging.getLogger(__name__)

# Helper methods for bot
async def get_prefix(bot, message):
    if message.guild is None:
        return '!'
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                    SELECT prefix FROM servers
                    WHERE server_id = %s
                ''', (message.guild.id,))
                res = await cur.fetchone()
        if res is None:
            logger.info("ERROR: server not found in db!")
            return '!'
        else:
            return res[0]
    except Exception as e:
        logger.error(f"DB error in get_prefix: {e}")
        return '!'

async def toggle_alerts(server_id):
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(''' 
                            UPDATE servers
                            SET alerts_on = NOT alerts_on
                            WHERE server_id = %s;
                            ''', (server_id,))
                await conn.commit()
                await cur.execute('''
                            SELECT alerts_on
                            FROM servers
                            WHERE server_id = %s;
                            ''', (server_id,))
                res = await cur.fetchone()
                if res is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Server not found: {server_id}")
                else:
                    return res[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DB error in toggle_alerts: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal database error")

async def set_channel(server_id, channel_id, ticker, signal=None):
    # Handles advanced signals
    signal_type = 'NONE' if signal is None else signal.upper()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                            INSERT INTO channels (channel_id, server_id, ticker, signal_type)
                            VALUES(%s, %s, %s, %s)
                            ON CONFLICT (server_id, ticker, signal_type) DO UPDATE
                            SET channel_id = EXCLUDED.channel_id
                            ''', (channel_id, server_id, ticker.upper(), signal_type))
                await conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DB error in set_channel: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal database error")

async def set_secret(server_id, secret=None):
    if secret is not None:
        secret = secret.strip()
        if secret == '':
            secret = None 
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                            INSERT INTO servers (server_id, secret)
                            VALUES(%s, %s)
                            ON CONFLICT (server_id) DO UPDATE
                            SET secret = EXCLUDED.secret
                            ''', (server_id, secret))
                await conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DB error in set_secret: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal database error")

async def get_secret(server_id):
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                            SELECT secret
                            FROM servers
                            WHERE server_id = %s;
                            ''', (server_id,))
                row = await cur.fetchone()
                if row:
                    return row[0]
                else:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Server not found: {server_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DB error in get_secret: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal database error")