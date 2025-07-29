import asyncio
import discord
from discord.ext import commands
from discord import Embed
import logging
from dotenv import load_dotenv
import os
import json
from datetime import datetime
import sys
from fastapi import FastAPI, Request, HTTPException, status
from contextlib import asynccontextmanager
from shared import logger, queue
from db import pool
from bot import bot
from models import AlertPayload

asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

load_dotenv()

handler = logging.StreamHandler(sys.stdout)
logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not set in .env")
    task = asyncio.create_task(bot.start(token))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Bot task cancelled cleanly.")

    try:
        await bot.close()
        logger.info("Bot closed.")
    except Exception as e:
        logger.warning(f"Error during bot close: {e}")
    try:
        await pool.close()
        logger.info("Database pool closed.")
    except Exception as e:
        logger.warning(f"Error closing DB pool: {e}")
        
app = FastAPI(lifespan=lifespan)


@app.get('/')
async def home():
    return {'Message': 'Running'}

@app.get('/health')
async def health():
    return {"status": "healthy"}

@app.post('/webhook')
async def webhook(payload: AlertPayload):
    try:
        await queue.put(payload.model_dump(exclude_unset=True))
        # 200 Success
        return {"status": "success"}
    except Exception as e:
        logger.error("Webhook error")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")
